import { afterEach, describe, expect, it, vi } from "vitest"

import {
    addGlossaryTerm,
    clearTranslations,
    createSnapshot,
    deleteGlossaryTerm,
    deleteSnapshot,
    fetchBaseGlossary,
    fetchModContext,
    fetchStrings,
    glossaryApplyAll,
    glossarySuggestEdits,
    listApiResponses,
    listSnapshots,
    listTranslationMods,
    loadGlossary,
    openModFolder,
    rescanMod,
    restoreSnapshot,
    saveModContext,
    saveString,
    syncChanges,
    updateGlossaryTerm,
} from "../../../games/total_war_warhammer_3/translationApi"
import { RegistryError } from "../../../games/total_war_warhammer_3/api"

const PREFIX = "/api/games/total_war_warhammer_3/translation"

function mockFetchOk(body: unknown) {
    return vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }))
}

function mockFetchError(status: number, detail = "boom") {
    return vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ detail }), { status, headers: { "content-type": "application/json" } })))
}

afterEach(() => {
    vi.restoreAllMocks()
})

describe("translationApi", () => {
    it("listTranslationMods GETs /mods", async () => {
        const spy = mockFetchOk([{ workshop_id: "1", display_name: "x", parent_workshop_ids: [], local_source_dir: "", source_language: "Chinese", target_language: "English" }])
        const result = await listTranslationMods()
        expect(spy).toHaveBeenCalledWith(expect.stringContaining(`${PREFIX}/mods`), undefined)
        expect(result).toHaveLength(1)
        expect(result[0].workshop_id).toBe("1")
    })

    it("rescanMod POSTs /mods/{id}/rescan", async () => {
        const spy = mockFetchOk({ mod_id: "abc", counts: { translated: 1, untranslated: 2, stale: 0, orphan: 0 }, scanned_at: "2026-05-24T00:00:00Z" })
        const result = await rescanMod("abc")
        expect(spy).toHaveBeenCalledWith(expect.stringContaining(`${PREFIX}/mods/abc/rescan`), expect.objectContaining({ method: "POST" }))
        expect(result.counts.translated).toBe(1)
    })

    it("fetchStrings GETs /mods/{id}/strings without status filter", async () => {
        const spy = mockFetchOk([])
        await fetchStrings("abc")
        expect(spy).toHaveBeenCalledWith(expect.stringMatching(/\/mods\/abc\/strings$/), undefined)
    })

    it("fetchStrings appends status as a query param", async () => {
        const spy = mockFetchOk([])
        await fetchStrings("abc", "untranslated")
        expect(spy).toHaveBeenCalledWith(expect.stringContaining("status=untranslated"), undefined)
    })

    it("saveString PUTs /mods/{id}/strings/{key} with text body", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await saveString("abc", "my.key", "Hello")
        const [url, init] = spy.mock.calls[0] as [string, RequestInit]
        expect(url).toContain(`${PREFIX}/mods/abc/strings/my.key`)
        expect(init.method).toBe("PUT")
        expect(init.body).toBe(JSON.stringify({ text: "Hello" }))
    })

    it("saveString URL-encodes the key", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await saveString("abc", "weird/key with spaces", "x")
        const [url] = spy.mock.calls[0] as [string, RequestInit]
        expect(url).toContain("weird%2Fkey%20with%20spaces")
    })

    it("fetchModContext GETs /mods/{id}/mod-context", async () => {
        const spy = mockFetchOk({ source_game: "WH3", character_name: "x", background: "y" })
        const ctx = await fetchModContext("abc")
        expect(spy).toHaveBeenCalledWith(expect.stringContaining(`${PREFIX}/mods/abc/mod-context`), undefined)
        expect(ctx.character_name).toBe("x")
    })

    it("saveModContext PUTs /mods/{id}/mod-context with the ctx body", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await saveModContext("abc", { source_game: "WH3", character_name: "y", background: "z", source_language_override: null, target_language_override: null })
        const [, init] = spy.mock.calls[0] as [string, RequestInit]
        expect(init.method).toBe("PUT")
        expect(JSON.parse(init.body as string)).toEqual({ source_game: "WH3", character_name: "y", background: "z", source_language_override: null, target_language_override: null })
    })

    it("throws RegistryError when the backend returns a 4xx with a detail string", async () => {
        mockFetchError(404, "not registered")
        await expect(listTranslationMods()).rejects.toBeInstanceOf(RegistryError)
        await expect(listTranslationMods()).rejects.toMatchObject({ status: 404, detail: "not registered" })
    })
})

