import { Routes, Route, Navigate } from "react-router-dom"
import DashboardPage from "@/games/chrono_ark/pages/Dashboard"
import ModDetail from "@/games/chrono_ark/pages/Details"
import GlossaryPage from "@/games/chrono_ark/pages/Glossary"
import StatisticsPage from "@/games/chrono_ark/pages/Statistics"

/**
 * Chrono Ark routes, mounted under the active-game subtree. Bare `/` redirects to the dashboard.
 *
 * @returns The routes.
 */
export function ChronoArkRoutes() {
    return (
        <Routes>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="translation/:modId" element={<ModDetail />} />
            <Route path="glossary" element={<GlossaryPage />} />
            <Route path="statistics" element={<StatisticsPage />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Routes>
    )
}
