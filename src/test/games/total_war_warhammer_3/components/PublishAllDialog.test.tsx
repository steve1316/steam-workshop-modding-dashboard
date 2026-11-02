import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import PublishAllDialog from "@/games/total_war_warhammer_3/components/PublishAllDialog"

/**
 * Controllable EventSource stand-in. Captures the most recent instance so tests can fire named events into the dialog
 * exactly as the backend SSE stream would.
 */
class MockEventSource {
    static instances: MockEventSource[] = []
    url: string
    listeners: Record<string, ((evt: MessageEvent) => void)[]> = {}
    onmessage: ((evt: MessageEvent) => void) | null = null
    onerror: (() => void) | null = null
    readyState = 1

    constructor(url: string) {
        this.url = url
        MockEventSource.instances.push(this)
    }

    addEventListener(type: string, fn: (evt: MessageEvent) => void) {
        ;(this.listeners[type] ||= []).push(fn)
    }

    removeEventListener(type: string, fn: (evt: MessageEvent) => void) {
        this.listeners[type] = (this.listeners[type] ?? []).filter((f) => f !== fn)
    }

    fire(type: string, data: unknown) {
        const evt = { data: JSON.stringify(data) } as MessageEvent
        if (type === "message" && this.onmessage) this.onmessage(evt)
        for (const fn of this.listeners[type] ?? []) fn(evt)
    }

    close() {
        this.readyState = 2
    }
}

const ORIGINAL_EVENT_SOURCE = (globalThis as unknown as { EventSource: typeof EventSource }).EventSource

const NOTES = {
    notes: {
        "111": { note: "Note Alpha", pending: true, kind: "compat" },
        "222": { note: "Note Beta", pending: true, kind: "compat" },
    },
    errors: [],
}

const BATCH = { batch_id: "batch-1", started_at: "2026-05-27T00:00:00Z", queued: 2, skipped: [] }

/**
 * Answer the change-notes request with `notes` and every other request with the batch handle.
 *
 * @param notes JSON body returned for `/packs/change-notes`.
 * @returns The fetch spy.
 */
const mockFetch = (notes: unknown = NOTES) =>
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => new Response(JSON.stringify(String(input).includes("/packs/change-notes") ? notes : BATCH), { status: 200 }))

/**
 * Read the JSON body the dialog POSTed to `/packs/publish-all`.
 *
 * @returns The parsed body, or null when no publish-all request was made.
 */
const publishAllBody = () => {
    const call = vi.mocked(globalThis.fetch).mock.calls.find(([url]) => String(url).includes("/packs/publish-all"))
    return call ? JSON.parse(String((call[1] as RequestInit).body)) : null
}

/** Wait until the generated notes have arrived and Publish All is clickable. */
const waitForNotes = () => waitFor(() => expect(screen.getByRole("button", { name: /publish all/i })).not.toBeDisabled())

beforeEach(() => {
    MockEventSource.instances.length = 0
    ;(globalThis as unknown as { EventSource: typeof MockEventSource }).EventSource = MockEventSource
    mockFetch()
})

afterEach(() => {
    ;(globalThis as unknown as { EventSource: typeof EventSource }).EventSource = ORIGINAL_EVENT_SOURCE
    vi.restoreAllMocks()
})

const ELIGIBLE_PACKS = [
    { title: "Mod Alpha", workshopId: "111" },
    { title: "Mod Beta", workshopId: "222" },
]

const PACKS_WITH_SKIPPED = [
    { title: "Mod Alpha", workshopId: "111" },
    { title: "Mod Beta", workshopId: "" },
]

