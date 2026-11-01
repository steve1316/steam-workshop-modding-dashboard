import React from "react"
import { NavLink } from "react-router-dom"
import { FaCog } from "react-icons/fa"
import GameSwitcher from "../GameSwitcher"
import { getBranding } from "../GameSwitcher/branding"
import { getGame, slugForId } from "../../games/registry"

interface SidebarProps {
    activeGameId: string
}

/**
 * Persistent sidebar: the `GameSwitcher`, an active-game header, the active game's manifest nav entries, and the cross-game Settings link.
 *
 * @param activeGameId Active game's id, used to look up the manifest and branding.
 * @returns The sidebar.
 */
const Sidebar: React.FC<SidebarProps> = ({ activeGameId }) => {
    const game = getGame(activeGameId)
    const slug = slugForId(activeGameId) ?? activeGameId
    const branding = getBranding(activeGameId)
    const hasBranding = branding.subtitle.length > 0
    const titleStyle: React.CSSProperties = hasBranding
        ? {
              backgroundImage: branding.gradient,
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              WebkitTextFillColor: "transparent",
              color: "transparent",
          }
        : {}
    const displayName = game?.displayName ?? humanizeGameId(activeGameId)

    return (
        <div className="sidebar">
            <GameSwitcher activeGameId={activeGameId} />

            <div className="sidebar__game-header">
                <div data-testid="sidebar-game-title" className="sidebar__game-title" style={titleStyle}>
                    {displayName}
                </div>
                {hasBranding && (
                    <div data-testid="sidebar-game-subtitle" className="sidebar__game-subtitle">
                        {branding.subtitle}
                    </div>
                )}
                <div data-testid="sidebar-game-divider" className="sidebar__game-divider" />
            </div>

            <nav style={{ display: "flex", flexDirection: "column", gap: "0.5rem", padding: "0.5rem" }}>
                {game?.nav.map((entry) => (
                    <NavLink
                        key={entry.to}
                        to={`/${slug}${entry.to}`}
                        className={({ isActive }) => `nav-link btn-outline ${isActive ? "active" : ""}`}
                        style={{ border: "none", textAlign: "left", width: "100%", textDecoration: "none", display: "flex", alignItems: "center", gap: "0.75rem" }}
                    >
                        {entry.icon} {entry.label}
                    </NavLink>
                ))}
                <NavLink
                    to="/settings"
                    className={({ isActive }) => `nav-link btn-outline ${isActive ? "active" : ""}`}
                    style={{ border: "none", textAlign: "left", width: "100%", textDecoration: "none", display: "flex", alignItems: "center", gap: "0.75rem" }}
                >
                    <FaCog /> Settings
                </NavLink>
            </nav>
        </div>
    )
}

/**
 * Convert a snake_case game id to a Title Case label, e.g. `"future_game"` to `"Future Game"`. Fallback for ids with no manifest entry.
 *
 * @param gameId Raw `game_id`.
 * @returns The display name.
 */
function humanizeGameId(gameId: string): string {
    return gameId
        .split("_")
        .filter((part) => part.length > 0)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ")
}

export default Sidebar
