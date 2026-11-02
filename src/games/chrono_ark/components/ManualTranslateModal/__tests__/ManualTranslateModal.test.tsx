import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import ManualTranslateModal from "@/games/chrono_ark/components/ManualTranslateModal"
import { findGlossaryMatches, findPairedRow } from "@/games/chrono_ark/components/ManualTranslateModal/matching"
import type { LocString } from "@/games/chrono_ark/lib/types"

/**
 * Build a row with sensible defaults.
 *
 * @param key The row key.
 * @param source The original text.
 * @param english The current translation.
 * @returns The row.
 */
function row(key: string, source: string, english = ""): LocString {
    return {
        key,
        type: "Text",
        desc: "",
        source,
        source_lang: "Japanese",
        english,
        is_translated: !!english,
        original_english: "",
        is_synced: false,
        is_untouched: false,
        translated_by: "",
        source_file: "LangDataDB.csv",
        untranslatable_reason: "",
    } as LocString
}

const GLOSSARY = {
    "Rosmontis's Embrace": { category: "items", key: "", source_mappings: { Japanese: "ロスモンティスの抱擁" } },
    Rosmontis: { category: "characters", key: "", source_mappings: { Japanese: "ロスモンティス" } },
}

/**
 * Render the dialog over the given rows.
 *
 * @param queue Rows to step through.
 * @param onSave Save handler.
 * @returns The render result.
 */
function renderModal(queue: LocString[], onSave = vi.fn().mockResolvedValue(true)) {
    return render(<ManualTranslateModal queue={queue} allStrings={queue} glossary={GLOSSARY} sourceLanguage="Japanese" targetLanguage="English" onSave={onSave} onClose={() => {}} />)
}

describe("ManualTranslateModal", () => {
    it("pairs name and description keys regardless of case", () => {
        const rows = [row("Item_Equip/E_mdx_0_name", "a"), row("Item_Equip/E_mdx_0_Description", "b"), row("Buff/B_0_Name", "c")]
        expect(findPairedRow("Item_Equip/E_mdx_0_name", rows)?.source).toBe("b")
        expect(findPairedRow("Item_Equip/E_mdx_0_Description", rows)?.source).toBe("a")
        expect(findPairedRow("Buff/B_0_Name", rows)).toBeUndefined()
        expect(findPairedRow("Buff/B_0_Tooltip", rows)).toBeUndefined()
    })

    it("lists glossary matches longest first", () => {
        expect(findGlossaryMatches("ロスモンティスの抱擁", GLOSSARY, "Japanese").map((m) => m.english)).toEqual(["Rosmontis's Embrace", "Rosmontis"])
        expect(findGlossaryMatches("ロスモンティスの抱擁", GLOSSARY, "Chinese")).toEqual([])
    })

    it("stays on the row and shows an error when the save fails", async () => {
        const onSave = vi.fn().mockResolvedValue(false)
        renderModal([row("A_name", "追憶"), row("B_name", "小さなうさぎ")], onSave)
        await userEvent.type(screen.getByRole("textbox"), "Reminiscence")
        await userEvent.click(screen.getByRole("button", { name: "Save & Next" }))
        expect(await screen.findByText(/Could not save this translation/)).toBeInTheDocument()
        expect(screen.getByText("1 of 2")).toBeInTheDocument()
        expect(screen.getByRole("textbox")).toHaveValue("Reminiscence")
    })

    it("skips without saving and does not re-save an unchanged row", async () => {
        const onSave = vi.fn().mockResolvedValue(true)
        renderModal([row("A_name", "追憶", "Reminiscence"), row("B_name", "小さなうさぎ")], onSave)
        await userEvent.click(screen.getByRole("button", { name: "Save & Next" }))
        await userEvent.click(screen.getByRole("button", { name: "Skip" }))
        expect(await screen.findByText(/Saved 0 of 2/)).toBeInTheDocument()
        expect(onSave).not.toHaveBeenCalled()
    })
})
