import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Activity, Clock, Target, Layers, TrendingUp, ChevronDown, ChevronRight } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

function pct(v) { return v != null ? (v * 100).toFixed(1) + '%' : '—' }
function num(v, d = 1) { return v != null ? Number(v).toFixed(d) : '—' }
function signed(v, d = 1) { if (v == null) return '—'; const n = Number(v); return (n >= 0 ? '+' : '') + n.toFixed(d) }

export default function Matches() {
    const [matches, setMatches] = useState([])
    const [selectedMatch, setSelectedMatch] = useState(null)
    const [context, setContext] = useState(null)
    const [contextLoading, setContextLoading] = useState(false)
    const [loading, setLoading] = useState(true)
    const [showMath, setShowMath] = useState(false)
    const [marketTab, setMarketTab] = useState('h2h')

    useEffect(() => {
        const fetchMatches = async () => {
            try {
                const res = await fetch(`${API_BASE}/matches`)
                const data = await res.json()
                setMatches(data)
                if (data.length > 0) setSelectedMatch(data[0])
            } catch (e) {
                console.error("Error fetching matches", e)
            } finally {
                setLoading(false)
            }
        }
        fetchMatches()
    }, [])

    useEffect(() => {
        if (!selectedMatch) return
        const fetchContext = async () => {
            setContextLoading(true)
            try {
                const res = await fetch(`${API_BASE}/matches/${selectedMatch.id}/context`)
                if (!res.ok) {
                    // Backend hasn't deployed v2.1 yet — fall back to the projection-only endpoint.
                    const fallback = await fetch(`${API_BASE}/matches/${selectedMatch.id}/projection`)
                    if (fallback.ok) {
                        const proj = await fallback.json()
                        setContext({ __legacy: true, projection: proj })
                    } else {
                        setContext(null)
                    }
                    return
                }
                const data = await res.json()
                if (data && data.calculation && data.probabilities) {
                    setContext(data)
                } else {
                    setContext(null)
                }
            } catch (e) {
                console.error("Error fetching context", e)
                setContext(null)
            } finally {
                setContextLoading(false)
            }
        }
        fetchContext()
    }, [selectedMatch])

    if (loading) {
        return (
            <div className="loader-container">
                <div className="loader-circle"></div>
                <p>Loading Matches...</p>
            </div>
        )
    }

    const scoreData = context ? [
        { team: context.home_team, score: context.calculation.expected_home_score },
        { team: context.away_team, score: context.calculation.expected_away_score }
    ] : []

    const marketRows = context ? (context.markets[marketTab] || []) : []
    const consensusForMarket = context ? context.consensus.filter(c => c.market === marketTab) : []

    return (
        <div className="matches-page">
            <div className="header-actions" style={{ marginBottom: "2rem" }}>
                <div>
                    <h1>AFL Matches <span className="neon-cyan-text">& Full Breakdown</span></h1>
                    <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
                        Every probability with its inputs exposed. Click a match to see how every number was calculated.
                    </p>
                </div>
            </div>

            <div className="layout-grid">
                {/* Match list */}
                <div className="matches-list glass-card">
                    <h3 style={{ marginBottom: "1rem" }}>
                        <Clock size={18} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'middle' }} /> Upcoming Matches
                    </h3>
                    <div className="matches-scroll">
                        {matches.length === 0 ? (
                            <p>No upcoming matches found.</p>
                        ) : matches.map(match => (
                            <div
                                key={match.id}
                                className={`match-item ${selectedMatch && selectedMatch.id === match.id ? 'active' : ''}`}
                                onClick={() => setSelectedMatch(match)}
                            >
                                <div className="match-teams">
                                    <span className="team">{match.home_team}</span>
                                    <span className="vs">vs</span>
                                    <span className="team">{match.away_team}</span>
                                </div>
                                <div className="match-venue">
                                    {new Date(match.match_date?.split('.')[0]).toLocaleDateString()} &middot; {match.venue}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Detail column */}
                <div className="match-details">
                    {!selectedMatch ? (
                        <div className="glass-card empty-state">
                            <p>Select a match to view data.</p>
                        </div>
                    ) : contextLoading || !context ? (
                        <div className="glass-card"><p style={{ color: "var(--text-secondary)" }}>Loading match context...</p></div>
                    ) : context.__legacy ? (
                        <div className="glass-card">
                            <h2>{selectedMatch.home_team} <span style={{ color: "var(--text-secondary)" }}>vs</span> {selectedMatch.away_team}</h2>
                            <p style={{ color: "var(--text-secondary)", marginBottom: "1.5rem" }}>
                                {new Date(selectedMatch.match_date?.split('.')[0]).toLocaleString()} &middot; {selectedMatch.venue}
                            </p>
                            <div className="projection-grid" style={{ marginBottom: '1.5rem' }}>
                                <div className="projection-card">
                                    <span>{context.projection.home_team}</span>
                                    <strong>{(context.projection.home_win_probability * 100).toFixed(1)}%</strong>
                                </div>
                                <div className="projection-card">
                                    <span>{context.projection.away_team}</span>
                                    <strong>{(context.projection.away_win_probability * 100).toFixed(1)}%</strong>
                                </div>
                            </div>
                            <div className="param-grid">
                                <div className="param-card"><span>Expected margin</span><strong>{signed(context.projection.expected_margin)}</strong></div>
                                <div className="param-card"><span>Expected total</span><strong>{num(context.projection.expected_total)}</strong></div>
                                <div className="param-card"><span>Home expected</span><strong>{num(context.projection.expected_home_score)}</strong></div>
                                <div className="param-card"><span>Away expected</span><strong>{num(context.projection.expected_away_score)}</strong></div>
                            </div>
                            <p style={{ color: 'var(--accent-danger)', marginTop: '1rem', fontSize: '0.85rem' }}>
                                Full breakdown unavailable — backend is on a pre-v2.1 build. Manual redeploy of the Render service required.
                            </p>
                        </div>
                    ) : (
                        <>
                            {/* Header */}
                            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                                <h2>{context.home_team} <span style={{ color: "var(--text-secondary)" }}>vs</span> {context.away_team}</h2>
                                <p style={{ color: "var(--text-secondary)", marginBottom: "1.5rem" }}>
                                    {new Date(context.match_date?.split('.')[0]).toLocaleString()} &middot; {context.venue}
                                </p>

                                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Activity size={20} className="neon-cyan-text" /> Model Win Probability
                                </h3>
                                <div className="projection-grid">
                                    <div className="projection-card">
                                        <span>{context.home_team}</span>
                                        <strong>{pct(context.probabilities.home_win_mc)}</strong>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                                            (Analytical: {pct(context.probabilities.home_win_analytical)})
                                        </div>
                                    </div>
                                    <div className="projection-card">
                                        <span>{context.away_team}</span>
                                        <strong>{pct(context.probabilities.away_win_mc)}</strong>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                                            (Analytical: {pct(context.probabilities.away_win_analytical)})
                                        </div>
                                    </div>
                                </div>
                                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.75rem' }}>
                                    Derived from {context.probabilities.mc_simulations.toLocaleString()} Monte Carlo simulations.
                                </p>
                            </div>

                            {/* Elo & Calculation */}
                            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <TrendingUp size={20} className="neon-cyan-text" /> Inputs to the Model
                                </h3>
                                <div className="param-grid">
                                    <div className="param-card">
                                        <span>{context.home_team} Elo</span>
                                        <strong>{context.ratings.home_elo}
                                            <span style={{ fontSize: '0.75rem', marginLeft: '6px', color: context.ratings.home_elo_delta >= 0 ? 'var(--accent-primary)' : 'var(--accent-danger)' }}>
                                                ({signed(context.ratings.home_elo_delta)})
                                            </span>
                                        </strong>
                                    </div>
                                    <div className="param-card">
                                        <span>{context.away_team} Elo</span>
                                        <strong>{context.ratings.away_elo}
                                            <span style={{ fontSize: '0.75rem', marginLeft: '6px', color: context.ratings.away_elo_delta >= 0 ? 'var(--accent-primary)' : 'var(--accent-danger)' }}>
                                                ({signed(context.ratings.away_elo_delta)})
                                            </span>
                                        </strong>
                                    </div>
                                    <div className="param-card"><span>Elo gap</span><strong>{signed(context.ratings.elo_gap)}</strong></div>
                                    <div className="param-card"><span>Home ground advantage</span><strong>+{context.calculation.home_ground_advantage} pts</strong></div>
                                    <div className="param-card"><span>Venue scoring adj</span><strong>{signed(context.calculation.venue_scoring_adjustment)} pts</strong></div>
                                    <div className="param-card"><span>Expected margin</span><strong>{signed(context.calculation.expected_margin)}</strong></div>
                                </div>

                                <button
                                    onClick={() => setShowMath(!showMath)}
                                    style={{
                                        marginTop: '1rem', background: 'transparent', border: 'none',
                                        color: 'var(--accent-primary)', cursor: 'pointer', fontSize: '0.9rem',
                                        display: 'flex', alignItems: 'center', gap: '4px'
                                    }}
                                >
                                    {showMath ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                    {showMath ? 'Hide' : 'Show'} the math
                                </button>

                                {showMath && (
                                    <div style={{
                                        marginTop: '1rem', padding: '1rem',
                                        background: 'var(--bg-tertiary)', borderRadius: '8px',
                                        fontFamily: 'monospace', fontSize: '0.85rem', lineHeight: 1.7,
                                        color: 'var(--text-secondary)'
                                    }}>
                                        <div>rating_margin = ({context.ratings.home_elo} − {context.ratings.away_elo}) / 28 = <strong style={{ color: 'var(--text-primary)' }}>{num(context.calculation.rating_margin_points, 2)}</strong></div>
                                        <div>expected_margin = {num(context.calculation.rating_margin_points, 2)} + {context.calculation.home_ground_advantage} (HGA) = <strong style={{ color: 'var(--text-primary)' }}>{signed(context.calculation.expected_margin)}</strong></div>
                                        <div style={{ marginTop: '8px' }}>expected_home_score = 82 + atk({context.calculation.home_attack}) − away_def({context.calculation.away_defence}) + margin/2 + venue/2 = <strong style={{ color: 'var(--text-primary)' }}>{num(context.calculation.expected_home_score)}</strong></div>
                                        <div>expected_away_score = 82 + atk({context.calculation.away_attack}) − home_def({context.calculation.home_defence}) − margin/2 + venue/2 = <strong style={{ color: 'var(--text-primary)' }}>{num(context.calculation.expected_away_score)}</strong></div>
                                        <div style={{ marginTop: '8px' }}>home_prob = NormalCDF({signed(context.calculation.expected_margin)} / 36) = <strong style={{ color: 'var(--text-primary)' }}>{pct(context.probabilities.home_win_analytical)}</strong></div>
                                    </div>
                                )}
                            </div>

                            {/* Score forecast */}
                            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Target size={20} style={{ color: "#8884d8" }} /> Expected Score & Distribution
                                </h3>
                                <div className="score-summary">
                                    <div>
                                        <span>Projected Margin</span>
                                        <strong>{signed(context.calculation.expected_margin)}</strong>
                                    </div>
                                    <div>
                                        <span>Projected Total</span>
                                        <strong>{num(context.calculation.expected_total)}</strong>
                                    </div>
                                </div>
                                <div style={{ height: "260px", width: "100%" }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={scoreData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                            <XAxis dataKey="team" stroke="var(--text-secondary)" />
                                            <YAxis stroke="var(--text-secondary)" />
                                            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid #333', borderRadius: '8px' }}
                                                itemStyle={{ color: '#fff' }}
                                                formatter={(value) => value.toFixed(1)}
                                            />
                                            <Bar dataKey="score" fill="var(--accent-primary)" radius={[6, 6, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>

                                <div className="param-grid" style={{ marginTop: '1rem' }}>
                                    <div className="param-card"><span>Margin 10th pct</span><strong>{signed(context.distributions.margin_p10)}</strong></div>
                                    <div className="param-card"><span>Margin median</span><strong>{signed(context.distributions.margin_p50)}</strong></div>
                                    <div className="param-card"><span>Margin 90th pct</span><strong>{signed(context.distributions.margin_p90)}</strong></div>
                                    <div className="param-card"><span>Total 10th pct</span><strong>{num(context.distributions.total_p10)}</strong></div>
                                    <div className="param-card"><span>Total median</span><strong>{num(context.distributions.total_p50)}</strong></div>
                                    <div className="param-card"><span>Total 90th pct</span><strong>{num(context.distributions.total_p90)}</strong></div>
                                </div>
                            </div>

                            {/* Live market */}
                            <div className="glass-card">
                                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Layers size={20} className="neon-cyan-text" /> Live Market by Bookmaker
                                </h3>

                                <div style={{ display: 'flex', gap: '6px', marginBottom: '1rem' }}>
                                    {['h2h', 'spreads', 'totals'].map(m => (
                                        <button
                                            key={m}
                                            onClick={() => setMarketTab(m)}
                                            style={{
                                                padding: '0.4rem 0.8rem',
                                                background: marketTab === m ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                                                color: marketTab === m ? '#000' : 'var(--text-primary)',
                                                border: '1px solid var(--border-color)',
                                                borderRadius: '6px',
                                                cursor: 'pointer',
                                                textTransform: 'capitalize',
                                                fontSize: '0.85rem',
                                                fontWeight: 600,
                                            }}
                                        >
                                            {m === 'h2h' ? 'Head to Head' : m === 'spreads' ? 'Line' : 'Totals'}
                                        </button>
                                    ))}
                                </div>

                                {consensusForMarket.length > 0 && (
                                    <div style={{ marginBottom: '1rem', padding: '0.75rem', background: 'var(--bg-tertiary)', borderRadius: '8px' }}>
                                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>Market consensus (margin stripped):</div>
                                        {consensusForMarket.map((c, idx) => (
                                            <div key={idx} style={{ fontSize: '0.9rem', display: 'flex', justifyContent: 'space-between' }}>
                                                <span>
                                                    {c.selection}{c.point != null ? ` ${c.point > 0 ? '+' : ''}${c.point}` : ''}
                                                </span>
                                                <span style={{ color: 'var(--text-primary)' }}>
                                                    fair {pct(c.fair_probability)} ({num(c.fair_odds, 2)})
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {marketRows.length === 0 ? (
                                    <p style={{ color: 'var(--text-secondary)' }}>No prices currently available for this market.</p>
                                ) : (
                                    <div className="market-table">
                                        <div className="market-header">
                                            <span>Bookmaker</span>
                                            <span>Selection</span>
                                            <span style={{ textAlign: 'right' }}>Odds</span>
                                            <span style={{ textAlign: 'right' }}>Implied</span>
                                        </div>
                                        {marketRows.map((row, idx) => (
                                            <div key={idx} className="market-row">
                                                <span>{row.bookmaker}</span>
                                                <span>{row.selection}{row.point != null ? ` ${row.point > 0 ? '+' : ''}${row.point}` : ''}</span>
                                                <span style={{ textAlign: 'right', fontWeight: 600 }}>{num(row.odds, 2)}</span>
                                                <span style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{pct(row.implied_probability)}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
