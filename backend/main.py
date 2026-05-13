from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models
import schemas
from database import engine, SessionLocal
import datetime
import os
import afl_engine
import odds_api

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AFL +EV Betting Model")

# Configure CORS
origins = [
    "http://localhost:5173", # Vite default
    "http://127.0.0.1:5173",
]
extra_origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGIN", "").split(",") if origin.strip()]
origins.extend(extra_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

MIN_EV_THRESHOLD = float(os.getenv("MIN_EV_THRESHOLD", "5.0"))
SIMULATION_COUNT = int(os.getenv("SIMULATION_COUNT", "20000"))
MAX_MARKET_EDGE = float(os.getenv("MAX_MARKET_EDGE", "0.08"))


def reset_non_afl_data(db: Session):
    stale_match = db.query(models.Match).filter(
        (~models.Match.home_team.in_(afl_engine.list_afl_teams()))
        | (~models.Match.away_team.in_(afl_engine.list_afl_teams()))
    ).first()

    if stale_match:
        db.query(models.Bet).delete()
        db.query(models.Match).delete()
        db.commit()


def seed_database(db: Session):
    reset_non_afl_data(db)
    if db.query(models.Match).count() > 0:
        return

    live_odds = odds_api.fetch_live_odds()
    sync_matches_from_odds(db, live_odds)


def sync_matches_from_odds(db: Session, live_odds):
    for event in odds_api.parse_events(live_odds):
        match = db.query(models.Match).filter(
            models.Match.home_team == event["home_team"],
            models.Match.away_team == event["away_team"],
            models.Match.status == "upcoming",
        ).first()

        if match:
            match.venue = event["venue"]
            match.match_date = _naive_utc(event["match_date"])
            continue

        db.add(
            models.Match(
                home_team=event["home_team"],
                away_team=event["away_team"],
                venue=event["venue"],
                match_date=_naive_utc(event["match_date"]),
                status="upcoming",
            )
        )

    db.commit()

@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    seed_database(db)
    db.close()

@app.get("/api/matches", response_model=list[schemas.Match])
def get_matches(db: Session = Depends(get_db)):
    return db.query(models.Match).order_by(models.Match.match_date.asc()).all()


@app.get("/api/matches/{match_id}/projection", response_model=schemas.MatchProjection)
def get_match_projection(match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    projection = afl_engine.predict_match(match.home_team, match.away_team, match.venue)
    return schemas.MatchProjection(
        match_id=match.id,
        home_team=match.home_team,
        away_team=match.away_team,
        venue=match.venue,
        home_win_probability=round(projection["home_prob"], 3),
        away_win_probability=round(projection["away_prob"], 3),
        expected_home_score=round(projection["expected_home_score"], 1),
        expected_away_score=round(projection["expected_away_score"], 1),
        expected_margin=round(projection["expected_margin"], 1),
        expected_total=round(projection["expected_total"], 1),
    )

@app.get("/api/bets/ev", response_model=list[schemas.Bet])
def get_ev_bets(db: Session = Depends(get_db)):
    ev_bets = db.query(models.Bet, models.Match)\
                .join(models.Match, models.Bet.match_id == models.Match.id)\
                .filter(models.Bet.is_value_bet == True)\
                .order_by(models.Bet.ev_percentage.desc()).all()
    
    out = []
    for bet, match in ev_bets:
        bet_data = bet.__dict__.copy()
        bet_data["match_date"] = match.match_date
        bet_data["home_team"] = match.home_team
        bet_data["away_team"] = match.away_team
        out.append(bet_data)
        
    return out

@app.get("/api/stats", response_model=schemas.DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    ev_bets = db.query(models.Bet).filter(models.Bet.is_value_bet == True).all()
    total_ev = len(ev_bets)
    avg_ev = sum([b.ev_percentage for b in ev_bets]) / total_ev if total_ev > 0 else 0.0
    upcoming = db.query(models.Match).filter(models.Match.status == "upcoming").count()
    return schemas.DashboardStats(
        total_ev_bets=total_ev,
        avg_ev_percentage=round(avg_ev, 2),
        total_matches_upcoming=upcoming
    )

def simulate_new_data():
    db = SessionLocal()
    try:
        db.query(models.Bet).delete()
        db.commit()

        live_odds = odds_api.fetch_live_odds()
        sync_matches_from_odds(db, live_odds)
        parsed_odds = odds_api.parse_odds(live_odds)
        market_consensus = _build_market_consensus(parsed_odds)
        mc_cache = {}

        for odd in parsed_odds:
            h_team = odd["home_team"]
            a_team = odd["away_team"]
            match_key = f"{h_team}_{a_team}"

            if match_key not in mc_cache:
                mc_cache[match_key] = afl_engine.run_monte_carlo_simulation(
                    h_team,
                    a_team,
                    afl_engine.get_default_venue(h_team),
                    num_simulations=SIMULATION_COUNT,
                )

            model_probability = _market_probability(
                odd,
                mc_cache[match_key],
                market_consensus,
            )
            if model_probability is None:
                continue

            bookmaker_odds = float(odd["odds"])
            ev = afl_engine.calculate_ev(model_probability, bookmaker_odds)
            if ev is None:
                continue

            ev_percentage = round(ev * 100, 2)
            if ev_percentage <= MIN_EV_THRESHOLD:
                continue

            match = db.query(models.Match).filter(
                models.Match.home_team == h_team,
                models.Match.away_team == a_team,
                models.Match.status == "upcoming",
            ).first()
            if not match:
                continue

            db.add(
                models.Bet(
                    match_id=match.id,
                    market=_format_market(odd["market"]),
                    selection=_format_selection(odd),
                    bookmaker_odds=bookmaker_odds,
                    model_probability=round(model_probability, 3),
                    ev_percentage=ev_percentage,
                    is_value_bet=True,
                    bookmaker=odd["bookmaker"],
                )
            )

        db.commit()
    finally:
        db.close()

@app.post("/api/run-simulation")
def trigger_simulation(background_tasks: BackgroundTasks):
    background_tasks.add_task(simulate_new_data)
    return {"message": f"AFL simulation queued with {SIMULATION_COUNT:,} iterations per match."}


def _raw_market_probability(odd, mc):
    market = odd["market"]
    selection = odd["selection"]
    point = odd.get("point")

    if market == "h2h":
        if selection == mc["home_team"]:
            return mc["mc_home_prob"]
        if selection == mc["away_team"]:
            return mc["mc_away_prob"]
        return None

    if market == "totals":
        if point is None:
            return None
        point_val = float(point)
        over_prob = sum(1 for total in mc["total_points_list"] if total > point_val) / len(mc["total_points_list"])
        if str(selection).lower() == "over":
            return over_prob
        if str(selection).lower() == "under":
            return 1.0 - over_prob
        return None

    if market == "spreads":
        if point is None:
            return None
        point_val = float(point)
        if selection == mc["home_team"]:
            cover_count = sum(1 for margin in mc["home_margins"] if margin + point_val > 0)
        elif selection == mc["away_team"]:
            cover_count = sum(1 for margin in mc["home_margins"] if -margin + point_val > 0)
        else:
            return None
        return cover_count / len(mc["home_margins"])

    return None


def _build_market_consensus(parsed_odds):
    grouped = {}
    for odd in parsed_odds:
        market = odd["market"]
        point = odd.get("point")
        if market == "spreads" and point is not None:
            point = abs(float(point))
        elif market == "totals" and point is not None:
            point = float(point)

        key = (
            odd["home_team"],
            odd["away_team"],
            market,
            point,
            odd["bookmaker"],
        )
        grouped.setdefault(key, []).append(odd)

    consensus_samples = {}
    for outcomes in grouped.values():
        implied_sum = sum(1.0 / float(outcome["odds"]) for outcome in outcomes if float(outcome["odds"]) > 1.0)
        if implied_sum <= 0:
            continue

        for outcome in outcomes:
            outcome_key = _consensus_key(outcome)
            fair_probability = (1.0 / float(outcome["odds"])) / implied_sum
            consensus_samples.setdefault(outcome_key, []).append(fair_probability)

    return {
        key: sum(values) / len(values)
        for key, values in consensus_samples.items()
        if values
    }


def _consensus_key(odd):
    point = odd.get("point")
    if odd["market"] == "spreads" and point is not None:
        point = abs(float(point))
    elif odd["market"] == "totals" and point is not None:
        point = float(point)

    return (
        odd["home_team"],
        odd["away_team"],
        odd["market"],
        point,
        odd["selection"],
    )


def _market_probability(odd, mc, market_consensus=None):
    raw_probability = _raw_market_probability(odd, mc)
    if raw_probability is None:
        return None

    consensus_probability = (market_consensus or {}).get(_consensus_key(odd))
    if consensus_probability is None:
        return raw_probability

    edge = raw_probability - consensus_probability
    calibrated_edge = max(-MAX_MARKET_EDGE, min(MAX_MARKET_EDGE, edge))
    return max(0.02, min(0.98, consensus_probability + calibrated_edge))


def _format_market(market):
    labels = {"h2h": "Head to Head", "spreads": "Line", "totals": "Total Points"}
    return labels.get(market, market)


def _format_selection(odd):
    point = odd.get("point")
    selection = odd["selection"]
    if point is None:
        return selection

    if odd["market"] == "spreads":
        point_value = float(point)
        sign = "+" if point_value > 0 else ""
        return f"{selection} {sign}{point_value:g}"

    if odd["market"] == "totals":
        return f"{selection} {float(point):g}"

    return selection


def _naive_utc(value):
    if value.tzinfo:
        return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return value
