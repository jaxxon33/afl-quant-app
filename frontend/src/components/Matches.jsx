import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Activity, Clock, Target } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export default function Matches() {
    const [matches, setMatches] = useState([])
    const [selectedMatch, setSelectedMatch] = useState(null)
    const [projection, setProjection] = useState(null)
    const [projectionLoading, setProjectionLoading] = useState(false)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchMatches = async () => {
            try {
                const res = await fetch(`${API_BASE}/matches`)
                const data = await res.json()
                setMatches(data)
                if (data.length > 0) {
                    setSelectedMatch(data[0])
                }
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

        const fetchProjection = async () => {
            setProjectionLoading(true)
            try {
                const res = await fetch(`${API_BASE}/matches/${selectedMatch.id}/projection`)
                const data = await res.json()
                setProjection(data)
            } catch (e) {
                console.error("Error fetching projection", e)
                setProjection(null)
            } finally {
                setProjectionLoading(false)
            }
        }

        fetchProjection()
    }, [selectedMatch])

    const scoreData = projection ? [
        { team: projection.home_team, score: projection.expected_home_score },
        { team: projection.away_team, score: projection.expected_away_score }
    ] : []

    if (loading) {
        return (
            <div className="loader-container">
                <div className="loader-circle"></div>
                <p>Loading Matches...</p>
            </div>
        )
    }

    return (
        <div className="matches-page">
            <div className="header-actions" style={{ marginBottom: "2rem" }}>
                <div>
                    <h1>AFL Matches <span className="neon-cyan-text">& Projections</span></h1>
                    <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
                        Upcoming fixtures with current model probabilities and expected scoring.
                    </p>
                </div>
            </div>

            <div className="layout-grid">
                {/* Match Selection Column */}
                <div className="matches-list glass-card">
                    <h3 style={{ marginBottom: "1rem" }}><Clock size={18} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'middle' }} /> Upcoming Matches</h3>
                    <div className="matches-scroll">
                        {matches.length === 0 ? (
                            <p>No upcoming matches found.</p>
                        ) : (
                            matches.map(match => (
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
                                    <div className="match-venue">{new Date(match.match_date?.split('.')[0]).toLocaleDateString()} &middot; {match.venue}</div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Match Data Column */}
                <div className="match-details">
                    {selectedMatch ? (
                        <>
                            <div className="glass-card" style={{ marginBottom: "1.5rem" }}>
                                <h2>{selectedMatch.home_team} <span style={{ color: "var(--text-secondary)" }}>vs</span> {selectedMatch.away_team}</h2>
                                <p style={{ color: "var(--text-secondary)", marginBottom: "1.5rem" }}>
                                    Match Date: {new Date(selectedMatch.match_date?.split('.')[0]).toLocaleDateString()} &middot; {selectedMatch.venue}
                                </p>

                                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Activity size={20} className="neon-cyan-text" />
                                    Model Win Probability
                                </h3>
                                {projectionLoading || !projection ? (
                                    <p style={{ color: "var(--text-secondary)" }}>Loading projection...</p>
                                ) : (
                                    <div className="projection-grid">
                                        <div className="projection-card">
                                            <span>{projection.home_team}</span>
                                            <strong>{(projection.home_win_probability * 100).toFixed(1)}%</strong>
                                        </div>
                                        <div className="projection-card">
                                            <span>{projection.away_team}</span>
                                            <strong>{(projection.away_win_probability * 100).toFixed(1)}%</strong>
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className="glass-card">
                                <h3 style={{ marginBottom: "1rem", display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Target size={20} style={{ color: "#8884d8" }} />
                                    Expected Score
                                </h3>
                                {projectionLoading || !projection ? (
                                    <p style={{ color: "var(--text-secondary)" }}>Loading score forecast...</p>
                                ) : (
                                    <>
                                        <div className="score-summary">
                                            <div>
                                                <span>Projected Margin</span>
                                                <strong>{projection.expected_margin > 0 ? '+' : ''}{projection.expected_margin.toFixed(1)}</strong>
                                            </div>
                                            <div>
                                                <span>Projected Total</span>
                                                <strong>{projection.expected_total.toFixed(1)}</strong>
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
                                    </>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="glass-card empty-state">
                            <p>Select a match to view data.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
