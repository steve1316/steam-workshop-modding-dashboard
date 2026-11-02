import React from "react"
import { NavLink } from "react-router-dom"
import { FaCog } from "react-icons/fa"
import GameSwitcher from "@/components/GameSwitcher"
import { useActiveGame } from "@/context/ActiveGameContext"
import "@/components/Sidebar/styles.css"

/**
 * Persistent sidebar: the `GameSwitcher`, an active-game header, the active game's manifest nav entries, and the cross-game Settings link.
 *
 * @returns The sidebar.
 */
const Sidebar: React.FC = () => {
    const game = useActiveGame()
    const { branding } = game
    const titleStyle: React.CSSProperties = {
        backgroundImage: branding.gradient,
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        WebkitTextFillColor: "transparent",
        color: "transparent",
    }

    return (
        <div className="sidebar">
            <GameSwitcher />

            <div className="sidebar__game-header">
                <div data-testid="sidebar-game-title" className="sidebar__game-title" style={titleStyle}>
                    {game.displayName}
                </div>
                {branding.subtitle && (
                    <div data-testid="sidebar-game-subtitle" className="sidebar__game-subtitle">
                        {branding.subtitle}
                    </div>
                )}
                <div data-testid="sidebar-game-divider" className="sidebar__game-divider" />
            </div>

            <nav style={{ display: "flex", flexDirection: "column", gap: "0.5rem", padding: "0.5rem" }}>
                {game.nav.map((entry) => (
                    <NavLink
                        key={entry.to}
                        to={`/${game.slug}${entry.to}`}
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

export default Sidebar
