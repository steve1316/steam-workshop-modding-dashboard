import React from "react"

/** Props for ModGridSkeleton. */
interface ModGridSkeletonProps {
    /** Defaults to 6. */
    count?: number
    /** Defaults to "Loading mods". */
    label?: string
}

/**
 * Placeholder grid shown while the mod list loads, mirroring the `ModCard` layout so the page keeps its shape.
 *
 * @param count Number of placeholder cards
 * @param label Accessible loading label
 * @returns A busy `mod-grid` of skeleton cards.
 */
const ModGridSkeleton: React.FC<ModGridSkeletonProps> = ({ count = 6, label = "Loading mods" }) => {
    return (
        <div className="mod-grid" role="status" aria-busy="true" aria-label={label}>
            {Array.from({ length: count }, (_, i) => (
                <div key={i} className="glass-card mod-card mod-card-skeleton" aria-hidden="true">
                    <div className="mod-preview skeleton-block" />
                    <div className="mod-card-content">
                        <div>
                            <div className="skeleton-block" style={{ height: "1.1rem", width: "70%" }} />
                            <div className="skeleton-block" style={{ height: "0.8rem", width: "40%", marginTop: "0.5rem" }} />
                        </div>
                        <div className="skeleton-block" style={{ height: "0.5rem", width: "100%" }} />
                        <div style={{ display: "flex", gap: "1rem" }}>
                            <div className="skeleton-block" style={{ height: "2.5rem", flex: 1 }} />
                            <div className="skeleton-block" style={{ height: "2.5rem", flex: 1 }} />
                        </div>
                        <div className="skeleton-block" style={{ height: "2.25rem", width: "100%", marginTop: "auto" }} />
                    </div>
                </div>
            ))}
        </div>
    )
}

export default ModGridSkeleton
