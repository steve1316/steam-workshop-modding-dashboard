import { render, screen, fireEvent } from "@testing-library/react"
import { TranslatingBanner } from "@/translation/TranslatingBanner"

describe("TranslatingBanner", () => {
    it("renders a 1-based batch progress message", () => {
        render(<TranslatingBanner batchIndex={0} totalBatches={3} onCancel={vi.fn()} />)
        expect(screen.getByText(/Translating batch 1 of 3/)).toBeInTheDocument()
    })

    it("shows 'waiting for provider response' when not streaming", () => {
        render(<TranslatingBanner batchIndex={1} totalBatches={2} onCancel={vi.fn()} />)
        expect(screen.getByText(/waiting for provider response/)).toBeInTheDocument()
    })

    it("shows token throughput stats when streaming", () => {
        render(<TranslatingBanner batchIndex={0} totalBatches={1} streaming={{ tokensGenerated: 120, tokensPerSec: 40, elapsedSec: 3 }} onCancel={vi.fn()} />)
        expect(screen.getByText(/120 tokens \(40 tok\/s, 3s elapsed\)/)).toBeInTheDocument()
    })

    it("calls onCancel when Cancel is clicked", () => {
        const onCancel = vi.fn()
        render(<TranslatingBanner batchIndex={0} totalBatches={1} onCancel={onCancel} />)
        fireEvent.click(screen.getByRole("button", { name: /cancel/i }))
        expect(onCancel).toHaveBeenCalledTimes(1)
    })
})
