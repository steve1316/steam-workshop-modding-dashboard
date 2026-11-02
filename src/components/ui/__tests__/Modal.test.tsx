import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import Modal from "@/components/ui/Modal"

describe("Modal", () => {
    it("renders a labelled dialog into document.body", () => {
        const { container } = render(
            <Modal title="History" onClose={vi.fn()}>
                body
            </Modal>
        )
        const dialog = screen.getByRole("dialog", { name: "History" })
        expect(dialog).toHaveAttribute("aria-modal", "true")
        expect(container).not.toContainElement(dialog)
    })

    it("applies the size class, defaulting to md", () => {
        const { rerender } = render(
            <Modal title="A" onClose={vi.fn()}>
                x
            </Modal>
        )
        expect(screen.getByRole("dialog")).toHaveClass("dialog-md")
        rerender(
            <Modal title="A" size="xl" fill onClose={vi.fn()}>
                x
            </Modal>
        )
        expect(screen.getByRole("dialog")).toHaveClass("dialog-xl", "dialog-fill")
    })

    it("closes on the X button, Escape, and a backdrop click", async () => {
        const onClose = vi.fn()
        render(
            <Modal title="A" onClose={onClose}>
                x
            </Modal>
        )
        await userEvent.click(screen.getByRole("button", { name: "Close" }))
        await userEvent.keyboard("{Escape}")
        const backdrop = screen.getByRole("dialog").parentElement as HTMLElement
        fireEvent.mouseDown(backdrop)
        fireEvent.click(backdrop)
        expect(onClose).toHaveBeenCalledTimes(3)
    })

    it("does not close when a press starts inside the panel and ends on the backdrop", () => {
        const onClose = vi.fn()
        render(
            <Modal title="A" onClose={onClose}>
                <p>selectable text</p>
            </Modal>
        )
        const backdrop = screen.getByRole("dialog").parentElement as HTMLElement
        fireEvent.mouseDown(screen.getByText("selectable text"))
        fireEvent.click(backdrop)
        expect(onClose).not.toHaveBeenCalled()
    })

    it("ignores every close path while closeDisabled is set", async () => {
        const onClose = vi.fn()
        render(
            <Modal title="Publishing" onClose={onClose} closeDisabled closeDisabledReason="Publish in progress">
                x
            </Modal>
        )
        const close = screen.getByRole("button", { name: "Close" })
        expect(close).toBeDisabled()
        expect(close).toHaveAttribute("title", "Publish in progress")
        await userEvent.keyboard("{Escape}")
        const backdrop = screen.getByRole("dialog").parentElement as HTMLElement
        fireEvent.mouseDown(backdrop)
        fireEvent.click(backdrop)
        expect(onClose).not.toHaveBeenCalled()
    })

    it("closes only the topmost dialog on Escape when dialogs are nested", async () => {
        const outerClose = vi.fn()
        const innerClose = vi.fn()
        render(
            <Modal title="Outer" onClose={outerClose}>
                <Modal title="Inner" onClose={innerClose}>
                    y
                </Modal>
            </Modal>
        )
        await userEvent.keyboard("{Escape}")
        expect(innerClose).toHaveBeenCalledTimes(1)
        expect(outerClose).not.toHaveBeenCalled()
    })

    it("stacks a nested dialog above its parent so the one Escape closes is the one on top", () => {
        render(
            <Modal title="Outer" onClose={vi.fn()}>
                <Modal title="Inner" onClose={vi.fn()}>
                    y
                </Modal>
            </Modal>
        )
        const outer = screen.getByRole("dialog", { name: "Outer" }).parentElement as HTMLElement
        const inner = screen.getByRole("dialog", { name: "Inner" }).parentElement as HTMLElement
        expect(Number(inner.style.zIndex)).toBeGreaterThan(Number(outer.style.zIndex))
    })

    it("ignores Escape while an IME composition is in progress", () => {
        const onClose = vi.fn()
        render(
            <Modal title="A" onClose={onClose}>
                <input aria-label="source" />
            </Modal>
        )
        fireEvent.keyDown(screen.getByLabelText("source"), { key: "Escape", isComposing: true })
        expect(onClose).not.toHaveBeenCalled()
    })

    it("stacks a dialog opened from the footer above its parent", () => {
        render(
            <Modal
                title="Outer"
                onClose={vi.fn()}
                footer={
                    <Modal title="Inner" onClose={vi.fn()}>
                        y
                    </Modal>
                }
            >
                x
            </Modal>
        )
        const outer = screen.getByRole("dialog", { name: "Outer" }).parentElement as HTMLElement
        const inner = screen.getByRole("dialog", { name: "Inner" }).parentElement as HTMLElement
        expect(Number(inner.style.zIndex)).toBeGreaterThan(Number(outer.style.zIndex))
    })

    it("renders the subtitle, header actions and footer slots", () => {
        render(
            <Modal title="Suggested terms" subtitle="Batch 1 of 3" headerActions={<button>Apply all</button>} footer={<button>Done</button>} onClose={vi.fn()}>
                x
            </Modal>
        )
        expect(screen.getByText("Batch 1 of 3")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Apply all" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Done" }).closest(".dialog-footer")).not.toBeNull()
    })
})
