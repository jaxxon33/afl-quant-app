import { useState, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

function getSettings() {
    return {
        bankroll: Number(localStorage.getItem('bankroll') ?? '1000'),
        kellyMultiplier: parseFloat(localStorage.getItem('kellyMultiplier') ?? '0.5'),
    }
}

export default function Dashboard() {
    const [stats, setStats] = useState({ total_ev_bets: 0, avg_ev_percentage: 0.0, total_matches_upcoming: 0 })
    const [evBets, setEvBets] = useState([])
    const [loading, setLoading] = useState(true)
    const [simulating, setSimulating] = useState(false)
    const [sortBy, setSortBy] = useState('ev_desc')
    const [settings, setSettings] = useState(getSettings)

    const fetchData = async () => {
        try {
            const statsRes = await fetch(`${API_BASE}/stats`)
            const statsData = await statsRes.json()
            setStats(statsData)

            const betsRes = await fetch(`${API_BASE}/bets/ev`)
            const betsData = await betsRes.json()
            setEvBets(betsData)
        } catch (e) {
            console.error("Error fetching data", e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, 10000)
        // Re-read settings on focus in case user changed them in Settings tab
        const onFocus = () => setSettings(getSettings())
        window.addEventListener('focus', onFocus)
        return () => { clearInterval(interval); window.removeEventListener('focus', onFocus) }
    }, [])

    const runSimulation = async () => {
        setSimulating(true)
        try {
            await fetch(`${API_BASE}/run-simulation`, { method: 'POST' })
            setTimeout(() => {
                fetchData()
                setSimulating(false)
            }, 2000)
        } catch (e) {
            console.error("Simulation failed", e)
            setSimulating(false)
        }
    }

    if (loading) {
        return (
            <div className="loader-container">
                <div className="loader-circle"></div>
                <p>Loading Quant Engine...</p>
            </div>
        )
    }

    const sortedBets = [...evBets].sort((a, b) => {
        if (sortBy === 'ev_desc') return b.ev_percentage - a.ev_percentage
        if (sortBy === 'odds_desc') return b.bookmaker_odds - a.bookmaker_odds
        if (sortBy === 'prob_desc') return b.model_probability - a.model_probability
        return 0
    })

    return (
        <div>
            <div className="header-actions">
                <div>
                    <h1>+EV Identification <span className="neon-cyan-text">Live Feed</span></h1>
                    <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
                        Model tracking AFL head-to-head, line, and totals prices across Australian bookies.
                    </p>
                </div>
                <button
                    className="btn btn-primary"
                    onClick={runSimulation}
                    disabled={simulating}
                >
                    {simulating ? (
                        <><span className="spinner"></span> Running Monte Carlo...</>
                    ) : (
                            'Run AFL Simulation'
                    )}
                </button>
            </div>

            <div className="stats-grid">
                <div className="glass-card">
                    <div className="stat-label">Identified Value Bets</div>
                    <div className="stat-value neon-cyan-text">{stats.total_ev_bets}</div>
                </div>
                <div className="glass-card">
                    <div className="stat-label">Average +EV Yield</div>
                    <div className="stat-value gradient-text">+{stats.avg_ev_percentage}%</div>
                </div>
                <div className="glass-card">
                    <div className="stat-label">Upcoming AFL Matches</div>
                    <div className="stat-value mono-text">{stats.total_matches_upcoming}</div>
                </div>
            </div>

            <div className="glass-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: "1.5rem" }}>
                    <h3>Live AFL +EV Bets</h3>
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                        style={{
                            background: 'var(--bg-tertiary)',
                            color: 'var(--text-primary)',
                            border: '1px solid var(--border-color)',
                            padding: '0.4rem 0.8rem',
                            borderRadius: '8px',
                            outline: 'none',
                            cursor: 'pointer'
                        }}
                    >
                        <option value="ev_desc">Highest +EV First</option>
                        <option value="prob_desc">Highest Probability</option>
                        <option value="odds_desc">Highest Odds</option>
                    </select>
                </div>

                <div className="ev-list">
                    {sortedBets.length === 0 ? (
                        <p style={{ color: "var(--text-secondary)" }}>No +EV bets currently identified above the threshold.</p>
                    ) : (
                        sortedBets.map((bet) => {
                            const bookImplied = 1 / bet.bookmaker_odds
                            const consensusProb = bet.consensus_probability
                            // Off-market: this book is pricing notably cheaper than market consensus
                            const offMarket = consensusProb != null && (consensusProb - bookImplied) > 0.03

                            const kellyStake = bet.kelly_fraction != null
                                ? (settings.bankroll * bet.kelly_fraction * settings.kellyMultiplier)
                                : null

                            return (
                            <div key={bet.id} className="ev-card">
                                <div className="ev-match-info">
                                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                                        {bet.home_team} vs {bet.away_team} &middot; {new Date(bet.match_date?.split('.')[0]).toLocaleDateString()}
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <div className="ev-market">{bet.market}</div>
                                        {offMarket && (
                                            <span style={{
                                                fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px',
                                                background: 'rgba(0,255,163,0.15)', color: 'var(--accent-primary)',
                                                border: '1px solid var(--accent-primary)', fontWeight: 600,
                                            }}>OFF MARKET</span>
                                        )}
                                    </div>
                                    <div className="ev-match-title">{bet.selection}</div>
                                    <div className="ev-selection">
                                        Model: {(bet.model_probability * 100).toFixed(1)}%
                                        {consensusProb != null && <> &middot; Market: {(consensusProb * 100).toFixed(1)}%</>}
                                        &nbsp;&middot; Book: {(bookImplied * 100).toFixed(1)}%
                                    </div>
                                    {kellyStake != null && (
                                        <div style={{ fontSize: '0.8rem', color: '#8884d8', marginTop: '4px' }}>
                                            Kelly stake: ${kellyStake.toFixed(2)}
                                            <span style={{ color: 'var(--text-secondary)', marginLeft: '4px' }}>
                                                ({(settings.kellyMultiplier * 100).toFixed(0)}% Kelly)
                                            </span>
                                        </div>
                                    )}
                                </div>

                                <div className="ev-odds-col">
                                    <div className="ev-odds">{bet.bookmaker_odds.toFixed(2)}</div>
                                    <div className="ev-bookie">{bet.bookmaker}</div>
                                </div>

                                <div className="ev-percentage">
                                    +{bet.ev_percentage}%
                                </div>
                            </div>
                            )
                        })
                    )}
                </div>
            </div>
        </div>
    )
}
