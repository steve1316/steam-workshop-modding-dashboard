import React, { useState, type HTMLAttributes, type ReactNode } from "react"

/** Props for WorkshopCard. */
interface WorkshopCardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
    /** A placeholder renders when omitted, null, or the image fires `onError`. */
    previewImageUrl?: string | null
    /** Defaults to a generic label. */
    previewAlt?: string
    title: ReactNode
    /** Monospace badge right of the title, e.g. workshop id. */
    idBadge?: string
    /** Dim line beneath the title. */
    subtitle?: ReactNode
    children?: ReactNode
}

/**
 * Shared shell for workshop-style cards: the glass frame, preview image slot with placeholder fallback, and header row. Per-game content goes in `children`.
 *
 * @param previewImageUrl Preview image URL
 * @param previewAlt Image alt text
 * @param title Card title
 * @param idBadge Badge text right of the title
 * @param subtitle Dim subtitle beneath the title
 * @param children Body and action content
 * @param className Extra classes for the root
 * @param rest HTML attributes for the root, e.g. `data-mod-id`
 * @returns The card.
 */
const WorkshopCard: React.FC<WorkshopCardProps> = ({ previewImageUrl, previewAlt = "Preview image", title, idBadge, subtitle, children, className, ...rest }) => {
    const [imageFailed, setImageFailed] = useState(false)

    return (
        <div className={`glass-card mod-card animate-fade-in${className ? ` ${className}` : ""}`} {...rest}>
            {previewImageUrl && (
                <div className="mod-preview">
                    {!imageFailed ? (
                        <img src={previewImageUrl} alt={previewAlt} loading="lazy" onError={() => setImageFailed(true)} />
                    ) : (
                        <div
                            data-testid="workshop-card-placeholder"
                            style={{
                                width: "100%",
                                height: "100%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                background: "rgba(255,255,255,0.04)",
                                color: "var(--text-dim, #777)",
                                fontSize: "0.8rem",
                            }}
                        >
                            {idBadge ?? "No preview"}
                        </div>
                    )}
                </div>
            )}
            <div className="mod-card-content">
                <div className="mod-header">
                    <div className="mod-info">
                        <h3>{title}</h3>
                        {subtitle && <span className="author">{subtitle}</span>}
                    </div>
                    {idBadge && <span className="id-badge">{idBadge}</span>}
                </div>
                {children}
            </div>
        </div>
    )
}

export default WorkshopCard
