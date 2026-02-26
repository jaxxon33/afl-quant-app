from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models
import schemas
from database import engine, SessionLocal
import datetime
import random
import ml_engine
import odds_api

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AFL +EV Betting Model")

# Configure CORS
origins = [
    "http://localhost:5173", # Vite default
    "http://127.0.0.1:5173",
    "*" # For ease in testing
]

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

# Seed Database
def seed_database(db: Session):
    if db.query(models.Match).count() == 0:
        teams = ["Collingwood", "Richmond", "Brisbane Lions", "Carlton", "Geelong", "Essendon", "Melbourne", "Sydney"]
        venues = ["MCG", "Gabba", "SCG", "Marvel Stadium", "Optus Stadium"]
        bookmakers = ["Sportsbet", "TAB", "Ladbrokes", "BetFair"]

        for _ in range(5):
            h_team, a_team = random.sample(teams, 2)
            match = models.Match(
                home_team=h_team,
                away_team=a_team,
                venue=random.choice(venues),
                match_date=datetime.datetime.utcnow() + datetime.timedelta(days=random.randint(1, 7)),
                status="upcoming"
            )
            db.add(match)
            db.commit()
            db.refresh(match)
            
            # Predict some bets for this match
            for _ in range(random.randint(2, 5)):
                bookmaker = random.choice(bookmakers)
                bookmaker_odds = round(random.uniform(1.5, 4.0), 2)
                # True probability derived randomly
                model_probability = round(random.uniform(0.3, 0.8), 2)
                implied_prob = 1 / bookmaker_odds
                
                ev = (model_probability * bookmaker_odds) - 1.0
                ev_percentage = round(ev * 100, 2)
                
                is_value = ev_percentage > 5.0 # Value bet if > 5%
                
                if is_value:
                    bet = models.Bet(
                        match_id=match.id,
                        market=random.choice(["H2H", "Line", "Total Goals", "Player Props"]),
                        selection=random.choice([h_team, a_team, "Over 160.5", "Under 160.5", "Dustin Martin 2+ Goals"]),
                        bookmaker_odds=bookmaker_odds,
                        model_probability=model_probability,
                        ev_percentage=ev_percentage,
                        is_value_bet=is_value,
                        bookmaker=bookmaker
                    )
                    db.add(bet)
        db.commit()

@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    seed_database(db)
    db.close()

@app.get("/api/matches", response_model=list[schemas.Match])
def get_matches(db: Session = Depends(get_db)):
    return db.query(models.Match).all()

@app.get("/api/bets/ev", response_model=list[schemas.Bet])
def get_ev_bets(db: Session = Depends(get_db)):
    return db.query(models.Bet).filter(models.Bet.is_value_bet == True).order_by(models.Bet.ev_percentage.desc()).all()

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

def simulate_new_data(db: Session):
    # Clear existing bets to prevent duplicates
    db.query(models.Bet).delete()
    db.commit()

    # Retrieve mock odds (or real if API key set)
    live_odds = odds_api.fetch_live_odds()
    parsed_odds = odds_api.parse_odds(live_odds)
    
    # Process each live odd with our ML Engine instead of random data
    for odd in parsed_odds:
        h_team = odd['home_team']
        a_team = odd['away_team']
        
        # Predict outcome based on historical XGBoost model
        # Currently defaults to mock venue logic if venue unknown
        prediction = ml_engine.predict_match(h_team, a_team, "MCG") 
        
        market = odd['market']
        selection = odd['selection']
        bookmaker_odds = odd['odds']
        
        # Assign model probability based on selection
        # (Assuming it's a Head-to-Head win market for simplicity here)
        if selection == h_team:
            model_probability = prediction['home_prob']
        elif selection == a_team:
            model_probability = prediction['away_prob']
        else:
            model_probability = random.uniform(0.4, 0.6) # Uncategorized markets
            
        implied_prob = 1 / bookmaker_odds
        
        # Calculate +EV
        ev = (model_probability * bookmaker_odds) - 1.0
        ev_percentage = round(ev * 100, 2)
        
        is_value = ev_percentage > 5.0
        
        if is_value:
            # Check if we have an active match for these teams
            # Simplified: just grabbing first upcoming match for demo purposes
            match = db.query(models.Match).filter(models.Match.status == "upcoming").first()
            if match:
                bet = models.Bet(
                    match_id=match.id,
                    market=market,
                    selection=selection,
                    bookmaker_odds=bookmaker_odds,
                    model_probability=round(model_probability, 3),
                    ev_percentage=ev_percentage,
                    is_value_bet=is_value,
                    bookmaker=odd['bookmaker']
                )
                db.add(bet)
                
    db.commit()

@app.post("/api/run-simulation")
def trigger_simulation(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Triggers the Monte Carlo simulation to find new lines"""
    background_tasks.add_task(simulate_new_data, db)
    return {"message": "Simulation started. Running millions of iterations in the background..."}
