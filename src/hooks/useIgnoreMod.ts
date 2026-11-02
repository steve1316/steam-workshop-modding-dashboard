import { useQueryClient } from "@tanstack/react-query"
import { API_BASE } from "@/lib/api"
import { settingsQuery } from "@/lib/queryClient"

/**
 * Adds a mod to, or takes it off, the saved ignore list that hides mods from the dashboard.
 *
 * @returns `setIgnored`, which saves the change and updates the shared settings cache.
 */
export function useIgnoreMod() {
    const queryClient = useQueryClient()

    /**
     * Save a mod's ignored state.
     *
     * @param modId Workshop id.
     * @param ignored True to hide the mod, false to show it again.
     */
    const setIgnored = async (modId: string, ignored: boolean) => {
        // Fetch the saved list first so an id ignored elsewhere since the page loaded is not dropped.
        const current = await queryClient.fetchQuery(settingsQuery)
        const others = ((current.ignored_mods as string[] | undefined) ?? []).filter((id) => id !== modId)
        const res = await fetch(`${API_BASE}/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ignored_mods: ignored ? [...others, modId] : others }),
        })
        const body = await res.json()
        if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`)
        queryClient.setQueryData(settingsQuery.queryKey, body)
    }

    return { setIgnored }
}
