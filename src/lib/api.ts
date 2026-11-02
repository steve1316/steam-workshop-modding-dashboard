/** Port injected by Vite at build time from SWMT_API_PORT in backend/.env. */
declare const __API_PORT__: string

/** Base URL for the FastAPI backend. */
export const API_BASE = `http://localhost:${__API_PORT__}/api`

export interface GameMetadata {
    game_id: string
    display_name: string
    icon: string
    capabilities: string[]
}

export function gameApi(gameId: string) {
    const base = `${API_BASE}/games/${gameId}`
    return {
        get: (path: string, init?: RequestInit) => fetch(`${base}${path}`, init),
        post: (path: string, body?: unknown, init?: RequestInit) =>
            fetch(`${base}${path}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: body == null ? undefined : JSON.stringify(body),
                ...init,
            }),
        put: (path: string, body?: unknown, init?: RequestInit) =>
            fetch(`${base}${path}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: body == null ? undefined : JSON.stringify(body),
                ...init,
            }),
        delete: (path: string, init?: RequestInit) => fetch(`${base}${path}`, { method: "DELETE", ...init }),
        url: (path: string) => `${base}${path}`,
    }
}

/**
 * Fetch a URL and parse its JSON body.
 *
 * @param url Absolute URL.
 * @param init Fetch options.
 * @returns The parsed body. A non-2xx status throws `HTTP <status>`.
 */
export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
    const res = await fetch(url, init)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
}

export async function fetchGames(): Promise<GameMetadata[]> {
    const res = await fetch(`${API_BASE}/games`)
    if (!res.ok) throw new Error(`Failed to load games: ${res.status}`)
    return res.json()
}
