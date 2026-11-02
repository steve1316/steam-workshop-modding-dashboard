import { render, screen, waitFor } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { describe, expect, it } from "vitest"

import { useConfirm } from "@/hooks/useConfirm"

/**
 * Test harness: a button that asks for confirmation and prints the answer.
 *
 * @returns The harness element.
 */
function Harness() {
    const { confirm, confirmDialog } = useConfirm()
    const [answer, setAnswer] = useState("none")
    return (
        <>
            <button onClick={async () => setAnswer(String(await confirm({ title: "Clear English", message: "Clear all?", confirmLabel: "Clear", variant: "danger" })))}>ask</button>
            <span data-testid="answer">{answer}</span>
            {confirmDialog}
        </>
    )
}

describe("useConfirm", () => {
    it("resolves true when the user confirms", async () => {
        render(<Harness />)
        await userEvent.click(screen.getByRole("button", { name: "ask" }))
        expect(screen.getByRole("dialog", { name: "Clear English" })).toHaveTextContent("Clear all?")
        await userEvent.click(screen.getByRole("button", { name: "Clear" }))
        expect(screen.getByTestId("answer")).toHaveTextContent("true")
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })

    it("resolves false when the user cancels", async () => {
        render(<Harness />)
        await userEvent.click(screen.getByRole("button", { name: "ask" }))
        await userEvent.click(screen.getByRole("button", { name: "Cancel" }))
        expect(screen.getByTestId("answer")).toHaveTextContent("false")
    })

    it("styles a danger confirm with the btn-danger class", async () => {
        render(<Harness />)
        await userEvent.click(screen.getByRole("button", { name: "ask" }))
        expect(screen.getByRole("button", { name: "Clear" })).toHaveClass("btn-danger")
    })

    it("settles a pending confirm to false when the owner unmounts", async () => {
        let settled: boolean | undefined
        /**
         * Harness that records the answer outside React so it survives unmount.
         *
         * @returns The harness element.
         */
        function Recorder() {
            const { confirm, confirmDialog } = useConfirm()
            return (
                <>
                    <button onClick={async () => (settled = await confirm({ title: "T", message: "M" }))}>ask</button>
                    {confirmDialog}
                </>
            )
        }
        const { unmount } = render(<Recorder />)
        await userEvent.click(screen.getByRole("button", { name: "ask" }))
        unmount()
        await waitFor(() => expect(settled).toBe(false))
    })
})
