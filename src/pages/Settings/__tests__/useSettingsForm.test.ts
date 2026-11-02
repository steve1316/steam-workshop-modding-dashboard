import { describe, expect, it } from "vitest"

import { DEFAULT_FORM, diffSettings, formFromResponse } from "@/pages/Settings/useSettingsForm"
import "@/games/total_war_warhammer_3"

describe("formFromResponse", () => {
    it("falls back to the default for missing or blank fields and never fills an API key", () => {
        const form = formFromResponse({ provider: "ollama", batch_size: 25, ollama_base_url: "", anthropic_api_key_set: "sk-...abcd", tw3_helper_path: "C:/helper" })
        expect(form.provider).toBe("ollama")
        expect(form.batch_size).toBe(25)
        expect(form.ollama_base_url).toBe(DEFAULT_FORM.ollama_base_url)
        expect(form.llamacpp_gpu_layers).toBe(-1)
        expect(form.anthropic_api_key).toBe("")
        expect(form.game.tw3_helper_path).toBe("C:/helper")
    })
})

describe("diffSettings", () => {
    it("returns only the changed fields, with game values flattened to their backend keys", () => {
        const saved = { ...DEFAULT_FORM, ignored_mods: ["1"], game: { tw3_helper_path: "C:/a", steam_username: "me" } }
        const draft = { ...saved, batch_size: 50, ignored_mods: ["1", "2"], deepl_api_key: "key", game: { ...saved.game, tw3_helper_path: "C:/b" } }
        expect(diffSettings(draft, saved)).toEqual({ batch_size: 50, ignored_mods: ["1", "2"], deepl_api_key: "key", tw3_helper_path: "C:/b" })
    })

    it("is empty when every field is back to its saved value", () => {
        expect(diffSettings({ ...DEFAULT_FORM, ignored_mods: [] }, DEFAULT_FORM)).toEqual({})
    })
})
