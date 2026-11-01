import { Routes, Route, Navigate } from "react-router-dom"
import DashboardPage from "./pages/Dashboard"
import GlossaryPage from "./pages/Glossary"
import RunnerPage from "./pages/Runner"
import SupportedModFormPage from "./pages/SupportedModForm"
import SupportedModsPage from "./pages/SupportedMods"
import TranslationDetailsPage from "./pages/TranslationDetails"

/**
 * Routes contributed by the TW3 game manifest.
 *
 * @returns The TW3 page routes.
 */
export function TotalWarWarhammer3Routes() {
    return (
        <Routes>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="supported-mods" element={<SupportedModsPage />} />
            <Route path="supported-mods/new" element={<SupportedModFormPage />} />
            <Route path="supported-mods/edit/:packageName" element={<SupportedModFormPage />} />
            <Route path="translation/:workshopId" element={<TranslationDetailsPage />} />
            {/* Validation now lives on the Supported Mods page. */}
            <Route path="validate" element={<Navigate to="../supported-mods" replace />} />
            <Route path="glossary" element={<GlossaryPage />} />
            <Route path="runner" element={<RunnerPage />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Routes>
    )
}