describe("PublishAllDialog", () => {
    it("disables Publish All while the changenotes are generating", () => {
        vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>(() => {}))
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        expect(screen.getByRole("button", { name: /publish all/i })).toBeDisabled()
        expect(screen.getAllByText("Generating...")).toHaveLength(2)
    })

    it("enables Publish All once every selected mod has a generated note", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    })

    it("requests notes only for mods with a workshop id", async () => {
        render(<PublishAllDialog packs={PACKS_WITH_SKIPPED} onClose={() => {}} />)
        await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
        const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0] as [string, RequestInit]
        expect(String(url)).toContain("/packs/change-notes")
        expect(JSON.parse(String(init.body))).toEqual({ ids: ["111"] })
    })

    it("lets the user edit a mod's note before publishing", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        fireEvent.click(screen.getByRole("button", { name: "Edit changenote for Mod Alpha" }))
        const editor = screen.getByRole("textbox", { name: "Changenote for Mod Alpha" })
        expect(editor).toHaveValue("Note Alpha")
        fireEvent.change(editor, { target: { value: "Edited" } })
        fireEvent.click(screen.getByRole("button", { name: /publish all/i }))
        await waitFor(() => expect(publishAllBody()?.items[0].changenote).toBe("Edited"))
    })

    it("starts mods with no changes since their last upload unchecked", async () => {
        mockFetch({ notes: { "111": NOTES.notes["111"], "222": { note: "x", pending: false, kind: "compat" } }, errors: [] })
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitFor(() => expect(screen.getAllByRole("checkbox")[1]).not.toBeChecked())
        expect(screen.getAllByRole("checkbox")[0]).toBeChecked()
        expect(screen.getByRole("button", { name: "Edit changenote for Mod Beta" })).toHaveTextContent("No changes")
    })

    it("keeps the generated note for an unchanged row so re-checking it enables Publish All and sends that note", async () => {
        mockFetch({ notes: { "111": NOTES.notes["111"], "222": { note: "Beta unchanged note", pending: false, kind: "compat" } }, errors: [] })
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitFor(() => expect(screen.getAllByRole("checkbox")[1]).not.toBeChecked())

        fireEvent.click(screen.getAllByRole("checkbox")[1])
        expect(screen.getByRole("button", { name: /publish all/i })).not.toBeDisabled()

        fireEvent.click(screen.getByRole("button", { name: /publish all/i }))
        await waitFor(() => {
            const body = publishAllBody()
            expect(body?.items).toContainEqual({ workshop_id: "222", title: "Mod Beta", changenote: "Beta unchanged note" })
        })
    })

    it("opens an empty editor and blocks publishing when a note could not be generated", async () => {
        mockFetch({ notes: { "111": NOTES.notes["111"], "222": null }, errors: ["helper_scripts path is not configured"] })
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        expect(await screen.findByText(/helper_scripts path is not configured/)).toBeInTheDocument()
        const editor = screen.getByRole("textbox", { name: "Changenote for Mod Beta" })
        expect(editor).toHaveValue("")
        expect(screen.getByRole("button", { name: /publish all/i })).toBeDisabled()
        fireEvent.change(editor, { target: { value: "manual note" } })
        expect(screen.getByRole("button", { name: /publish all/i })).not.toBeDisabled()
    })

    it("lists eligible mods and tags pre-skipped entries with no workshopId", () => {
        render(<PublishAllDialog packs={PACKS_WITH_SKIPPED} onClose={() => {}} />)
        expect(screen.getByText(/Mod Alpha/)).toBeInTheDocument()
        expect(screen.getByText(/Mod Beta/)).toBeInTheDocument()
        // The empty-workshopId entry should carry a skipped badge.
        expect(screen.getByText(/skipped/i)).toBeInTheDocument()
        // Header should reflect the eligible count (1 out of 2).
        expect(screen.getByText(/1 mod/i)).toBeInTheDocument()
    })

    it("POSTs to /packs/publish-all and opens an EventSource on the returned batch_id", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        fireEvent.click(screen.getByRole("button", { name: /publish all/i }))

        await waitFor(() => {
            const body = publishAllBody()
            expect(body).not.toBeNull()
            expect(body.changenote).toBeUndefined()
            expect(body.items).toEqual([
                { workshop_id: "111", title: "Mod Alpha", changenote: "Note Alpha" },
                { workshop_id: "222", title: "Mod Beta", changenote: "Note Beta" },
            ])
        })

        await waitFor(() => expect(MockEventSource.instances.length).toBe(1))
        expect(MockEventSource.instances[0].url).toContain("/packs/publish-all/stream/batch-1")
    })

    it("flips a row from pending to publishing to done as mod_started and mod_finished events arrive", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        fireEvent.click(screen.getByRole("button", { name: /publish all/i }))
        await waitFor(() => expect(MockEventSource.instances.length).toBe(1))
        const es = MockEventSource.instances[0]

        act(() => {
            es.fire("batch_started", { batch_id: "batch-1", total: 2, items: [] })
            es.fire("mod_started", { workshop_id: "111", title: "Mod Alpha", index: 1, total: 2, started_at: "t" })
        })
        expect(screen.getByText(/publishing/i)).toBeInTheDocument()

        act(() => {
            es.fire("log_line", { workshop_id: "111", line: "uploading...", ts: "t" })
        })
        expect(screen.getByText(/uploading.../)).toBeInTheDocument()

        act(() => {
            es.fire("mod_finished", { workshop_id: "111", exit_code: 0, duration_seconds: 1.2, status: "done", error: null })
        })
        // Row should now show a "done" badge for Mod Alpha (look for "done" text near Mod Alpha row).
        const doneBadges = screen.getAllByText(/done/i)
        expect(doneBadges.length).toBeGreaterThan(0)
    })

    it("marks a row failed when mod_finished reports a non-zero exit and still updates the next mod_started", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        fireEvent.click(screen.getByRole("button", { name: /publish all/i }))
        await waitFor(() => expect(MockEventSource.instances.length).toBe(1))
        const es = MockEventSource.instances[0]

        act(() => {
            es.fire("batch_started", { batch_id: "batch-1", total: 2, items: [] })
            es.fire("mod_started", { workshop_id: "111", title: "Mod Alpha", index: 1, total: 2, started_at: "t" })
            es.fire("mod_finished", {
                workshop_id: "111",
                exit_code: 1,
                duration_seconds: 0.5,
                status: "failed",
                error: "SteamCMD exit code 1",
            })
        })
        expect(screen.getByText(/failed/i)).toBeInTheDocument()

        act(() => {
            es.fire("mod_started", { workshop_id: "222", title: "Mod Beta", index: 2, total: 2, started_at: "t" })
        })
        // Beta row should now indicate publishing.
        expect(screen.getByText(/publishing/i)).toBeInTheDocument()
    })

    it("renders a checked checkbox for every eligible mod and no checkbox for pre-skipped rows", () => {
        render(<PublishAllDialog packs={PACKS_WITH_SKIPPED} onClose={() => {}} />)
        const checkboxes = screen.getAllByRole("checkbox")
        // One eligible mod (Alpha) -> one checkbox; the empty-workshopId Beta row has no checkbox.
        expect(checkboxes).toHaveLength(1)
        expect(checkboxes[0]).toBeChecked()
    })

    it("excludes deselected mods from the POST body and the count text", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        const checkboxes = screen.getAllByRole("checkbox")
        expect(checkboxes).toHaveLength(2)
        fireEvent.click(checkboxes[1])
        expect(screen.getByText(/1 mod/i)).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /publish all/i }))
        await waitFor(() => expect(publishAllBody()?.items).toEqual([{ workshop_id: "111", title: "Mod Alpha", changenote: "Note Alpha" }]))
    })

    it("disables Publish All when every eligible row is deselected", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        const checkboxes = screen.getAllByRole("checkbox")
        fireEvent.click(checkboxes[0])
        fireEvent.click(checkboxes[1])
        expect(screen.getByRole("button", { name: /publish all/i })).toBeDisabled()
    })

    it("marks deselected eligible rows as skipped once the batch starts", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        const checkboxes = screen.getAllByRole("checkbox")
        fireEvent.click(checkboxes[1])
        fireEvent.click(screen.getByRole("button", { name: /publish all/i }))
        await waitFor(() => expect(MockEventSource.instances.length).toBe(1))
        // Beta should now show a skipped badge with the "not selected" reason.
        expect(screen.getByText(/not selected/i)).toBeInTheDocument()
    })

    it("enables Close once batch_done arrives", async () => {
        render(<PublishAllDialog packs={ELIGIBLE_PACKS} onClose={() => {}} />)
        await waitForNotes()
        fireEvent.click(screen.getByRole("button", { name: /publish all/i }))
        await waitFor(() => expect(MockEventSource.instances.length).toBe(1))
        const es = MockEventSource.instances[0]

        // While running, both the header X and the footer Close are disabled.
        const closeButtons = screen.getAllByRole("button", { name: /^close$/i })
        expect(closeButtons).toHaveLength(2)
        for (const button of closeButtons) expect(button).toBeDisabled()

        act(() => {
            es.fire("batch_started", { batch_id: "batch-1", total: 2, items: [] })
            es.fire("batch_done", { batch_id: "batch-1", succeeded: 2, failed: 0, duration_seconds: 3.0 })
        })

        for (const button of screen.getAllByRole("button", { name: /^close$/i })) expect(button).not.toBeDisabled()
    })
})
