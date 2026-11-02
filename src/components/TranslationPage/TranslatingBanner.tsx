/** Real-time progress from a streaming provider. */
interface StreamingProgress {
    tokensGenerated: number
    /** Tokens per second. */
    tokensPerSec: number
    /** Seconds elapsed in the current batch. */
    elapsedSec: number
}

/** Props for TranslatingBanner. */
interface TranslatingBannerProps {
    /** Zero-based index of the batch currently translating. */
    batchIndex: number
    totalBatches: number
    /** Live stats, only when the provider streams. */
    streaming?: StreamingProgress
    onCancel: () => void
}

/**
 * In-progress banner showing the current batch, streaming throughput when available, and Cancel.
 * @param batchIndex - Zero-based current batch.
 * @param totalBatches - Batches in the run.
 * @param streaming - Live streaming stats.
 * @param onCancel - Cancel handler.
 * @returns The banner.
 */
export function TranslatingBanner({ batchIndex, totalBatches, streaming, onCancel }: TranslatingBannerProps) {
    const detail = streaming ? `${streaming.tokensGenerated} tokens (${streaming.tokensPerSec} tok/s, ${streaming.elapsedSec}s elapsed)` : "waiting for provider response"
    return (
        <div
            className="glass-card"
            style={{
                background: "rgba(125, 211, 252, 0.08)",
                border: "1px solid rgba(125, 211, 252, 0.25)",
                padding: "1rem 1.25rem",
                marginBottom: "1rem",
                display: "flex",
                alignItems: "center",
                gap: "1rem",
            }}
        >
            <span
                style={{
                    width: "1.25rem",
                    height: "1.25rem",
                    borderRadius: "50%",
                    border: "2px solid rgba(125, 211, 252, 0.3)",
                    borderTopColor: "var(--accent-primary)",
                    animation: "spin 1s linear infinite",
                    flexShrink: 0,
                }}
            />
            <span style={{ flex: 1 }}>
                Translating batch {batchIndex + 1} of {totalBatches}... {detail}
            </span>
            <button className="btn btn-outline" onClick={onCancel}>
                Cancel
            </button>
        </div>
    )
}
