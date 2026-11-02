import { useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query"
import type { ContextFields } from "@/components/TranslationPage/ContextPanel"

/** How a game loads and saves one mod's context. */
export interface ModContextStore<T> {
    load: () => Promise<T>
    save: (next: T) => Promise<void>
}

/**
 * One mod's saved context, such as the character fields fed to the prompt. A save shows at once and is rolled back when the backend refuses it.
 *
 * @param queryKey Cache key, unique to the game and mod.
 * @param store The game's load and save calls.
 * @param empty The context before it loads, or when loading fails.
 * @returns The context, its loading flag, whether any character field is filled, and `save`.
 */
export function useModContext<T extends ContextFields>(queryKey: QueryKey, store: ModContextStore<T>, empty: T) {
    const queryClient = useQueryClient()
    const { data = empty, isPending } = useQuery({ queryKey, queryFn: store.load })

    /**
     * Merge fields into the context and save the whole of it.
     *
     * @param patch Fields to change.
     */
    const save = async (patch: Partial<T>) => {
        // Read the cache rather than this render's value so two quick saves both keep their fields.
        const before = queryClient.getQueryData<T>(queryKey) ?? empty
        const next = { ...before, ...patch }
        queryClient.setQueryData(queryKey, next)
        try {
            await store.save(next)
        } catch (err) {
            queryClient.setQueryData(queryKey, before)
            throw err
        }
    }

    return { context: data, loading: isPending, hasContext: !!(data.source_game || data.character_name || data.background), save }
}
