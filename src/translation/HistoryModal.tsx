import { useState } from "react"
import type { ReactNode } from "react"
import Modal from "../ui/Modal"

/** One normalized history/snapshot entry rendered by the shared modal. Each game maps its own backup/snapshot shape onto this. */
export interface HistoryModalEntry {
    /** React key, also passed back to the restore and delete handlers. */
    id: string
    /** Primary line: the backup reason (Chrono Ark) or the snapshot label (WH3). */
    title: string
    /** "auto" for snapshots taken before destructive ops, "manual" for user saves. Sets the pill color. */
    kind: "auto" | "manual"
    createdAt: string
    /** Secondary metadata line (e.g. translated/total counts). */
    subtitle?: ReactNode
}

/** Props for the shared `HistoryModal`. */
interface HistoryModalProps {
    /** Header text. Defaults to "History Backups"; WH3's Reset action passes "Reset to snapshot". */
    title?: string
    /** Entries to list, newest first (the parent orders them). */
    entries: HistoryModalEntry[]
    /** Create a manual snapshot. On resolve the modal clears its input and the parent re-fetches. */
    onSave: (label: string) => Promise<void>
    /** Restore clicked. The parent decides how to confirm. */
    onRestore: (entry: HistoryModalEntry) => void
    /** Delete clicked. The parent decides how to confirm. */
    onDelete: (entry: HistoryModalEntry) => void
    onClose: () => void
    emptyMessage?: string
    /** Parent data-layer error, shown above the list. */
    error?: string | null
}

/**
 * Shared history/snapshot modal. It owns only the save-label input and saving state, and each game wraps it with its own API and entry mapping.
 * @param title - Header text.
 * @param entries - Entries to render.
 * @param onSave - Persists a snapshot with the typed label.
 * @param onRestore - Restore handler.
 * @param onDelete - Delete handler.
 * @param onClose - Close handler.
 * @param emptyMessage - Shown when there are no entries.
 * @param error - Parent error, shown alongside any save error.
 * @returns The modal.
 */
export default function HistoryModal({ title = "History Backups", entries, onSave, onRestore, onDelete, onClose, emptyMessage, error }: HistoryModalProps) {
    const [label, setLabel] = useState("")
    const [saving, setSaving] = useState(false)
    const [saveError, setSaveError] = useState<string | null>(null)

    const handleSave = async () => {
        setSaving(true)
        setSaveError(null)
        try {
            await onSave(label)
            setLabel("")
        } catch (err) {
            setSaveError((err as Error).message || "Failed to save snapshot.")
        } finally {
            setSaving(false)
        }
    }

    return (
        <Modal title={title} size="md" onClose={onClose}>
            {(error || saveError) && <p style={{ color: "var(--tone-danger)", marginTop: 0, marginBottom: "1rem" }}>{error || saveError}</p>}
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
                <input
                    type="text"
                    placeholder="Snapshot label..."
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter" && !saving) handleSave()
                    }}
                    style={{ flex: 1, padding: "0.5rem 0.75rem", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "rgba(0,0,0,0.2)", color: "var(--text-main)" }}
                />
                <button className="btn btn-primary" onClick={handleSave} disabled={saving} style={{ padding: "0.5rem 1rem", whiteSpace: "nowrap" }}>
                    {saving ? "Saving..." : "Save snapshot"}
                </button>
            </div>
            {entries.length === 0 ? (
                <p style={{ color: "var(--text-dim)", textAlign: "center", padding: "2rem" }}>{emptyMessage ?? "No snapshots yet."}</p>
            ) : (
                <div>
                    {entries.map((entry) => (
                        <div
                            key={entry.id}
                            data-testid="snapshot-row"
                            style={{
                                padding: "1rem",
                                marginBottom: "0.75rem",
                                background: "rgba(0,0,0,0.2)",
                                borderRadius: "8px",
                                border: "1px solid var(--glass-border)",
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                            }}
                        >
                            <div>
                                <div style={{ fontWeight: 500, display: "flex", alignItems: "center", gap: "0.4rem" }}>
                                    <span className={`snapshot-kind ${entry.kind}`}>{entry.kind}</span>
                                    {entry.title}
                                </div>
                                <div style={{ color: "var(--text-dim)", fontSize: "0.85rem", marginTop: "0.25rem" }}>{new Date(entry.createdAt).toLocaleString()}</div>
                                {entry.subtitle != null && <div style={{ color: "var(--text-dim)", fontSize: "0.75rem", marginTop: "0.15rem" }}>{entry.subtitle}</div>}
                            </div>
                            <div style={{ display: "flex", gap: "0.35rem", flexShrink: 0 }}>
                                <button className="btn btn-primary btn-sm" onClick={() => onRestore(entry)}>
                                    Restore
                                </button>
                                <button className="btn btn-outline btn-sm tone-danger" onClick={() => onDelete(entry)}>
                                    Delete
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </Modal>
    )
}
