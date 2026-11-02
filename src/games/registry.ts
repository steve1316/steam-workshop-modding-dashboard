import type { ComponentType, ReactElement } from "react"

export interface GameNavEntry {
    to: string
    label: string
    icon: ReactElement
}

/** Per-game visual identity used by the GameSwitcher pills, the sidebar's active-game header and the accent CSS variables. */
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

/** Props the shared Settings page passes to a game's settings panels. */
export interface GameSettingsPanelProps {
    /** Current value of each of the game's `settingsPanel.keys`. */
    values: Record<string, string>
    onChange: (key: string, value: string) => void
    /** Records a value the backend already saved, such as an installed SteamCMD path, so it is not a pending change. */
    onSaved: (key: string, value: string) => void
    /** Prefix for field ids, unique to the Settings page. */
    fieldId: string
}

/** A game's section of the Settings page and the `/api/settings` keys it edits. */
export interface GameSettingsSlot {
    /** String fields of `/api/settings` that the panels read, and that Save sends when they change. */
    keys: string[]
    Panel: ComponentType<GameSettingsPanelProps>
}

export interface GameManifest {
    id: string
    /** URL slug for game-prefixed routes (e.g. `warhammer_3` for id `total_war_warhammer_3`). */
    slug: string
    displayName: string
    icon: string
    branding: GameBranding
    nav: GameNavEntry[]
    routes: () => ReactElement
    settingsPanel?: GameSettingsSlot
}

const FALLBACK_BRANDING: GameBranding = {
    logo: "",
    accent: "var(--text-dim)",
    gradient: "linear-gradient(135deg, #94a3b8 0%, #64748b 100%)",
    subtitle: "",
}

const _registry = new Map<string, GameManifest>()

export function registerGame(manifest: GameManifest): void {
    _registry.set(manifest.id, manifest)
}

export function getGame(id: string): GameManifest | undefined {
    return _registry.get(id)
}

export function listGames(): GameManifest[] {
    return [..._registry.values()]
}

export function getGameBySlug(slug: string): GameManifest | undefined {
    return [..._registry.values()].find((g) => g.slug === slug)
}

export function idForSlug(slug: string): string | undefined {
    return getGameBySlug(slug)?.id
}

export function slugForId(id: string): string | undefined {
    return _registry.get(id)?.slug
}

/**
 * Get a game's branding, falling back to a neutral entry for a backend game the frontend has not registered.
 *
 * @param gameId Backend `game_id`, e.g. `"chrono_ark"`.
 * @returns The manifest's branding, or `FALLBACK_BRANDING`.
 */
export function getBranding(gameId: string): GameBranding {
    return _registry.get(gameId)?.branding ?? FALLBACK_BRANDING
}
