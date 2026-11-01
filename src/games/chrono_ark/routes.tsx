import { Routes, Route, Navigate } from "react-router-dom"
import DashboardPage from "./pages/Dashboard"
import ModDetail from "./pages/Details"
import GlossaryPage from "./pages/Glossary"
import StatisticsPage from "./pages/Statistics"

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
