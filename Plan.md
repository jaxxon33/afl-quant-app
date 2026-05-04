# AFL +EV Betting Model - Implementation Plan

This document tracks the AFL betting model described in `Jackson.md`.

## Phase 1: AFL Data Infrastructure

- Store teams, venues, matches, bookmaker odds, model projections, and recommended bets.
- Add licensed AFL historical data for the last three seasons.
- Include weather, venue, home ground, injuries, lineups, team form, and player availability.

## Phase 2: AFL Modeling

- Build separate probability models for head-to-head, line, totals, and player props.
- Backtest each model against historical market prices and closing lines.
- Calibrate probabilities so reported edges are not overstated.

## Phase 3: Simulation

- Run large AFL-specific simulations from expected scores, margin variance, player availability, and weather.
- Store auditable projection outputs for each market.
- Expose projections through the API for the frontend.

## Phase 4: Odds Integration

- Use The Odds API AFL sport key `aussierules_afl` for featured markets.
- Pull AU bookmaker prices from Sportsbet, TAB, Ladbrokes, Betfair, and other available books.
- Add event-level player prop markets when the data plan supports them.

## Phase 5: Expected Value

- Compare model probability to bookmaker implied probability.
- Store EV only when the edge clears the configured threshold.
- Track bookmaker, market, selection, decimal odds, model probability, implied probability, and timestamp.

## Phase 6: Product

- Dashboard: current AFL +EV feed and summary stats.
- Match view: upcoming fixtures, model win probabilities, projected score, line, and total.
- Settings: EV threshold, bankroll, and staking controls connected to backend config.

## Phase 7: Deployment

- Frontend: GitHub Pages under `https://jaxxon33.github.io/afl-quant-app/`.
- Backend: Render or equivalent FastAPI host.
- Database: managed PostgreSQL.
- Worker: scheduled odds refresh and simulation jobs.
