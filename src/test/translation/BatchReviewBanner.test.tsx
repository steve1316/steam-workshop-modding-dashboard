import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { BatchReviewBanner } from "@/translation/BatchReviewBanner"

describe("BatchReviewBanner", () => {
    it("shows the finished batch and wires its three actions", async () => {
        const onReview = vi.fn()
        const onContinue = vi.fn()
        const onCancel = vi.fn()
        render(<BatchReviewBanner batchIndex={1} totalBatches={4} onReview={onReview} onContinue={onContinue} onCancel={onCancel} />)
        expect(screen.getByText("Batch 2 of 4 complete.")).toBeInTheDocument()
        await userEvent.click(screen.getByRole("button", { name: "Review Suggestions" }))
        await userEvent.click(screen.getByRole("button", { name: "Continue" }))
        await userEvent.click(screen.getByRole("button", { name: "Cancel" }))
        expect(onReview).toHaveBeenCalledTimes(1)
        expect(onContinue).toHaveBeenCalledTimes(1)
        expect(onCancel).toHaveBeenCalledTimes(1)
    })
})
