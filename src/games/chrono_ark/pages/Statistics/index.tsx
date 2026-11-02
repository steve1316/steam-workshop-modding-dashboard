import React from "react"
import { useQuery } from "@tanstack/react-query"

import { API_BASE, fetchJson } from "@/lib/api"
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
    const { data: stats, error, isFetching, refetch } = useQuery({ queryKey: ["stats"], queryFn: () => fetchJson<Stats>(`${API_BASE}/stats`) })

    // While Retry is in flight the loading state shows instead of the old error.
    if (error && !isFetching)
        return <ErrorState title="Could not load statistics" message={`${error.message}. Check that the backend is running, then retry.`} action={{ label: "Retry", onClick: () => refetch() }} />
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
