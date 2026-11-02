import { useEffect, useRef, useState, type KeyboardEvent } from "react"
import { useNavigate } from "react-router-dom"
import { fetchGames, type GameMetadata } from "@/lib/api"
import { API_BASE } from "@/lib/config"
import { slugForId } from "@/games/registry"
import { getBranding } from "@/components/GameSwitcher/branding"

interface GameSwitcherProps {
    /** Marks the matching pill `aria-checked` and skips the POST when re-clicked. */
    activeGameId: string
}

/**
 * Segmented toggle for switching between registered games. Navigates to the new game's dashboard at once, then saves `active_game` in the background.
 *
 * @param activeGameId Active game's id.
 * @returns The radiogroup of pills, or `null` while the games list loads.
 */
const GameSwitcher = ({ activeGameId }: GameSwitcherProps) => {
    const [games, setGames] = useState<GameMetadata[]>([])
    const navigate = useNavigate()
    const pillRefs = useRef<Record<string, HTMLButtonElement | null>>({})

    useEffect(() => {
        fetchGames()
            .then(setGames)
            .catch((err) => console.error("Failed to load games:", err))
    }, [])

    const handleSelect = (gameId: string) => {
        if (gameId === activeGameId) return
        // The URL is the source of truth, and the persisted setting only seeds the "/" redirect, so saving can finish in the background.
        navigate(`/${slugForId(gameId) ?? gameId}/dashboard`)
        fetch(`${API_BASE}/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ active_game: gameId }),
        }).catch((err) => console.error("Failed to persist active game:", err))
    }

    const handleKey = (evt: KeyboardEvent<HTMLButtonElement>, idx: number) => {
        if (games.length === 0) return
        if (evt.key === "ArrowRight" || evt.key === "ArrowDown") {
            evt.preventDefault()
            const next = games[(idx + 1) % games.length]
            pillRefs.current[next.game_id]?.focus()
        } else if (evt.key === "ArrowLeft" || evt.key === "ArrowUp") {
            evt.preventDefault()
            const prev = games[(idx - 1 + games.length) % games.length]
            pillRefs.current[prev.game_id]?.focus()
        } else if (evt.key === "Enter" || evt.key === " ") {
            evt.preventDefault()
            const current = games[idx]
            handleSelect(current.game_id)
        }
    }

    if (games.length === 0) return null

    return (
        <div role="radiogroup" aria-label="Active game" className="game-switcher">
            {games.map((g, idx) => {
                const branding = getBranding(g.game_id)
                const selected = g.game_id === activeGameId
                const pillStyle: React.CSSProperties = selected
                    ? {
                          borderColor: branding.accent,
                          boxShadow: `0 0 14px ${hexToRgba(branding.accent, 0.28)}`,
                          backgroundImage: `${branding.gradient}, var(--glass-bg)`,
                          backgroundBlendMode: "overlay",
                      }
                    : {}
                return (
                    <button
                        key={g.game_id}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        aria-label={g.display_name}
                        tabIndex={selected ? 0 : -1}
                        ref={(el) => {
                            pillRefs.current[g.game_id] = el
                        }}
                        onClick={() => handleSelect(g.game_id)}
                        onKeyDown={(e) => handleKey(e, idx)}
                        className={`game-switcher__pill${selected ? " game-switcher__pill--active" : ""}`}
                        style={pillStyle}
                    >
                        {branding.logo ? (
                            <img src={branding.logo} alt={g.display_name} className="game-switcher__logo" draggable={false} />
                        ) : (
                            <span className="game-switcher__fallback" aria-hidden="true">
                                {g.display_name.charAt(0).toUpperCase()}
                            </span>
                        )}
                    </button>
                )
            })}
        </div>
    )
}

/**
 * Convert a `#rrggbb` color to `rgba(r,g,b,alpha)`, falling back to a neutral grey on parse failure.
 *
 * @param hex `#rrggbb` color.
 * @param alpha 0-1.
 * @returns An `rgba(...)` string.
 */
function hexToRgba(hex: string, alpha: number): string {
    const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
    if (!match) return `rgba(148, 163, 184, ${alpha})`
    const r = parseInt(match[1], 16)
    const g = parseInt(match[2], 16)
    const b = parseInt(match[3], 16)
    return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export default GameSwitcher
