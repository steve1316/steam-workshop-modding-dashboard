import { afterEach, describe, expect, it, vi } from "vitest"
import { fetchChangeNotes, fetchSupportedMods, getCurrentRun, publishAllPacks, publishAllStreamUrl, runStreamUrl, startRun } from "@/games/total_war_warhammer_3/lib/registryApi"

afterEach(() => {
    vi.restoreAllMocks()
})

describe("tw3 api wrappers", () => {
    it("fetchSupportedMods hits /api/games/total_war_warhammer_3/supported-mods", async () => {
        const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ mods: [] }), { status: 200 }))
        await fetchSupportedMods()
        expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/games/total_war_warhammer_3/supported-mods"), undefined)
    })

    it("startRun POSTs /run/{script_id}", async () => {
        const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }))
        await startRun("update_dynamic_rors")
        const [url, init] = fetchMock.mock.calls[0]
        expect(String(url)).toContain("/api/games/total_war_warhammer_3/run/update_dynamic_rors")
        expect((init as RequestInit).method).toBe("POST")
    })

    it("getCurrentRun hits /api/games/total_war_warhammer_3/run", async () => {
        const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "idle" }), { status: 200 }))
        await getCurrentRun()
        expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/games/total_war_warhammer_3/run"), undefined)
    })

    it("runStreamUrl returns the SSE endpoint", () => {
        expect(runStreamUrl()).toContain("/api/games/total_war_warhammer_3/run/stream")
    })

    it("publishAllPacks POSTs /packs/publish-all with a changenote per item", async () => {
        const responseBody = { batch_id: "abc", started_at: "2026-05-27T00:00:00Z", queued: 2, skipped: [] }
        const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(responseBody), { status: 200 }))
        const items = [
            { workshop_id: "111", title: "Mod A", changenote: "note A" },
            { workshop_id: "222", title: "Mod B", changenote: "note B" },
        ]
        const result = await publishAllPacks(items)
        const [url, init] = fetchMock.mock.calls[0]
        expect(String(url)).toContain("/api/games/total_war_warhammer_3/packs/publish-all")
        expect(init?.method).toBe("POST")
        const body = JSON.parse(String(init?.body))
        expect(body).toEqual({ items })
        expect(result.batch_id).toBe("abc")
        expect(result.queued).toBe(2)
    })

    it("publishAllPacks throws RegistryError when the backend returns a non-2xx response", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "boom" }), { status: 409 }))
        await expect(publishAllPacks([{ workshop_id: "111", title: "X", changenote: "notes" }])).rejects.toThrow()
    })

    it("publishAllStreamUrl returns the per-batch SSE endpoint", () => {
        const url = publishAllStreamUrl("batch-123")
        expect(url).toContain("/api/games/total_war_warhammer_3/packs/publish-all/stream/batch-123")
    })

    it("fetchChangeNotes POSTs the ids to /packs/change-notes", async () => {
        const responseBody = { notes: { "111": { note: "n", pending: true, kind: "compat" } }, errors: [] }
        const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(responseBody), { status: 200 }))
        const result = await fetchChangeNotes(["111"])
        const [url, init] = fetchMock.mock.calls[0]
        expect(String(url)).toContain("/api/games/total_war_warhammer_3/packs/change-notes")
        expect(JSON.parse(String(init?.body))).toEqual({ ids: ["111"] })
        expect(result).toEqual(responseBody)
    })

    it("fetchChangeNotes tolerates a response without notes or errors", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }))
        expect(await fetchChangeNotes(["111"])).toEqual({ notes: {}, errors: [] })
    })
})
