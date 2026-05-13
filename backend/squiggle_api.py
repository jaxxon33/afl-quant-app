import requests
import afl_engine

SQUIGGLE_BASE = "https://api.squiggle.com.au/"
_HEADERS = {"User-Agent": "AFL-Quant-App/1.0 (paul@x.net.au)"}


def fetch_completed_games(year=2026):
    """Return completed AFL game results for the given year, for Elo updates."""
    try:
        response = requests.get(
            SQUIGGLE_BASE,
            params={"q": "games", "year": year, "complete": 100},
            headers=_HEADERS,
            timeout=10,
        )
        if response.status_code != 200:
            print(f"Squiggle API error: {response.status_code}")
            return []

        results = []
        for g in response.json().get("games", []):
            if g.get("complete", 0) < 100:
                continue
            home = afl_engine.normalize_team_name(g.get("hteam", ""))
            away = afl_engine.normalize_team_name(g.get("ateam", ""))
            if not afl_engine.is_afl_team(home) or not afl_engine.is_afl_team(away):
                continue
            home_score = g.get("hscore")
            away_score = g.get("ascore")
            if home_score is None or away_score is None:
                continue
            results.append({
                "home_team": home,
                "away_team": away,
                "home_score": int(home_score),
                "away_score": int(away_score),
            })
        return results

    except Exception as exc:
        print(f"Squiggle fetch error: {exc}")
        return []
