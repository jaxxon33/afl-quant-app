import hashlib
import math
import random


LEAGUE_AVG_TEAM_SCORE = 82.0
HOME_GROUND_ADVANTAGE_POINTS = 7.0
MARGIN_STD_DEV = 36.0
SCORE_STD_DEV = 24.0


TEAM_PROFILES = {
    "Adelaide Crows": {"rating": 1515, "attack": 4.0, "defence": -1.0, "venue": "Adelaide Oval"},
    "Brisbane Lions": {"rating": 1625, "attack": 8.0, "defence": 4.0, "venue": "Gabba"},
    "Carlton Blues": {"rating": 1530, "attack": 3.0, "defence": 1.0, "venue": "MCG"},
    "Collingwood Magpies": {"rating": 1565, "attack": 4.0, "defence": 2.0, "venue": "MCG"},
    "Essendon Bombers": {"rating": 1490, "attack": 0.0, "defence": -1.0, "venue": "Marvel Stadium"},
    "Fremantle Dockers": {"rating": 1525, "attack": 1.0, "defence": 4.0, "venue": "Optus Stadium"},
    "Geelong Cats": {"rating": 1585, "attack": 5.0, "defence": 4.0, "venue": "GMHBA Stadium"},
    "Gold Coast Suns": {"rating": 1510, "attack": 2.0, "defence": 1.0, "venue": "People First Stadium"},
    "Greater Western Sydney Giants": {"rating": 1575, "attack": 6.0, "defence": 2.0, "venue": "ENGIE Stadium"},
    "Hawthorn Hawks": {"rating": 1545, "attack": 5.0, "defence": 0.0, "venue": "MCG"},
    "Melbourne Demons": {"rating": 1505, "attack": -1.0, "defence": 3.0, "venue": "MCG"},
    "North Melbourne Kangaroos": {"rating": 1445, "attack": -4.0, "defence": -4.0, "venue": "Marvel Stadium"},
    "Port Adelaide Power": {"rating": 1550, "attack": 4.0, "defence": 1.0, "venue": "Adelaide Oval"},
    "Richmond Tigers": {"rating": 1455, "attack": -3.0, "defence": -3.0, "venue": "MCG"},
    "St Kilda Saints": {"rating": 1485, "attack": -2.0, "defence": 2.0, "venue": "Marvel Stadium"},
    "Sydney Swans": {"rating": 1600, "attack": 7.0, "defence": 3.0, "venue": "SCG"},
    "West Coast Eagles": {"rating": 1435, "attack": -5.0, "defence": -5.0, "venue": "Optus Stadium"},
    "Western Bulldogs": {"rating": 1535, "attack": 3.0, "defence": 0.0, "venue": "Marvel Stadium"},
}


TEAM_ALIASES = {
    "Adelaide": "Adelaide Crows",
    "Brisbane": "Brisbane Lions",
    "Carlton": "Carlton Blues",
    "Collingwood": "Collingwood Magpies",
    "Essendon": "Essendon Bombers",
    "Fremantle": "Fremantle Dockers",
    "Geelong": "Geelong Cats",
    "Gold Coast": "Gold Coast Suns",
    "GWS Giants": "Greater Western Sydney Giants",
    "Greater Western Sydney": "Greater Western Sydney Giants",
    "Hawthorn": "Hawthorn Hawks",
    "Melbourne": "Melbourne Demons",
    "North Melbourne": "North Melbourne Kangaroos",
    "Port Adelaide": "Port Adelaide Power",
    "Richmond": "Richmond Tigers",
    "St Kilda": "St Kilda Saints",
    "Sydney": "Sydney Swans",
    "West Coast": "West Coast Eagles",
    "Western Bulldogs": "Western Bulldogs",
}


def normalize_team_name(team_name):
    cleaned = " ".join(str(team_name or "").strip().split())
    return TEAM_ALIASES.get(cleaned, cleaned)


def is_afl_team(team_name):
    return normalize_team_name(team_name) in TEAM_PROFILES


def list_afl_teams():
    return sorted(TEAM_PROFILES.keys())


def get_default_venue(home_team):
    team = normalize_team_name(home_team)
    return TEAM_PROFILES.get(team, {}).get("venue", "TBA")


def _profile(team_name):
    team = normalize_team_name(team_name)
    return TEAM_PROFILES.get(team, {"rating": 1500, "attack": 0.0, "defence": 0.0, "venue": "TBA"})


def _normal_cdf(value):
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _clamp(value, low, high):
    return max(low, min(high, value))


def predict_match(home_team, away_team, venue=None, weather_total_adjustment=0.0, home_lineup_adjustment=0.0, away_lineup_adjustment=0.0):
    home = normalize_team_name(home_team)
    away = normalize_team_name(away_team)
    home_profile = _profile(home)
    away_profile = _profile(away)

    rating_margin = (home_profile["rating"] - away_profile["rating"]) / 28.0
    expected_margin = (
        rating_margin
        + HOME_GROUND_ADVANTAGE_POINTS
        + home_lineup_adjustment
        - away_lineup_adjustment
    )

    expected_home_score = (
        LEAGUE_AVG_TEAM_SCORE
        + home_profile["attack"]
        - away_profile["defence"]
        + expected_margin / 2.0
        + weather_total_adjustment / 2.0
    )
    expected_away_score = (
        LEAGUE_AVG_TEAM_SCORE
        + away_profile["attack"]
        - home_profile["defence"]
        - expected_margin / 2.0
        + weather_total_adjustment / 2.0
    )

    expected_home_score = max(35.0, expected_home_score)
    expected_away_score = max(35.0, expected_away_score)
    expected_total = expected_home_score + expected_away_score
    home_prob = _clamp(_normal_cdf(expected_margin / MARGIN_STD_DEV), 0.05, 0.95)

    return {
        "home_team": home,
        "away_team": away,
        "venue": venue or get_default_venue(home),
        "home_prob": home_prob,
        "away_prob": 1.0 - home_prob,
        "expected_home_score": expected_home_score,
        "expected_away_score": expected_away_score,
        "expected_margin": expected_margin,
        "expected_total": expected_total,
    }


def run_monte_carlo_simulation(home_team, away_team, venue=None, num_simulations=20000):
    projection = predict_match(home_team, away_team, venue)
    seed_key = f"{projection['home_team']}|{projection['away_team']}|{projection['venue']}"
    seed = int(hashlib.sha256(seed_key.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)

    home_wins = 0
    total_points_list = []
    home_margins = []

    for _ in range(num_simulations):
        home_score = max(0.0, rng.gauss(projection["expected_home_score"], SCORE_STD_DEV))
        away_score = max(0.0, rng.gauss(projection["expected_away_score"], SCORE_STD_DEV))
        home_margin = home_score - away_score

        if home_margin > 0:
            home_wins += 1

        total_points_list.append(home_score + away_score)
        home_margins.append(home_margin)

    mc_home_prob = home_wins / num_simulations

    return {
        **projection,
        "mc_home_prob": mc_home_prob,
        "mc_away_prob": 1.0 - mc_home_prob,
        "total_points_list": total_points_list,
        "home_margins": home_margins,
        "num_simulations": num_simulations,
    }


def calculate_ev(model_probability, decimal_odds):
    if not decimal_odds or decimal_odds <= 1:
        return None
    return (model_probability * decimal_odds) - 1.0
