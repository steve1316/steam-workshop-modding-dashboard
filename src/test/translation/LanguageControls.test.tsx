import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { LanguageControls } from "@/translation/LanguageControls"

describe("LanguageControls", () => {
    it("labels the source select and reports changes", async () => {
        const onSourceChange = vi.fn()
        render(<LanguageControls source="Chinese" target="Chinese" onSourceChange={onSourceChange} onTargetChange={vi.fn()} />)
        const select = screen.getByLabelText(/Source Language/) as HTMLSelectElement
        expect(select.value).toBe("Chinese")
        await userEvent.selectOptions(select, "Korean")
        expect(onSourceChange).toHaveBeenCalledWith("Korean")
    })

    it("shows the target select only when the source is English", async () => {
        const onTargetChange = vi.fn()
        const { rerender } = render(<LanguageControls source="Chinese" target="Chinese" onSourceChange={vi.fn()} onTargetChange={onTargetChange} />)
        expect(screen.queryByLabelText("Target Language")).not.toBeInTheDocument()
        rerender(<LanguageControls source="English" target="Chinese" onSourceChange={vi.fn()} onTargetChange={onTargetChange} />)
        await userEvent.selectOptions(screen.getByLabelText("Target Language"), "Japanese")
        expect(onTargetChange).toHaveBeenCalledWith("Japanese")
    })
})
