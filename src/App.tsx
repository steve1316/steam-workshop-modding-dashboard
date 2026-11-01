import { useState, useEffect } from "react"
import { Routes, Route, Navigate, useParams, useMatch, useLocation } from "react-router-dom"
import Sidebar from "./components/Sidebar"
import ErrorBoundary from "./ui/ErrorBoundary"
import LoadingState from "./ui/LoadingState"
import { getBranding } from "./components/GameSwitcher/branding"
import SettingsPage from "./pages/Settings"
import { API_BASE } from "./config"
import { getGame, getGameBySlug, slugForId } from "./games/registry"
import "./games/chrono_ark" // side-effect: registers manifest
import "./games/total_war_warhammer_3" // side-effect: registers manifest
import "./index.css"

/**
 * Renders the resolved game's route subtree, or redirects home when the slug is unknown.
 * @returns The active game's routes, or a redirect to `/`.
 */
function GameSubtree() {
    const { gameSlug } = useParams<{ gameSlug: string }>()
    const manifest = gameSlug ? getGameBySlug(gameSlug) : undefined
    if (!manifest) return <Navigate to="/" replace />
    return manifest.routes()
}

/**
 * App shell: a persistent sidebar plus the routed page area. The `:gameSlug` URL segment is the source of truth for the active game.
 * @returns The application shell.
 */
function App() {
    const [defaultGameId, setDefaultGameId] = useState<string>("chrono_ark")
    const [loading, setLoading] = useState(true)
    // Keeps /settings in the game the user came from.
    const [lastGameId, setLastGameId] = useState<string | null>(null)
    const location = useLocation()

    // Only picks the default redirect target for "/".
    useEffect(() => {
        fetch(`${API_BASE}/settings`)
            .then((r) => r.json())
            .then((data) => setDefaultGameId(data.active_game ?? "chrono_ark"))
            .catch((err) => console.error("Failed to load active game:", err))
            .finally(() => setLoading(false))
    }, [])

    // Off-slug routes (e.g. /settings) fall back to the last game visited, then the persisted default.
    const match = useMatch("/:gameSlug/*")
    const activeSlug = match?.params.gameSlug
    const routeGameId = activeSlug ? getGameBySlug(activeSlug)?.id : undefined
    // Derived-state pattern, so the first /settings render already uses the route's game.
    if (routeGameId && routeGameId !== lastGameId) setLastGameId(routeGameId)
    const activeGameId = routeGameId || lastGameId || defaultGameId
    const isDetailPage = !!useMatch("/:gameSlug/translation/*")
    const defaultSlug = slugForId(defaultGameId) ?? "chrono_ark"

    // Set on <html> so portaled dialogs inherit the game's theme variables.
    const branding = getBranding(activeGameId)
    useEffect(() => {
        const root = document.documentElement.style
        root.setProperty("--game-accent", branding.accent)
        root.setProperty("--game-accent-gradient", branding.gradient)
    }, [branding.accent, branding.gradient])

    const gameName = getGame(activeGameId)?.displayName ?? "Chrono Ark"
    useEffect(() => {
        document.title = `${gameName} Translator`
    }, [gameName])

    return (
        <>
            <Sidebar activeGameId={activeGameId} />

            <main className={isDetailPage ? "container-fluid" : "container"}>
                {loading ? (
                    <LoadingState message="Loading resources..." />
                ) : (
                    <ErrorBoundary key={location.pathname}>
                        <Routes>
                            <Route path="/settings" element={<SettingsPage gameId={activeGameId} />} />

                            <Route path="/:gameSlug/*" element={<GameSubtree />} />

                            <Route path="*" element={<Navigate to={`/${defaultSlug}/dashboard`} replace />} />
                        </Routes>
                    </ErrorBoundary>
                )}
            </main>
        </>
    )
}

export default App
