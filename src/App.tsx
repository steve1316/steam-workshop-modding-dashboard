import { useState, useEffect } from "react"
import { Routes, Route, Navigate, useParams, useMatch, useLocation } from "react-router-dom"
import Sidebar from "@/components/Sidebar"
import ErrorBoundary from "@/components/ui/ErrorBoundary"
import LoadingState from "@/components/ui/LoadingState"
import SettingsPage from "@/pages/Settings"
import { ActiveGameContext } from "@/context/ActiveGameContext"
import { API_BASE } from "@/lib/api"
import { getGame, getGameBySlug, listGames, type GameManifest } from "@/games/registry"
import "@/games/chrono_ark" // side-effect: registers manifest
import "@/games/total_war_warhammer_3" // side-effect: registers manifest

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
    // The first registered game until settings name the one the user last used.
    const [defaultGame, setDefaultGame] = useState<GameManifest>(() => listGames()[0])
    const [loading, setLoading] = useState(true)
    // Keeps /settings in the game the user came from.
    const [lastGameId, setLastGameId] = useState<string | null>(null)
    const location = useLocation()

    // Only picks the default redirect target for "/".
    useEffect(() => {
        fetch(`${API_BASE}/settings`)
            .then((r) => r.json())
            .then((data) => {
                const saved = getGame(data.active_game ?? "")
                if (saved) setDefaultGame(saved)
            })
            .catch((err) => console.error("Failed to load active game:", err))
            .finally(() => setLoading(false))
    }, [])

    // Off-slug routes (e.g. /settings) fall back to the last game visited, then the persisted default.
    const match = useMatch("/:gameSlug/*")
    const activeSlug = match?.params.gameSlug
    const routeGame = activeSlug ? getGameBySlug(activeSlug) : undefined
    // Derived-state pattern, so the first /settings render already uses the route's game.
    if (routeGame && routeGame.id !== lastGameId) setLastGameId(routeGame.id)
    const activeGame = routeGame ?? (lastGameId ? getGame(lastGameId) : undefined) ?? defaultGame
    const isDetailPage = !!useMatch("/:gameSlug/translation/*")

    // Set on <html> so portaled dialogs inherit the game's theme variables.
    const branding = activeGame.branding
    useEffect(() => {
        const root = document.documentElement.style
        root.setProperty("--game-accent", branding.accent)
        root.setProperty("--game-accent-gradient", branding.gradient)
    }, [branding.accent, branding.gradient])

    const gameName = activeGame.displayName
    useEffect(() => {
        document.title = `${gameName} Translator`
    }, [gameName])

    return (
        <ActiveGameContext value={activeGame}>
            <Sidebar />

            <main className={isDetailPage ? "container-fluid" : "container"}>
                {loading ? (
                    <LoadingState message="Loading resources..." />
                ) : (
                    <ErrorBoundary key={location.pathname}>
                        <Routes>
                            <Route path="/settings" element={<SettingsPage />} />

                            <Route path="/:gameSlug/*" element={<GameSubtree />} />

                            <Route path="*" element={<Navigate to={`/${defaultGame.slug}/dashboard`} replace />} />
                        </Routes>
                    </ErrorBoundary>
                )}
            </main>
        </ActiveGameContext>
    )
}

export default App
