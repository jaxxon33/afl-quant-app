import datetime
import os

import requests

import afl_engine


ODDS_API_KEY = os.getenv("ODDS_API_KEY")
SPORT_KEY = os.getenv("ODDS_SPORT_KEY", "aussierules_afl")
REGIONS = os.getenv("ODDS_REGIONS", "au")
MARKETS = os.getenv("ODDS_MARKETS", "h2h,spreads,totals")
ODDS_FORMAT = os.getenv("ODDS_FORMAT", "decimal")
ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"


def fetch_live_odds():
    if not ODDS_API_KEY:
        return generate_demo_odds()

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
    }

    try:
        response = requests.get(ODDS_URL, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data if data else generate_demo_odds()

        print(f"Error fetching AFL odds: {response.status_code}")
        return generate_demo_odds()
    except Exception as exc:
        print(f"Connection error to Odds API: {exc}")
        return generate_demo_odds()


def parse_events(odds_data):
    events = []
    seen = set()

    for game in odds_data or []:
        home_team = afl_engine.normalize_team_name(game.get("home_team"))
        away_team = afl_engine.normalize_team_name(game.get("away_team"))
        if not home_team or not away_team:
            continue

        event_key = game.get("id") or f"{home_team}_{away_team}_{game.get('commence_time')}"
        if event_key in seen:
            continue
        seen.add(event_key)

        events.append(
            {
                "event_id": event_key,
                "home_team": home_team,
                "away_team": away_team,
                "venue": afl_engine.get_default_venue(home_team),
                "match_date": _parse_datetime(game.get("commence_time")),
            }
        )

    return events


def parse_odds(odds_data):
    standardized = []

    for game in odds_data or []:
        home_team = afl_engine.normalize_team_name(game.get("home_team"))
        away_team = afl_engine.normalize_team_name(game.get("away_team"))
        if not home_team or not away_team:
            continue

        for bookmaker in game.get("bookmakers", []):
            bookie_title = bookmaker.get("title") or bookmaker.get("key") or "Unknown"

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")
                if market_key not in {"h2h", "spreads", "totals"}:
                    continue

                for outcome in market.get("outcomes", []):
                    price = outcome.get("price")
                    if price is None:
                        continue

                    standardized.append(
                        {
                            "event_id": game.get("id"),
                            "home_team": home_team,
                            "away_team": away_team,
                            "bookmaker": bookie_title,
                            "market": market_key,
                            "selection": afl_engine.normalize_team_name(outcome.get("name")),
                            "odds": float(price),
                            "point": outcome.get("point"),
                            "commence_time": game.get("commence_time"),
                        }
                    )

    return standardized


def generate_demo_odds():
    fixtures = [
        ("Collingwood Magpies", "Carlton Blues", 1),
        ("Brisbane Lions", "Sydney Swans", 2),
        ("Adelaide Crows", "Port Adelaide Power", 3),
        ("Fremantle Dockers", "West Coast Eagles", 4),
    ]
    bookmakers = ["Sportsbet", "TAB", "Ladbrokes", "Betfair"]
    now = datetime.datetime.now(datetime.timezone.utc)
    events = []

    for home_team, away_team, days_ahead in fixtures:
        projection = afl_engine.predict_match(home_team, away_team)
        event = {
            "id": f"demo_{home_team}_{away_team}".replace(" ", "_").lower(),
            "sport_key": SPORT_KEY,
            "sport_title": "AFL",
            "commence_time": (now + datetime.timedelta(days=days_ahead)).isoformat().replace("+00:00", "Z"),
            "home_team": home_team,
            "away_team": away_team,
            "bookmakers": [],
        }

        for book_index, bookmaker in enumerate(bookmakers):
            event["bookmakers"].append(
                {
                    "key": bookmaker.lower().replace(" ", "_"),
                    "title": bookmaker,
                    "markets": [
                        _demo_h2h_market(projection, book_index),
                        _demo_spread_market(projection, book_index),
                        _demo_totals_market(projection, book_index),
                    ],
                }
            )

        events.append(event)

    return events


def _demo_h2h_market(projection, book_index):
    home_prob = _market_probability(projection["home_prob"], book_index, 0.012)
    away_prob = _market_probability(projection["away_prob"], book_index, -0.012)
    return {
        "key": "h2h",
        "outcomes": [
            {"name": projection["home_team"], "price": _probability_to_price(home_prob)},
            {"name": projection["away_team"], "price": _probability_to_price(away_prob)},
        ],
    }


def _demo_spread_market(projection, book_index):
    line = round((projection["expected_margin"] + (book_index - 1.5) * 1.5) * -2) / 2
    return {
        "key": "spreads",
        "outcomes": [
            {"name": projection["home_team"], "price": 1.91, "point": line},
            {"name": projection["away_team"], "price": 1.91, "point": -line},
        ],
    }


def _demo_totals_market(projection, book_index):
    total = round((projection["expected_total"] + (book_index - 1.5) * 2.0) * 2) / 2
    return {
        "key": "totals",
        "outcomes": [
            {"name": "Over", "price": 1.91, "point": total},
            {"name": "Under", "price": 1.91, "point": total},
        ],
    }


def _market_probability(probability, book_index, skew):
    margin = 1.035
    book_shift = (book_index - 1.5) * skew
    return min(0.95, max(0.05, probability * margin + book_shift))


def _probability_to_price(probability):
    return round(1 / probability, 2)


def _parse_datetime(value):
    if not value:
        return datetime.datetime.now(datetime.timezone.utc)

    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.datetime.now(datetime.timezone.utc)


if __name__ == "__main__":
    odds = fetch_live_odds()
    parsed = parse_odds(odds)
    print(f"Fetched {len(parsed)} AFL market lines.")
