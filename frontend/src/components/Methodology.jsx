import { useState, useEffect } from 'react'
import { BookOpen, Calculator, MapPin, TrendingUp, Database, RefreshCw } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export default function Methodology() {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)

    const fetchData = async () => {
        try {
            const res = await fetch(`${API_BASE}/methodology`)
            const json = await res.json()
            setData(json)
        } catch (e) {
            console.error("Methodology fetch error", e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchData() }, [])

    const refreshElo = async () => {
        setRefreshing(true)
        try {
            await fetch(`${API_BASE}/refresh-elo`, { method: 'POST' })
            setTimeout(() => { fetchData(); setRefreshing(false) }, 3000)
        } catch (e) {
            console.error("Elo refresh failed", e)
            setRefreshing(false)
        }
    }

    if (loading || !data) {
        return (
            <div className="loader-container">
                <div className="loader-circle"></div>
                <p>Loading Methodology...</p>
            </div>
        )
    }

    const p = data.model_parameters
    const venues = Object.entries(data.venue_adjustments).sort((a, b) => b[1] - a[1])

    return (
        <div>
            <div className="header-actions" style={{ marginBottom: "2rem" }}>
                <div>
                    <h1>Model <span className="neon-cyan-text">Methodology</span></h1>
                    <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
                        Full transparency on how AFL Quant calculates probabilities, edges, and stakes.
                    </p>
                </div>
                <button className="btn btn-primary" onClick={refreshElo} disabled={refreshing}>
                    {refreshing ? <><span className="spinner"></span> Refreshing...</> : <><RefreshCw size={16} /> Refresh Elo from Squiggle</>}
                </button>
            </div>

            {/* Pipeline overview */}
            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <BookOpen size={20} className="neon-cyan-text" /> How a +EV Bet is Identified
                </h3>
                <ol style={{ lineHeight: 1.8, color: 'var(--text-secondary)', paddingLeft: '1.25rem' }}>
                    <li><strong style={{ color: 'var(--text-primary)' }}>Live odds</strong> are fetched from {data.data_sources.odds} for AFL h2h, line and totals markets.</li>
                    <li><strong style={{ color: 'var(--text-primary)' }}>Elo ratings</strong> are built on startup from completed 2026 results via {data.data_sources.results}.</li>
                    <li>For each match, <strong style={{ color: 'var(--text-primary)' }}>expected margin</strong> = (home_elo − away_elo) / 28 + {p.home_ground_advantage_points} HGA.</li>
                    <li><strong style={{ color: 'var(--text-primary)' }}>Win probability</strong> = Normal CDF(expected_margin / {p.margin_std_dev}), clamped to [5%, 95%].</li>
                    <li>A <strong style={{ color: 'var(--text-primary)' }}>Monte Carlo</strong> with {p.simulation_count.toLocaleString()} simulations samples scores ~ N(expected_score, {p.score_std_dev}) per team to derive line and totals probabilities.</li>
                    <li><strong style={{ color: 'var(--text-primary)' }}>Market consensus</strong> = average of bookmaker implied probabilities with margin stripped (1/odds normalised so they sum to 1).</li>
                    <li>Model probability is <strong style={{ color: 'var(--text-primary)' }}>calibrated</strong> to consensus with edge capped at ±{(p.max_market_edge * 100).toFixed(1)}%.</li>
                    <li><strong style={{ color: 'var(--text-primary)' }}>EV = (model_prob × decimal_odds) − 1</strong>. Bets exceeding {p.min_ev_threshold_pct}% are flagged.</li>
                    <li><strong style={{ color: 'var(--text-primary)' }}>Kelly stake</strong> = ((b·p − q) / b) × {p.kelly_fraction_default} fraction, where b = odds − 1.</li>
                </ol>
            </div>

            {/* Model Parameters */}
            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Calculator size={20} className="neon-cyan-text" /> Model Parameters
                </h3>
                <div className="param-grid">
                    <div className="param-card"><span>League avg team score</span><strong>{p.league_avg_team_score}</strong></div>
                    <div className="param-card"><span>Home ground advantage</span><strong>+{p.home_ground_advantage_points} pts</strong></div>
                    <div className="param-card"><span>Margin std deviation</span><strong>{p.margin_std_dev}</strong></div>
                    <div className="param-card"><span>Score std deviation</span><strong>{p.score_std_dev}</strong></div>
                    <div className="param-card"><span>Elo K-factor</span><strong>{p.elo_k_factor}</strong></div>
                    <div className="param-card"><span>Elo HGA boost</span><strong>{p.elo_home_advantage}</strong></div>
                    <div className="param-card"><span>MC simulations</span><strong>{p.simulation_count.toLocaleString()}</strong></div>
                    <div className="param-card"><span>Min EV threshold</span><strong>{p.min_ev_threshold_pct}%</strong></div>
                    <div className="param-card"><span>Max model edge over market</span><strong>{(p.max_market_edge * 100).toFixed(1)}%</strong></div>
                    <div className="param-card"><span>Kelly fraction default</span><strong>{p.kelly_fraction_default}x</strong></div>
                </div>
            </div>

            {/* Team Ratings Ladder */}
            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <TrendingUp size={20} className="neon-cyan-text" /> Live Elo Ratings (current vs base)
                </h3>
                <div className="rating-table">
                    <div className="rating-header">
                        <span>#</span>
                        <span>Team</span>
                        <span style={{ textAlign: 'right' }}>Base</span>
                        <span style={{ textAlign: 'right' }}>Current</span>
                        <span style={{ textAlign: 'right' }}>Δ</span>
                        <span style={{ textAlign: 'right' }}>Atk / Def</span>
                    </div>
                    {data.teams.map((t, idx) => {
                        const positive = t.rating_delta >= 0
                        return (
                            <div key={t.team} className="rating-row">
                                <span style={{ color: 'var(--text-secondary)' }}>{idx + 1}</span>
                                <span>{t.team}</span>
                                <span style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{t.base_rating}</span>
                                <span style={{ textAlign: 'right', fontWeight: 600 }}>{t.current_rating}</span>
                                <span style={{ textAlign: 'right', color: positive ? 'var(--accent-primary)' : 'var(--accent-danger)' }}>
                                    {positive ? '+' : ''}{t.rating_delta}
                                </span>
                                <span style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>
                                    {t.attack >= 0 ? '+' : ''}{t.attack} / {t.defence >= 0 ? '+' : ''}{t.defence}
                                </span>
                            </div>
                        )
                    })}
                </div>
            </div>

            {/* Venue Adjustments */}
            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <MapPin size={20} className="neon-cyan-text" /> Venue Scoring Adjustments
                </h3>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.9rem' }}>
                    Points added to expected total at each ground (relative to league average).
                </p>
                <div className="venue-grid">
                    {venues.map(([venue, adj]) => (
                        <div key={venue} className="param-card">
                            <span>{venue}</span>
                            <strong style={{ color: adj > 0 ? 'var(--accent-primary)' : adj < 0 ? 'var(--accent-danger)' : 'var(--text-primary)' }}>
                                {adj > 0 ? '+' : ''}{adj}
                            </strong>
                        </div>
                    ))}
                </div>
            </div>

            {/* Data Sources */}
            <div className="glass-card">
                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Database size={20} className="neon-cyan-text" /> Data Sources
                </h3>
                <ul style={{ color: 'var(--text-secondary)', lineHeight: 1.8, paddingLeft: '1.25rem' }}>
                    <li><strong style={{ color: 'var(--text-primary)' }}>Odds:</strong> {data.data_sources.odds}</li>
                    <li><strong style={{ color: 'var(--text-primary)' }}>Results:</strong> {data.data_sources.results}</li>
                </ul>
            </div>
        </div>
    )
}