describe("plan3 routes", () => {
    it("syncChanges POSTs to /sync and returns per_file map", async () => {
        const spy = mockFetchOk({ per_file: { "C:\\x.loc.tsv": 2 } })
        const result = await syncChanges("123")
        expect(result.per_file["C:\\x.loc.tsv"]).toBe(2)
        expect(spy).toHaveBeenCalledWith(expect.stringContaining("/translation/mods/123/sync"), expect.objectContaining({ method: "POST" }))
    })

    it("clearTranslations POSTs to /clear-translations and returns the cleared count", async () => {
        const spy = mockFetchOk({ cleared: 7 })
        const result = await clearTranslations("123")
        expect(result.cleared).toBe(7)
        expect(spy).toHaveBeenCalledWith(expect.stringContaining("/translation/mods/123/clear-translations"), expect.objectContaining({ method: "POST" }))
    })

    it("listSnapshots returns SnapshotMeta list", async () => {
        mockFetchOk([{ ulid: "01H", created_at: "2026-05-25T00:00:00Z", label: "x", kind: "auto" }])
        const result = await listSnapshots("123")
        expect(result.length).toBe(1)
        expect(result[0].kind).toBe("auto")
    })

    it("createSnapshot POSTs label and returns new meta", async () => {
        const spy = mockFetchOk({ ulid: "01J", label: "my save", kind: "manual" })
        const result = await createSnapshot("123", "my save")
        expect(result.ulid).toBe("01J")
        const [, init] = spy.mock.calls[0]
        expect(JSON.parse((init as RequestInit).body as string)).toEqual({ label: "my save" })
    })

    it("restoreSnapshot POSTs to /restore", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await restoreSnapshot("123", "01H")
        expect(spy).toHaveBeenCalledWith(expect.stringContaining("/translation/mods/123/snapshots/01H/restore"), expect.objectContaining({ method: "POST" }))
    })

    it("deleteSnapshot DELETEs by ulid", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await deleteSnapshot("123", "01H")
        expect(spy).toHaveBeenCalledWith(expect.stringContaining("/translation/mods/123/snapshots/01H"), expect.objectContaining({ method: "DELETE" }))
    })

    it("loadGlossary GETs and returns the dict", async () => {
        mockFetchOk({ Phoenix: { source: "凤", category: "factions" } })
        const result = await loadGlossary("123")
        expect(result.Phoenix.source).toBe("凤")
    })

    it("addGlossaryTerm POSTs the entry", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await addGlossaryTerm("123", { english: "Phoenix", source: "凤", category: "factions" })
        const [, init] = spy.mock.calls[0]
        expect(JSON.parse((init as RequestInit).body as string)).toEqual({ english: "Phoenix", source: "凤", category: "factions" })
    })

    it("updateGlossaryTerm PUTs by english key", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await updateGlossaryTerm("123", "Phoenix", { english: "Phoenix Lord", source: "凤", category: "factions" })
        expect(spy).toHaveBeenCalledWith(expect.stringContaining("/translation/mods/123/glossary/Phoenix"), expect.objectContaining({ method: "PUT" }))
    })

    it("deleteGlossaryTerm DELETEs by english key", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await deleteGlossaryTerm("123", "Phoenix")
        expect(spy).toHaveBeenCalledWith(expect.stringContaining("/translation/mods/123/glossary/Phoenix"), expect.objectContaining({ method: "DELETE" }))
    })

    it("glossaryApplyAll POSTs old_english + new_english", async () => {
        const spy = mockFetchOk({ replaced: 3 })
        const result = await glossaryApplyAll("123", "Cathay Phoenix", "Cathayan Phoenix")
        expect(result.replaced).toBe(3)
        const [, init] = spy.mock.calls[0]
        expect(JSON.parse((init as RequestInit).body as string)).toEqual({ old_english: "Cathay Phoenix", new_english: "Cathayan Phoenix" })
    })

    it("glossarySuggestEdits POSTs to the game-root endpoint and returns the added count", async () => {
        const spy = mockFetchOk({ status: "success", new: 1 })
        const result = await glossarySuggestEdits("123")
        expect(result.new).toBe(1)
        expect(String(spy.mock.calls[0][0])).toMatch(/\/api\/games\/total_war_warhammer_3\/mods\/123\/glossary\/suggest-edits$/)
    })

    it("listApiResponses GETs and returns the list", async () => {
        mockFetchOk([
            {
                timestamp: "2026-05-25T00:00:00Z",
                kind: "translate-batch",
                provider: "claude",
                model: "claude",
                input_tokens: null,
                output_tokens: null,
                cost_usd: null,
                keys_or_inputs: ["k1"],
                raw_response: "{}",
            },
        ])
        const result = await listApiResponses("123")
        expect(result[0].kind).toBe("translate-batch")
    })

    it("openModFolder POSTs to /open-folder", async () => {
        const spy = mockFetchOk({ status: "ok" })
        await openModFolder("123")
        expect(spy).toHaveBeenCalledWith(expect.stringContaining("/translation/mods/123/open-folder"), expect.objectContaining({ method: "POST" }))
    })

    it("fetchBaseGlossary GETs /glossary", async () => {
        const spy = mockFetchOk({ terms: { Armour: { english: "Armour", category: "stats", key: "k", source_mappings: { Chinese: "护甲" } } } })
        const result = await fetchBaseGlossary()
        expect(spy).toHaveBeenCalledWith(expect.stringContaining(`${PREFIX}/glossary`), undefined)
        expect(result.terms.Armour.category).toBe("stats")
    })
})
