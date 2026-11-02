import { render, screen, withActiveGame } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import SettingsPage from "@/pages/Settings"
import "@/games/chrono_ark"
import "@/games/total_war_warhammer_3"

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

const SETTINGS = {
    provider: "claude",
    batch_size: 50,
    anthropic_api_key_set: "sk-...abcd",
    openai_api_key_set: "",
    deepl_api_key_set: "",
    ignored_mods: ["2945863327"],
    tw3_helper_path: "C:/helper",
    steam_username: "someone",
    claude_model: "claude-sonnet-5",
}

/**
 * Answers every request the Settings page makes. `/settings` comes from `settings()`, `overrides` win for their URL suffix, and the rest get
 * small fixed bodies.
 *
 * @param settings Produces the `/settings` response for each call.
 * @param overrides Responses keyed by URL suffix, checked first.
 * @returns The fetch spy.
 */
function mockSettingsFetch(settings: () => Promise<Response> = () => Promise.resolve(json(SETTINGS)), overrides: Record<string, () => Promise<Response>> = {}) {
    return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
        const url = String(input)
        for (const [suffix, respond] of Object.entries(overrides)) if (url.endsWith(suffix)) return respond()
        if (url.endsWith("/settings")) return settings()
        if (url.endsWith("/models/claude")) return Promise.resolve(json({ models: [{ id: "claude-sonnet-5", label: "Sonnet 5", input_per_mtok: 3, output_per_mtok: 15 }] }))
        if (url.endsWith("/models/openai")) return Promise.resolve(json({ models: [] }))
        if (url.endsWith("/ollama/status")) return Promise.resolve(json({ status: "not_installed", models: [], managed: false }))
        if (url.endsWith("/llamacpp/models")) return Promise.resolve(json({ models: [] }))
        if (url.endsWith("/llamacpp/status")) return Promise.resolve(json({ status: "unknown", installed: false }))
        return Promise.resolve(json({}))
    })
}

afterEach(() => {
    vi.restoreAllMocks()
})

