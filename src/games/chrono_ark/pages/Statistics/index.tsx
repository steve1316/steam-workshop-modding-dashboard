import React, { useEffect, useState } from "react"

import { API_BASE } from "@/lib/api"
import type { Stats } from "@/games/chrono_ark/lib/types"
import ErrorState from "@/components/ui/ErrorState"
import LoadingState from "@/components/ui/LoadingState"
import PageHeader from "@/components/ui/PageHeader"

/**
 * Translation memory and global progress, from the cross-game `GET /api/stats`.
 *
 * @returns The statistics page, its loading state, or an error with Retry.
 */
const StatisticsPage: React.FC = () => {
    const [stats, setStats] = useState<Stats | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [attempt, setAttempt] = useState(0)

    useEffect(() => {
        let cancelled = false
        fetch(`${API_BASE}/stats`)
            .then((res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                return res.json()
            })
            .then((data: Stats) => {
                if (!cancelled) setStats(data)
            })
            .catch((err: unknown) => {
                if (!cancelled) setError(err instanceof Error ? err.message : String(err))
            })
        return () => {
            cancelled = true
        }
    }, [attempt])

    /** Clear the error, which brings the loading state back, and load again. */
    const retry = () => {
        setError(null)
        setAttempt((n) => n + 1)
    }

    if (error) return <ErrorState title="Could not load statistics" message={`${error}. Check that the backend is running, then retry.`} action={{ label: "Retry", onClick: retry }} />
    if (!stats) return <LoadingState message="Loading statistics..." />

    return (
        <div className="stats-view animate-fade-in">
            <PageHeader title="System Statistics" meta={<p>Translation memory and global progress</p>} />

            <div className="mod-grid">
                <div className="glass-card stat-tile">
                    <h2 className="stat-tile-value stat-tile-primary">{stats.global_progress}%</h2>
                    <p className="stat-tile-label">Global Progress</p>
                </div>
                <div className="glass-card stat-tile">
                    <h2 className="stat-tile-value stat-tile-secondary">{stats.tm_entries}</h2>
                    <p className="stat-tile-label">Translation Memory Entries</p>
                </div>
                <div className="glass-card stat-tile">
                    <h2 className="stat-tile-value stat-tile-success">{stats.tm_hits}</h2>
                    <p className="stat-tile-label">Total Cache Hits</p>
                </div>
            </div>
        </div>
    )
}

export default StatisticsPage
