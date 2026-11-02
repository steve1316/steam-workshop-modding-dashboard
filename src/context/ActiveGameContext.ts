import { createContext, useContext } from "react"
import type { GameManifest } from "@/games/registry"

/** The game the shell is showing: the route's game, or on /settings the last one visited. */
export const ActiveGameContext = createContext<GameManifest | null>(null)

/**
 * Read the active game's manifest.
 *
 * @returns The manifest. Throws outside an `ActiveGameContext` provider.
 */
export function useActiveGame(): GameManifest {
    const game = useContext(ActiveGameContext)
    if (!game) throw new Error("useActiveGame must be used inside an ActiveGameContext provider")
    return game
}
