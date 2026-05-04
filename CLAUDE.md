# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

A full-stack quantitative betting analysis app for AFL matches. The app compares AFL model probabilities against Australian bookmaker odds to identify possible positive expected value bets.

`Jackson.md` is the product brief. It calls for AFL markets across head-to-head, lines, totals, and player props with weather, venue, injuries, lineups, and bookmaker feeds. The current implementation supports AFL head-to-head, line, and totals markets. Player props and real injury/lineup/weather feeds still need licensed data sources before they should be shown.

## Development Commands

### Frontend
```bash
cd frontend
npm run dev
npm run build
npm run lint
npm run deploy
```

### Backend
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
python data_scraper.py
python test_bets.py
python clear_db.py
```

## Architecture

### Data Flow
1. On startup, `seed_database()` removes stale non-AFL match rows and seeds upcoming AFL matches from the odds feed.
2. `odds_api.py` calls The Odds API with sport key `aussierules_afl`, AU region, and featured markets `h2h,spreads,totals`.
3. If no API key or no current odds are available, `odds_api.py` returns deterministic AFL demo fixtures and prices.
4. `afl_engine.py` creates deterministic AFL team projections from team ratings, home ground advantage, expected scoring, and Monte Carlo simulation.
5. `simulate_new_data()` compares model probabilities to decimal bookmaker odds and stores only bets above `MIN_EV_THRESHOLD`.
6. The frontend polls `/api/stats` and `/api/bets/ev`, and fetches match projections from `/api/matches/{id}/projection`.

## Key Files

- `backend/main.py` - FastAPI app, routes, match seeding, simulation trigger
- `backend/afl_engine.py` - AFL ratings, projections, simulation, EV helper
- `backend/odds_api.py` - AFL odds ingestion and deterministic demo fallback
- `backend/models.py` - SQLAlchemy `Match` and `Bet` entities
- `backend/schemas.py` - Pydantic response schemas
- `backend/database.py` - DB connection
- `frontend/src/App.jsx` - App shell and tabs
- `frontend/src/components/Dashboard.jsx` - +EV feed and stats
- `frontend/src/components/Matches.jsx` - AFL fixture and projection view
- `frontend/src/components/Settings.jsx` - Local settings UI

## Deployment

- Frontend: configured for GitHub Pages with Vite base path `/afl-quant-app/`
- Backend: Render-compatible `Procfile`
- Database: PostgreSQL via `DATABASE_URL`, with local SQLite fallback

## Environment Variables

### Backend
```bash
DATABASE_URL=postgresql://...
ODDS_API_KEY=...
ODDS_SPORT_KEY=aussierules_afl
ODDS_REGIONS=au
ODDS_MARKETS=h2h,spreads,totals
MIN_EV_THRESHOLD=5.0
SIMULATION_COUNT=20000
FRONTEND_ORIGIN=https://jaxxon33.github.io
```

### Frontend
```bash
VITE_API_URL=https://afl-quant-app.onrender.com/api
```

## Known Limitations

- Team ratings are deterministic seed ratings, not a trained model.
- Real AFL injuries, lineups, weather, player props, and historical closing-line data are not wired in yet.
- Demo odds are only a fallback so the UI can run without an API key.
- Background jobs use FastAPI `BackgroundTasks`; use a worker/queue before production load.
