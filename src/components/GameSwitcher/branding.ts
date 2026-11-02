import chronoArkLogo from "@/assets/games/chrono_ark.png"
import wh3Logo from "@/assets/games/wh3.png"

/** Per-game visual identity used by the GameSwitcher pills and the sidebar's active-game header. */
export interface GameBranding {
    /** Square logo PNG URL. Empty for the fallback. */
    logo: string
    /** Active pill's border and outer glow. */
    accent: string
    /** Active pill's background fill and the sidebar's active-game title text. */
    gradient: string
    /** Subtitle under the active game's name. Empty for the fallback. */
    subtitle: string
}

/** Registered branding entries, keyed by the backend's `game_id`. */
export const GAME_BRANDING: Record<string, GameBranding> = {
    chrono_ark: {
        logo: chronoArkLogo,
        accent: "#38bdf8",
        gradient: "linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)",
        subtitle: "Translation tools",
    },
    total_war_warhammer_3: {
        logo: wh3Logo,
        accent: "#dc2626",
        gradient: "linear-gradient(135deg, #dc2626 0%, #f97316 100%)",
        subtitle: "Workshop tools",
    },
}

const FALLBACK_BRANDING: GameBranding = {
    logo: "",
    accent: "var(--text-dim)",
    gradient: "linear-gradient(135deg, #94a3b8 0%, #64748b 100%)",
    subtitle: "",
}

/**
 * Get branding for a game id, falling back to a neutral entry so a game registered without branding still renders.
 *
 * @param gameId Backend `game_id`, e.g. `"chrono_ark"`.
 * @returns The registered branding, or `FALLBACK_BRANDING`.
 */
export function getBranding(gameId: string): GameBranding {
    return GAME_BRANDING[gameId] ?? FALLBACK_BRANDING
}
