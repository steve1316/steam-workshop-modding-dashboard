import Banner from "@/ui/Banner"

/** Props for FeedbackBanner. */
interface FeedbackBannerProps {
    type: "success" | "error"
    /** Message text, with whitespace preserved. */
    message: string
    onDismiss: () => void
}

/**
 * Dismissible success or error banner, a thin wrapper over `Banner`.
 * @param type - Success or error tone.
 * @param message - Message text.
 * @param onDismiss - Close handler.
 * @returns The banner.
 */
export function FeedbackBanner({ type, message, onDismiss }: FeedbackBannerProps) {
    return (
        <Banner tone={type} onDismiss={onDismiss}>
            {message}
        </Banner>
    )
}
