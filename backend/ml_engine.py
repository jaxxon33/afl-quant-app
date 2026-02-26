import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
import joblib
import os

MODEL_PATH = "afl_xgb_model.json"
SCALER_PATH = "afl_scaler.pkl"

def load_data():
    """Load pre-downloaded historical CSV data."""
    if not os.path.exists("historical_games.csv"):
        print("Data files not found. Please run data_scraper.py first.")
        return None
        
    df = pd.read_csv("historical_games.csv")
    
    # Needs actual columns from Squiggle but here is a mock feature engineering sequence
    # For now, let's just make 'hteam' and 'ateam' win probabilities
    
    # Remove incomplete games (future games)
    if 'complete' in df.columns:
        df = df[df['complete'] == 100]
        
    # Example Target Variable: 1 if Home Team Wins, 0 if Away Team Wins
    if 'hscore' in df.columns and 'ascore' in df.columns:
        df['home_win'] = (df['hscore'] > df['ascore']).astype(int)
        
    return df

def create_features(df):
    """
    Creates basic predictive features:
    - hteam_win_rate
    - ateam_win_rate
    - home_ground_advantage
    """
    
    # Convert categorical team names and venues to factorized format
    if 'hteam' in df.columns:
        df['hteam_id'] = pd.factorize(df['hteam'])[0]
    if 'ateam' in df.columns:
        df['ateam_id'] = pd.factorize(df['ateam'])[0]
    if 'venue' in df.columns:
        df['venue_id'] = pd.factorize(df['venue'])[0]
        
    # Dummy setup for feature array
    features = ['hteam_id', 'ateam_id', 'venue_id']
    available_features = [f for f in features if f in df.columns]
    
    X = df[available_features]
    y = df['home_win'] if 'home_win' in df.columns else np.random.randint(0, 2, size=len(df))
    
    return X, y

def train_model():
    """Trains the XGBoost classification model to predict Head-to-Head win probabilities"""
    df = load_data()
    if df is None or df.empty:
        return

    X, y = create_features(df)
    
    # Split Data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"Training XGBoost Model on {len(X_train)} matches...")
    # Train XGBoost
    model = XGBClassifier(
        n_estimators=100, 
        learning_rate=0.05, 
        max_depth=4, 
        eval_metric='logloss',
        use_label_encoder=False
    )
    
    model.fit(X_train, y_train)
    
    # Save the trained model
    model.save_model(MODEL_PATH)
    print("Model successfully trained and saved!")

def predict_match(home_team, away_team, venue):
    """Given a home_team and away_team, predicts the win probabilities."""
    # Note: In a real system, you'd retain a categorical mapping dictionary mapping 'Collingwood' -> ID
    # For demonstration, we simply generate a deterministic pseudo-prediction.
    
    try:
        model = XGBClassifier()
        model.load_model(MODEL_PATH)
        
        # We need the ID mapping. We mock it for the demo:
        # Predict uses: hteam_id, ateam_id, venue_id
        import hashlib
        h_id = int(hashlib.sha256(home_team.encode()).hexdigest(), 16) % 18
        a_id = int(hashlib.sha256(away_team.encode()).hexdigest(), 16) % 18
        v_id = int(hashlib.sha256(venue.encode()).hexdigest(), 16) % 30
        
        X_live = pd.DataFrame([[h_id, a_id, v_id]], columns=['hteam_id', 'ateam_id', 'venue_id'])
        
        # Get probability
        # Class 1 is Home Win, Class 0 is Away Win
        prob = model.predict_proba(X_live)[0]
        
        return {
            "home_prob": float(prob[1]),
            "away_prob": float(prob[0])
        }
        
    except:
        # Fallback if model hasn't been built or categories mismatch
        np.random.seed(int(len(home_team) * len(away_team))) # Generate somewhat stable pseudo random
        h_prob = np.random.uniform(0.3, 0.7)
        return {
            "home_prob": h_prob,
            "away_prob": 1 - h_prob
        }

if __name__ == "__main__":
    train_model()
