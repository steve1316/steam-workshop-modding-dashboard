import { API_BASE } from "@/lib/config"

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

export async function fetchGames(): Promise<GameMetadata[]> {
    const res = await fetch(`${API_BASE}/games`)
    if (!res.ok) throw new Error(`Failed to load games: ${res.status}`)
    return res.json()
}
