from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import Session
import models
import schemas
from database import engine, SessionLocal
import datetime
import os
import afl_engine
import odds_api
import squiggle_api

models.Base.metadata.create_all(bind=engine)

# In-memory Elo ratings cache, populated at startup from Squiggle results.
_elo_ratings: dict = {}


def run_migrations():
    """Add any new columns to existing tables without full Alembic migrations."""
    inspector = sa_inspect(engine)
    existing = {col["name"] for col in inspector.get_columns("bets")}
    new_cols = {"kelly_fraction": "FLOAT", "consensus_probability": "FLOAT"}
    with engine.connect() as conn:
        for col, col_type in new_cols.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE bets ADD COLUMN {col} {col_type}"))
                conn.commit()


def build_elo_ratings():
    global _elo_ratings
    results = squiggle_api.fetch_completed_games()
    if results:
        _elo_ratings = afl_engine.update_elo_ratings(results)
        print(f"Elo ratings built from {len(results)} completed games.")
    else:
        _elo_ratings = {team: p["rating"] for team, p in afl_engine.TEAM_PROFILES.items()}
        print("Using base ratings (Squiggle returned no data).")

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
MAX_MARKET_EDGE = float(os.getenv("MAX_MARKET_EDGE", "0.05"))
MAX_BOOK_EDGE = float(os.getenv("MAX_BOOK_EDGE", "0.015"))


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
    run_migrations()
    build_elo_ratings()
    db = SessionLocal()
    seed_database(db)
    db.close()

@app.get("/api/elo-ratings")
def get_elo_ratings():
    return {
        "ratings": dict(sorted(_elo_ratings.items(), key=lambda x: x[1], reverse=True))
    }


@app.post("/api/refresh-elo")
def refresh_elo(background_tasks: BackgroundTasks):
    background_tasks.add_task(build_elo_ratings)
    return {"message": "Elo ratings refresh queued from Squiggle."}


@app.get("/api/methodology")
def get_methodology():
    """Returns full model parameters, team ratings, and venue adjustments for full transparency."""
    teams = []
    for team, profile in afl_engine.TEAM_PROFILES.items():
        current = _elo_ratings.get(team, profile["rating"])
        teams.append({
            "team": team,
            "base_rating": profile["rating"],
            "current_rating": round(current, 1),
            "rating_delta": round(current - profile["rating"], 1),
            "attack": profile["attack"],
            "defence": profile["defence"],
            "home_venue": profile["venue"],
        })
    teams.sort(key=lambda t: t["current_rating"], reverse=True)

    return {
        "model_parameters": {
            "league_avg_team_score": afl_engine.LEAGUE_AVG_TEAM_SCORE,
            "home_ground_advantage_points": afl_engine.HOME_GROUND_ADVANTAGE_POINTS,
            "margin_std_dev": afl_engine.MARGIN_STD_DEV,
            "score_std_dev": afl_engine.SCORE_STD_DEV,
            "elo_k_factor": afl_engine.ELO_K,
            "elo_home_advantage": afl_engine.ELO_HOME_ADVANTAGE,
            "rating_to_margin_divisor": 28.0,
            "simulation_count": SIMULATION_COUNT,
            "min_ev_threshold_pct": MIN_EV_THRESHOLD,
            "max_market_edge": MAX_MARKET_EDGE,
            "max_book_edge": MAX_BOOK_EDGE,
            "kelly_fraction_default": 0.5,
        },
        "venue_adjustments": afl_engine.VENUE_SCORING_ADJUSTMENTS,
        "teams": teams,
        "data_sources": {
            "odds": "The Odds API (aussierules_afl, AU region)",
            "results": "Squiggle API (https://api.squiggle.com.au/)",
        },
    }


