import { render, screen, fireEvent } from "@/testUtils"
import { FeedbackBanner } from "@/components/TranslationPage/FeedbackBanner"

describe("FeedbackBanner", () => {
    it("renders the message", () => {
        render(<FeedbackBanner type="success" message="Translated 5 strings." onDismiss={vi.fn()} />)
        expect(screen.getByText("Translated 5 strings.")).toBeInTheDocument()
    })

    it("calls onDismiss when the close button is clicked", () => {
        const onDismiss = vi.fn()
        render(<FeedbackBanner type="error" message="Translation failed" onDismiss={onDismiss} />)
        fireEvent.click(screen.getByRole("button", { name: /dismiss/i }))
        expect(onDismiss).toHaveBeenCalledTimes(1)
    })

    it("uses the success tone for success and the error tone for error", () => {
        const { rerender } = render(<FeedbackBanner type="success" message="ok" onDismiss={vi.fn()} />)
        expect(screen.getByText("ok").closest(".banner")).toHaveClass("banner-success")
        rerender(<FeedbackBanner type="error" message="bad" onDismiss={vi.fn()} />)
        expect(screen.getByText("bad").closest(".banner")).toHaveClass("banner-error")
    })
})
