import type { ReactNode } from "react"

/** Color tone for a `Banner`. */
export type BannerTone = "success" | "error" | "info" | "warning"

/** Props for Banner. */
interface BannerProps {
    /** Tone that sets the tint and text color. */
    tone: BannerTone
    children: ReactNode
    /** When given, a Dismiss (x) button calls it. */
    onDismiss?: () => void
}

/**
 * Tinted full-width notice for results, errors and in-progress states.
 *
 * @param tone Tint and text color.
 * @param children Banner content.
 * @param onDismiss Optional close handler, which shows a Dismiss button when set.
 * @returns The banner element.
 */
export default function Banner({ tone, children, onDismiss }: BannerProps) {
    return (
        <div className={`glass-card banner banner-${tone}`}>
            <div className="banner-content">{children}</div>
            {onDismiss && (
                <button type="button" className="banner-dismiss" onClick={onDismiss} aria-label="Dismiss">
                    &times;
                </button>
            )}
        </div>
    )
}