describe("SettingsPage", () => {
    it("shows a loading state, then every Claude-provider panel as a static settings panel", async () => {
        mockSettingsFetch()
        render(withActiveGame("chrono_ark", <SettingsPage />))
        expect(screen.getByText("Loading settings...")).toBeInTheDocument()
        for (const name of ["System Prompt Preview", "Translation Provider", "Model", "API Keys", "Batch Size", "Ignored Mods", "Total War: Warhammer III", "Steam Account"]) {
            const heading = await screen.findByRole("heading", { name })
            expect(heading.closest(".panel.settings-panel")).not.toBeNull()
        }
    })

    it("shows an error with Retry instead of default values when settings fail to load, and Retry loads them", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {})
        let calls = 0
        mockSettingsFetch(() => Promise.resolve(++calls === 1 ? json({ detail: "boom" }, 500) : json(SETTINGS)))
        render(withActiveGame("chrono_ark", <SettingsPage />))
        expect(await screen.findByRole("alert")).toHaveTextContent("Could not load settings")
        expect(screen.queryByRole("button", { name: "Save Settings" })).not.toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByRole("heading", { name: "Translation Provider" })).toBeInTheDocument()
    })

    it("links every always-visible settings field to its label", async () => {
        mockSettingsFetch()
        render(withActiveGame("chrono_ark", <SettingsPage />))
        await screen.findByRole("heading", { name: "Translation Provider" })
        for (const label of [
            "Source Language",
            "Model",
            "Claude API Key",
            "OpenAI API Key",
            "DeepL API Key",
            "Batch size",
            "Workshop mod ID",
            "helper_scripts directory",
            "rpfm_cli.exe path (optional, defaults to helper_scripts/rpfm_cli.exe)",
            "Steam library drive (e.g., F:)",
            "SteamCMD path (steamcmd.exe)",
            "Steam username",
        ]) {
            expect(screen.getByLabelText(label)).toBeInTheDocument()
        }
        expect(screen.getByLabelText("helper_scripts directory")).toHaveValue("C:/helper")
    })

    it("links the llama.cpp advanced fields to their labels", async () => {
        mockSettingsFetch(() => Promise.resolve(json({ ...SETTINGS, provider: "llamacpp" })))
        render(withActiveGame("chrono_ark", <SettingsPage />))
        await userEvent.click(await screen.findByRole("button", { name: "Advanced Settings" }))
        for (const label of ["Model Path (override)", "GPU Layers", "Context Size", "Server URL", "Binary Path", "Display Name"]) {
            expect(screen.getByLabelText(label)).toBeInTheDocument()
        }
    })

    it("links the Ollama URL field to its label", async () => {
        mockSettingsFetch(() => Promise.resolve(json({ ...SETTINGS, provider: "ollama" })))
        render(withActiveGame("chrono_ark", <SettingsPage />))
        await userEvent.click(await screen.findByRole("button", { name: "Advanced Settings" }))
        expect(screen.getByLabelText("Ollama URL")).toHaveValue("http://localhost:11434")
    })

    it("uses the danger button to stop a managed Ollama server", async () => {
        mockSettingsFetch(() => Promise.resolve(json({ ...SETTINGS, provider: "ollama" })), {
            "/ollama/status": () => Promise.resolve(json({ status: "running", models: [{ name: "qwen2.5:7b" }], managed: true })),
        })
        render(withActiveGame("chrono_ark", <SettingsPage />))
        expect(await screen.findByRole("button", { name: "Stop" })).toHaveClass("btn", "btn-danger", "btn-sm")
    })

    it("reports whether the advanced settings are expanded", async () => {
        mockSettingsFetch(() => Promise.resolve(json({ ...SETTINGS, provider: "ollama" })))
        render(withActiveGame("chrono_ark", <SettingsPage />))
        const toggle = await screen.findByRole("button", { name: "Advanced Settings" })
        expect(toggle).toHaveAttribute("aria-expanded", "false")
        await userEvent.click(toggle)
        expect(toggle).toHaveAttribute("aria-expanded", "true")
    })

    it("removes an ignored mod from its chip, which enables Save", async () => {
        mockSettingsFetch()
        render(withActiveGame("chrono_ark", <SettingsPage />))
        const remove = await screen.findByRole("button", { name: "Remove 2945863327" })
        expect(remove.closest(".chip")).not.toBeNull()
        expect(screen.getByRole("button", { name: "Save Settings" })).toBeDisabled()
        await userEvent.click(remove)
        expect(screen.queryByText("2945863327")).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Save Settings" })).toBeEnabled()
    })

    it("shows a failed SteamCMD install in an error banner", async () => {
        mockSettingsFetch(undefined, { "/steamcmd/install": () => Promise.resolve(json({ detail: "no network" }, 500)) })
        render(withActiveGame("chrono_ark", <SettingsPage />))
        await userEvent.click(await screen.findByRole("button", { name: "Install SteamCMD" }))
        expect((await screen.findByText("Install failed: no network")).closest(".banner-error")).not.toBeNull()
    })

    it("reloads the model list on Retry, so the Model dropdown is filled once the backend is back", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {})
        let settingsCalls = 0
        let modelCalls = 0
        mockSettingsFetch(() => Promise.resolve(++settingsCalls === 1 ? json({ detail: "down" }, 500) : json(SETTINGS)), {
            "/models/claude": () =>
                ++modelCalls === 1
                    ? Promise.reject(new TypeError("Failed to fetch"))
                    : Promise.resolve(json({ models: [{ id: "claude-sonnet-5", label: "Sonnet 5", input_per_mtok: 3, output_per_mtok: 15 }] })),
        })
        render(withActiveGame("chrono_ark", <SettingsPage />))
        await userEvent.click(await screen.findByRole("button", { name: "Retry" }))
        expect(await screen.findByRole("option", { name: /Sonnet 5/ })).toBeInTheDocument()
    })

    it("shows a failed save in an error banner", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {})
        let rejectSave = false
        mockSettingsFetch(() => Promise.resolve(rejectSave ? json({ detail: "batch size too large" }, 400) : json(SETTINGS)))
        render(withActiveGame("chrono_ark", <SettingsPage />))
        const batch = await screen.findByLabelText("Batch size")
        rejectSave = true
        await userEvent.clear(batch)
        await userEvent.type(batch, "60")
        await userEvent.click(screen.getByRole("button", { name: "Save Settings" }))
        expect((await screen.findByText("Could not save settings: batch size too large")).closest(".banner-error")).not.toBeNull()
    })

    it("loads the Warhammer III system prompt when Settings is in WH3", async () => {
        const fetchSpy = mockSettingsFetch(undefined, { "/translate/system-prompt?source_lang=Chinese": () => Promise.resolve(json({ system_prompt: "WH3 PROMPT" })) })
        render(withActiveGame("total_war_warhammer_3", <SettingsPage />))
        await userEvent.click(await screen.findByRole("button", { name: "Load Prompt" }))
        expect(await screen.findByText("WH3 PROMPT")).toBeInTheDocument()
        expect(fetchSpy.mock.calls.some(([url]) => String(url).includes("/games/total_war_warhammer_3/translate/system-prompt"))).toBe(true)
        expect(fetchSpy.mock.calls.some(([url]) => String(url).includes("/games/chrono_ark/translate/system-prompt"))).toBe(false)
    })

    it("loads the Chrono Ark system prompt when Settings is in Chrono Ark", async () => {
        const fetchSpy = mockSettingsFetch(undefined, { "/translate/system-prompt?source_lang=Chinese": () => Promise.resolve(json({ system_prompt: "CA PROMPT" })) })
        render(withActiveGame("chrono_ark", <SettingsPage />))
        await userEvent.click(await screen.findByRole("button", { name: "Load Prompt" }))
        expect(await screen.findByText("CA PROMPT")).toBeInTheDocument()
        expect(fetchSpy.mock.calls.some(([url]) => String(url).includes("/games/chrono_ark/translate/system-prompt"))).toBe(true)
    })

    it("turns Load Prompt into Unload Prompt, which closes the prompt", async () => {
        mockSettingsFetch(undefined, { "/translate/system-prompt?source_lang=Chinese": () => Promise.resolve(json({ system_prompt: "CA PROMPT" })) })
        render(withActiveGame("chrono_ark", <SettingsPage />))
        await userEvent.click(await screen.findByRole("button", { name: "Load Prompt" }))
        expect(await screen.findByText("CA PROMPT")).toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Unload Prompt" }))
        expect(screen.queryByText("CA PROMPT")).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Load Prompt" })).toBeInTheDocument()
    })
})
