import { QueryClient, queryOptions } from "@tanstack/react-query"
import { API_BASE, fetchJson } from "@/lib/api"

/** The saved app settings. Pages share this cache entry, so a save in Settings shows everywhere. */
export const settingsQuery = queryOptions({ queryKey: ["settings"], queryFn: () => fetchJson<Record<string, unknown>>(`${API_BASE}/settings`) })

/**
 * Build the app's TanStack Query client.
 *
 * @returns A client that fails fast, since every page shows its own Retry, and only refetches when told to.
 */
export function createQueryClient(): QueryClient {
    return new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } })
}
