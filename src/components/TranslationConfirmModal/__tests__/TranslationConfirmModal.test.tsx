import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import TranslationConfirmModal, { type TranslationPreview } from "@/components/TranslationConfirmModal"

const PREVIEW: TranslationPreview = {
    total_strings: 152,
    total_batches: 2,
    batch_size: 80,
    provider: "claude",
    previews: { English: { system_prompt: "system", user_messages: ["user"], strings_in_language: 152, batches: 2 } },
}

describe("TranslationConfirmModal", () => {
    it("keeps Cancel and Translate in the pinned dialog footer so a tall prompt cannot push them out of view", () => {
        render(<TranslationConfirmModal preview={PREVIEW} onConfirm={vi.fn()} onCancel={vi.fn()} />)
        expect(screen.getByRole("button", { name: "Translate 152 strings" }).closest(".dialog-footer")).not.toBeNull()
        expect(screen.getByRole("button", { name: "Cancel" }).closest(".dialog-footer")).not.toBeNull()
    })
})
