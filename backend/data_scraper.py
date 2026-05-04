import csv

import afl_engine


def write_team_reference(path="afl_teams.csv"):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["team", "home_venue"])
        writer.writeheader()
        for team in afl_engine.list_afl_teams():
            writer.writerow({"team": team, "home_venue": afl_engine.get_default_venue(team)})

    print(f"Saved {path}")


def process_historical_data():
    print("No AFL historical scraper is bundled yet.")
    print("Use a licensed AFL data source for match results, weather, injuries, lineups, and player stats.")
    write_team_reference()


if __name__ == "__main__":
    process_historical_data()
