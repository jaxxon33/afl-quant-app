import requests
import pandas as pd
from datetime import datetime
import time
import os
import sys

SQUIGGLE_API_URL = "https://api.squiggle.com.au/"
USER_AGENT_HEADER = {'User-Agent': "Paul's AFL Quant App Bot - paul@example.com"}

def fetch_historical_matches(years_str="2023,2024,2025"):
    """Fetches historical match results in one request to reduce API load."""
    print(f"Fetching matches for years {years_str}...")
    params = {"q": "games", "year": years_str}
    
    # 1 & 5. Respectful User-Agent and Error Handling
    response = requests.get(SQUIGGLE_API_URL, params=params, headers=USER_AGENT_HEADER)
    
    if response.status_code == 200:
        games = response.json().get("games", [])
        print(f"Successfully fetched {len(games)} games from Squiggle API.")
    else:
        print(f"Error: Squiggle API returned status code {response.status_code}.")
        print("Stopping further requests to avoid overloading the API.")
        return pd.DataFrame() # Back off entirely
        
    df = pd.DataFrame(games)
    if not df.empty:
        cols = ['id', 'date', 'round', 'hteam', 'ateam', 'hscore', 'ascore', 'venue', 'winner', 'complete']
        available_cols = [c for c in cols if c in df.columns]
        df = df[available_cols]
        if 'hscore' in df.columns and 'ascore' in df.columns:
            df['margin'] = df['hscore'].fillna(0) - df['ascore'].fillna(0)
            
    return df

def fetch_teams():
    print(f"Fetching team data...")
    params = {"q": "teams"}
    response = requests.get(SQUIGGLE_API_URL, params=params, headers=USER_AGENT_HEADER)
    
    if response.status_code == 200:
        teams = response.json().get("teams", [])
        print(f"Successfully fetched {len(teams)} teams.")
        return pd.DataFrame(teams)
    else:
        print(f"Error fetching teams: {response.status_code}")
        return pd.DataFrame()

def process_historical_data(force_refresh=False):
    """Main pipeline for scraping and saving clean historical data"""
    # 2. Cache and Re-use data. Only fetch if missing or explicitly asked.
    if not force_refresh and os.path.exists("historical_games.csv") and os.path.exists("historical_teams.csv"):
        print("Data files already exist locally (Cached). Skipping API requests to abide by Squiggle Bot rules.")
        print("Run with '--force' to bypass cache and re-download data.")
        return pd.read_csv("historical_games.csv")
    
    print("Initiating historical data dump...")
    
    # 3 & 4. Fetch all needed years at once instead of looping request per year
    games_df = fetch_historical_matches(years_str="2023,2024,2025")
    
    # Sleep to be extra safe and nice between requests
    time.sleep(2)
    teams_df = fetch_teams()
    
    if not games_df.empty:
        games_df.to_csv("historical_games.csv", index=False)
        print("Saved historical_games.csv")
        
    if not teams_df.empty:
        teams_df.to_csv("historical_teams.csv", index=False)
        print("Saved historical_teams.csv")
        
    return games_df

if __name__ == "__main__":
    force = "--force" in sys.argv
    process_historical_data(force_refresh=force)
