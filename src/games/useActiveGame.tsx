import { useParams } from "react-router-dom"
import { getGameBySlug, type GameManifest } from "@/games/registry"

/** The resolved active game derived from the `:gameSlug` URL segment. */
export interface ActiveGame {
    /** Backend game id (e.g. `total_war_warhammer_3`). */
    id: string
    /** URL slug (e.g. `warhammer_3`). */
    slug: string
    /** The full registered manifest. */
    manifest: GameManifest
}

/**
 * Resolve the active game from the current `:gameSlug` route param.
 * @returns The active game, or null when the slug is missing or unregistered.
 */
export function useActiveGame(): ActiveGame | null {
    const { gameSlug } = useParams<{ gameSlug: string }>()
    if (!gameSlug) return null
    const manifest = getGameBySlug(gameSlug)
    if (!manifest) return null
    return { id: manifest.id, slug: manifest.slug, manifest }
}
