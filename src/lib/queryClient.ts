import { QueryClient } from "@tanstack/react-query"

/**
 * Build the app's TanStack Query client.
 *
 * @returns A client that fails fast, since every page shows its own Retry, and only refetches when told to.
 */
export function createQueryClient(): QueryClient {
    return new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } })
}