@app.get("/api/matches/{match_id}/context")
def get_match_context(match_id: int, db: Session = Depends(get_db)):
    """Returns the full calculation breakdown and live market for a match."""
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    home = match.home_team
    away = match.away_team
    venue = match.venue

    home_profile = afl_engine.TEAM_PROFILES.get(home, {"rating": 1500, "attack": 0, "defence": 0})
    away_profile = afl_engine.TEAM_PROFILES.get(away, {"rating": 1500, "attack": 0, "defence": 0})
    home_base = home_profile["rating"]
    away_base = away_profile["rating"]
    home_elo = round(_elo_ratings.get(home, home_base), 1)
    away_elo = round(_elo_ratings.get(away, away_base), 1)

    projection = afl_engine.predict_match(home, away, venue, elo_ratings=_elo_ratings)
    mc = afl_engine.run_monte_carlo_simulation(
        home, away, venue, num_simulations=10000, elo_ratings=_elo_ratings
    )
    margins = sorted(mc["home_margins"])
    totals = sorted(mc["total_points_list"])
    n = len(margins) or 1

    rating_margin = (home_elo - away_elo) / 28.0
    venue_adj = afl_engine.VENUE_SCORING_ADJUSTMENTS.get(venue, 0.0)

    # Pull live bookmaker prices for this match.
    live_odds = odds_api.fetch_live_odds()
    parsed = odds_api.parse_odds(live_odds)
    match_odds = [o for o in parsed if o["home_team"] == home and o["away_team"] == away]

    market_consensus, _ = _build_market_consensus(match_odds)

    markets = {"h2h": [], "spreads": [], "totals": []}
    for o in match_odds:
        if o["market"] in markets:
            implied = round(1.0 / float(o["odds"]), 4) if o["odds"] else None
            markets[o["market"]].append({
                "bookmaker": o["bookmaker"],
                "selection": o["selection"],
                "odds": o["odds"],
                "point": o.get("point"),
                "implied_probability": implied,
            })

    consensus_rows = []
    for key, prob in market_consensus.items():
        h, a, mkt, point, sel = key
        if h == home and a == away:
            consensus_rows.append({
                "market": mkt,
                "selection": sel,
                "point": point,
                "fair_probability": round(prob, 4),
                "fair_odds": round(1.0 / prob, 2) if prob else None,
            })

    return {
        "match_id": match.id,
        "home_team": home,
        "away_team": away,
        "venue": venue,
        "match_date": match.match_date,
        "ratings": {
            "home_base": home_base,
            "away_base": away_base,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "home_elo_delta": round(home_elo - home_base, 1),
            "away_elo_delta": round(away_elo - away_base, 1),
            "elo_gap": round(home_elo - away_elo, 1),
        },
        "calculation": {
            "rating_margin_points": round(rating_margin, 2),
            "home_ground_advantage": afl_engine.HOME_GROUND_ADVANTAGE_POINTS,
            "venue_scoring_adjustment": venue_adj,
            "expected_margin": round(projection["expected_margin"], 2),
            "expected_total": round(projection["expected_total"], 2),
            "expected_home_score": round(projection["expected_home_score"], 2),
            "expected_away_score": round(projection["expected_away_score"], 2),
            "home_attack": home_profile.get("attack", 0),
            "home_defence": home_profile.get("defence", 0),
            "away_attack": away_profile.get("attack", 0),
            "away_defence": away_profile.get("defence", 0),
        },
        "probabilities": {
            "home_win_analytical": round(projection["home_prob"], 4),
            "away_win_analytical": round(projection["away_prob"], 4),
            "home_win_mc": round(mc["mc_home_prob"], 4),
            "away_win_mc": round(mc["mc_away_prob"], 4),
            "mc_simulations": mc["num_simulations"],
        },
        "distributions": {
            "margin_p10": round(margins[int(n * 0.10)], 1),
            "margin_p50": round(margins[int(n * 0.50)], 1),
            "margin_p90": round(margins[int(n * 0.90)], 1),
            "total_p10": round(totals[int(n * 0.10)], 1),
            "total_p50": round(totals[int(n * 0.50)], 1),
            "total_p90": round(totals[int(n * 0.90)], 1),
        },
        "markets": markets,
        "consensus": consensus_rows,
    }


@app.get("/api/matches", response_model=list[schemas.Match])
def get_matches(db: Session = Depends(get_db)):
    return db.query(models.Match).order_by(models.Match.match_date.asc()).all()


@app.get("/api/matches/{match_id}/projection", response_model=schemas.MatchProjection)
def get_match_projection(match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    projection = afl_engine.predict_match(match.home_team, match.away_team, match.venue, elo_ratings=_elo_ratings)
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
        market_consensus, bookmaker_consensus = _build_market_consensus(parsed_odds)
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
                    elo_ratings=_elo_ratings,
                )

            model_probability = _market_probability(
                odd,
                mc_cache[match_key],
                market_consensus,
                bookmaker_consensus,
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

            consensus_prob = (market_consensus or {}).get(_consensus_key(odd))
            kelly = afl_engine.calculate_kelly(model_probability, bookmaker_odds)

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
                    kelly_fraction=kelly,
                    consensus_probability=round(consensus_prob, 3) if consensus_prob else None,
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
    bookmaker_samples = {}
    for outcomes in grouped.values():
        implied_sum = sum(1.0 / float(outcome["odds"]) for outcome in outcomes if float(outcome["odds"]) > 1.0)
        if implied_sum <= 0:
            continue

        for outcome in outcomes:
            outcome_key = _consensus_key(outcome)
            fair_probability = (1.0 / float(outcome["odds"])) / implied_sum
            consensus_samples.setdefault(outcome_key, []).append(fair_probability)
            bookmaker_samples[_bookmaker_consensus_key(outcome)] = fair_probability

    return {
        key: sum(values) / len(values)
        for key, values in consensus_samples.items()
        if values
    }, bookmaker_samples


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


def _bookmaker_consensus_key(odd):
    return (*_consensus_key(odd), odd["bookmaker"])


def _market_probability(odd, mc, market_consensus=None, bookmaker_consensus=None):
    raw_probability = _raw_market_probability(odd, mc)
    if raw_probability is None:
        return None

    consensus_probability = (market_consensus or {}).get(_consensus_key(odd))
    if consensus_probability is None:
        return raw_probability

    edge = raw_probability - consensus_probability
    calibrated_edge = max(-MAX_MARKET_EDGE, min(MAX_MARKET_EDGE, edge))
    calibrated_probability = consensus_probability + calibrated_edge

    bookmaker_probability = (bookmaker_consensus or {}).get(_bookmaker_consensus_key(odd))
    if bookmaker_probability is not None:
        calibrated_probability = min(calibrated_probability, bookmaker_probability + MAX_BOOK_EDGE)

    return max(0.02, min(0.98, calibrated_probability))


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
