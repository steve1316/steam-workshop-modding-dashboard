import { useParams } from "react-router-dom"

/**
 * Return the `:gameSlug` route segment, for building game-prefixed links like `/${slug}/translation/${id}`.
 * @returns The slug, or "" outside a game subtree.
 */
export function useGameSlug(): string {
    return useParams<{ gameSlug: string }>().gameSlug ?? ""
}
