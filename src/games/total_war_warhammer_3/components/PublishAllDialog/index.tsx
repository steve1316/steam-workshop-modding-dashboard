import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react"

import { fetchChangeNotes, publishAllPacks, publishAllStreamUrl, RegistryError } from "@/games/total_war_warhammer_3/lib/registryApi"
import { type BatchPublishHandle, type BatchPublishItem, type ChangeNote } from "@/games/total_war_warhammer_3/lib/types"
import Modal from "@/components/ui/Modal"

/** One pack entry from the Dashboard. */
interface PackEntry {
    title: string
    /** Empty values are treated as skipped and never sent to the backend. */
    workshopId: string
    /** Unused here, accepted so the Dashboard can pass its array as-is. */
    scriptId?: string
    /** Unused here, same reason as `scriptId`. */
    sharedNote?: string
}

/** Props for `PublishAllDialog`. */
interface PublishAllDialogProps {
    /** Empty-workshopId entries show as pre-skipped. */
    packs: PackEntry[]
    onClose: () => void
}

/** Per-mod status mirrored from the backend orchestrator. */
type ModStatus = "pending" | "publishing" | "done" | "failed" | "skipped"

/** Dialog lifecycle. */
type Phase = "confirming" | "running" | "done"

/** Lifecycle of a row's generated changenote. */
type NoteState = "loading" | "ready" | "unchanged" | "error"

const NOTE_LABELS: Record<NoteState, string> = {
    loading: "Generating...",
    ready: "Note",
    unchanged: "No changes",
    error: "Needs note",
}

/** Shared look of the per-row changenote editors. */
const TEXTAREA_STYLE: CSSProperties = {
    width: "100%",
    marginTop: "0.5rem",
    padding: "0.5rem",
    background: "rgba(0,0,0,0.25)",
    color: "var(--text-main)",
    border: "1px solid var(--border-dim, rgba(255,255,255,0.15))",
    borderRadius: 6,
    fontFamily: "inherit",
    fontSize: "0.85rem",
    resize: "vertical",
    boxSizing: "border-box",
}

/** One row in the per-mod status list. */
interface ModRow {
    workshopId: string
    title: string
    status: ModStatus
    exitCode: number | null
    error: string | null
    durationSeconds: number | null
    reason: string | null
    /** Ignored for pre-skipped rows. */
    selected: boolean
    /** Pre-filled from the generated note and editable before publishing. */
    note: string
    /** Rows without a workshop id never load a note. */
    noteState: NoteState
    expanded: boolean
}

/** One line of SteamCMD output, scoped to its mod. */
interface LogEntry {
    seq: number
    workshopId: string
    line: string
}

/**
 * Fold one generated changenote into a row. Unchanged mods start unchecked but keep the note, and failures open an empty editor.
 *
 * @param row Row to update.
 * @param result Generated note, or null when none could be generated.
 * @returns The updated row, unchanged if it is not waiting on a note.
 */
function applyNote(row: ModRow, result: ChangeNote | null | undefined): ModRow {
    if (row.noteState !== "loading") return row
    if (!result) return { ...row, noteState: "error", expanded: true }
    if (!result.pending) return { ...row, noteState: "unchanged", selected: false, note: row.note || result.note }
    return { ...row, noteState: "ready", note: row.note || result.note }
}

/**
 * Modal that publishes many compat packs to the Workshop, each with its own editable generated changelog. Streams per-mod status and the live SteamCMD log.
 *
 * @param packs Pack entries to consider.
 * @param onClose Called when the user dismisses the dialog.
 * @returns The modal overlay.
 */
const PublishAllDialog = ({ packs, onClose }: PublishAllDialogProps) => {
    const [phase, setPhase] = useState<Phase>("confirming")
    const [rows, setRows] = useState<ModRow[]>(() =>
        packs.map((p) => ({
            workshopId: p.workshopId,
            title: p.title,
            status: p.workshopId ? "pending" : "skipped",
            exitCode: null,
            error: null,
            durationSeconds: null,
            reason: p.workshopId ? null : "no workshopId",
            selected: Boolean(p.workshopId),
            note: "",
            noteState: p.workshopId ? "loading" : "ready",
            expanded: false,
        }))
    )
    const [currentId, setCurrentId] = useState<string | null>(null)
    const [currentLog, setCurrentLog] = useState<LogEntry[]>([])
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [noteWarning, setNoteWarning] = useState<string | null>(null)
    const seqRef = useRef(0)
    const sourceRef = useRef<EventSource | null>(null)
    const scrollRef = useRef<HTMLPreElement | null>(null)

    const eligible = useMemo(() => rows.filter((r) => r.status !== "skipped"), [rows])
    const selectedEligible = useMemo(() => eligible.filter((r) => r.selected), [eligible])
    const isRunning = phase === "running"
    const isDone = phase === "done"

    const notesLoading = eligible.some((r) => r.noteState === "loading")
    const canPublish = !notesLoading && selectedEligible.length > 0 && selectedEligible.every((r) => r.note.trim().length > 0)

    // Keyed on the ids so a parent re-render with a new array does not refetch.
    const idsKey = packs
        .map((p) => p.workshopId)
        .filter(Boolean)
        .join(",")
    useEffect(() => {
        const ids = idsKey ? idsKey.split(",") : []
        if (ids.length === 0) return
        let cancelled = false
        fetchChangeNotes(ids)
            .then(({ notes, errors }) => {
                if (cancelled) return
                if (errors.length > 0) setNoteWarning(`Some changenotes could not be generated: ${errors.join("; ")}`)
                setRows((prev) => prev.map((r) => applyNote(r, notes[r.workshopId])))
            })
            .catch((err: unknown) => {
                if (cancelled) return
                setNoteWarning(`Couldn't generate changenotes: ${(err as RegistryError).detail || (err as Error).message || "request failed"}`)
                setRows((prev) => prev.map((r) => applyNote(r, null)))
            })
        return () => {
            cancelled = true
        }
    }, [idsKey])

    useEffect(() => {
        const el = scrollRef.current
        if (el) el.scrollTop = el.scrollHeight
    }, [currentLog.length])

    useEffect(() => {
        return () => {
            sourceRef.current?.close()
            sourceRef.current = null
        }
    }, [])

    const updateRow = (workshopId: string, patch: Partial<ModRow>) => {
        setRows((prev) => prev.map((r) => (r.workshopId === workshopId ? { ...r, ...patch } : r)))
    }

    const toggleSelected = (workshopId: string) => {
        setRows((prev) => prev.map((r) => (r.workshopId === workshopId ? { ...r, selected: !r.selected } : r)))
    }

    const toggleExpanded = (workshopId: string) => {
        setRows((prev) => prev.map((r) => (r.workshopId === workshopId ? { ...r, expanded: !r.expanded } : r)))
    }

    const subscribeToBatch = (batchId: string) => {
        const es = new EventSource(publishAllStreamUrl(batchId))
        sourceRef.current = es

        es.addEventListener("mod_started", (evt) => {
            try {
                const payload = JSON.parse((evt as MessageEvent).data) as { workshop_id: string; title: string }
                setCurrentId(payload.workshop_id)
                setCurrentLog([])
                seqRef.current = 0
                updateRow(payload.workshop_id, { status: "publishing", error: null })
            } catch {
                /* ignore */
            }
        })

        es.addEventListener("log_line", (evt) => {
            try {
                const payload = JSON.parse((evt as MessageEvent).data) as { workshop_id: string; line: string }
                seqRef.current += 1
                setCurrentLog((prev) => [...prev, { seq: seqRef.current, workshopId: payload.workshop_id, line: payload.line }])
            } catch {
                /* ignore */
            }
        })

        es.addEventListener("mod_finished", (evt) => {
            try {
                const payload = JSON.parse((evt as MessageEvent).data) as {
                    workshop_id: string
                    exit_code: number | null
                    duration_seconds: number | null
                    status: "done" | "failed"
                    error: string | null
                }
                updateRow(payload.workshop_id, {
                    status: payload.status,
                    exitCode: payload.exit_code,
                    durationSeconds: payload.duration_seconds,
                    error: payload.error,
                })
            } catch {
                /* ignore */
            }
        })

        es.addEventListener("mod_skipped", (evt) => {
            try {
                const payload = JSON.parse((evt as MessageEvent).data) as { workshop_id: string; reason: string }
                updateRow(payload.workshop_id, { status: "skipped", reason: payload.reason })
            } catch {
                /* ignore */
            }
        })

        es.addEventListener("batch_done", () => {
            es.close()
            sourceRef.current = null
            setPhase("done")
            setCurrentId(null)
        })

        es.onerror = () => {
            es.close()
            sourceRef.current = null
            setPhase("done")
            setErrorMessage("Stream connection lost. The backend may still be publishing - refresh and reopen to reconnect.")
        }
    }

    const handlePublishAll = async () => {
        if (!canPublish) return
        setErrorMessage(null)

        // Mark unchecked rows as skipped so the running view shows them.
        const deselectedIds = new Set(eligible.filter((r) => !r.selected).map((r) => r.workshopId))
        if (deselectedIds.size > 0) {
            setRows((prev) => prev.map((r) => (deselectedIds.has(r.workshopId) ? { ...r, status: "skipped", reason: "not selected" } : r)))
        }

        const items: BatchPublishItem[] = selectedEligible.map((r) => ({ workshop_id: r.workshopId, title: r.title, changenote: r.note }))

        let handle: BatchPublishHandle
        try {
            handle = await publishAllPacks(items)
        } catch (err) {
            const reg = err as RegistryError
            if (reg.status === 409) {
                setErrorMessage("Another publish is already in progress. Wait for it to finish, then try again.")
            } else if (reg.status === 400) {
                setErrorMessage(reg.detail || "Backend rejected the request.")
            } else {
                setErrorMessage(reg.detail || "Failed to start the batch publish.")
            }
            return
        }

        setPhase("running")
        try {
            localStorage.setItem("wh3-publish-all-active-batch", handle.batch_id)
        } catch {
            /* ignore quota / disabled storage */
        }
        subscribeToBatch(handle.batch_id)
    }

    const handleClose = () => {
        if (isRunning) return
        try {
            localStorage.removeItem("wh3-publish-all-active-batch")
        } catch {
            /* ignore */
        }
        onClose()
    }

    return (
        <Modal title="Publish All to Workshop" size="md" onClose={handleClose} closeDisabled={isRunning} closeDisabledReason="Batch publish in progress">
            {noteWarning && <p style={{ marginTop: 0, marginBottom: "0.75rem", color: "#fbbf24", fontSize: "0.85rem", lineHeight: 1.4 }}>{noteWarning}</p>}

            <p style={{ marginTop: 0, marginBottom: "0.5rem", color: "var(--text-dim)" }}>
                This will publish {selectedEligible.length} {selectedEligible.length === 1 ? "mod" : "mods"} to the Steam Workshop, each with its own changenote:
            </p>
            <ul style={{ listStyle: "none", padding: 0, margin: "0 0 1rem 0", borderRadius: 6, border: "1px solid var(--border-dim, rgba(255,255,255,0.12))" }}>
                {rows.map((row) => (
                    <li
                        key={row.workshopId || `skip-${row.title}`}
                        style={{
                            padding: "0.5rem 0.85rem",
                            borderTop: "1px solid rgba(255,255,255,0.05)",
                            opacity: row.status === "skipped" ? 0.55 : 1,
                        }}
                    >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
                            {phase === "confirming" && row.workshopId && row.status !== "skipped" && (
                                <input
                                    type="checkbox"
                                    checked={row.selected}
                                    onChange={() => toggleSelected(row.workshopId)}
                                    aria-label={`Include ${row.title} in the batch`}
                                    style={{ cursor: "pointer", flexShrink: 0 }}
                                />
                            )}
                            <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {row.title}
                                {row.workshopId && <code style={{ marginLeft: "0.5rem", color: "var(--text-dim)" }}>{row.workshopId}</code>}
                            </span>
                            {phase === "confirming" && row.workshopId && row.status !== "skipped" && (
                                <button
                                    type="button"
                                    className="btn btn-outline btn-compact"
                                    onClick={() => toggleExpanded(row.workshopId)}
                                    disabled={row.noteState === "loading"}
                                    aria-label={`Edit changenote for ${row.title}`}
                                    aria-expanded={row.expanded}
                                >
                                    {NOTE_LABELS[row.noteState]}
                                </button>
                            )}
                            <StatusBadge row={row} />
                        </div>
                        {phase === "confirming" && row.expanded && row.status !== "skipped" && (
                            <textarea
                                aria-label={`Changenote for ${row.title}`}
                                value={row.note}
                                onChange={(e) => updateRow(row.workshopId, { note: e.target.value })}
                                rows={5}
                                style={TEXTAREA_STYLE}
                                placeholder="Changenote shown in the Workshop changelog"
                            />
                        )}
                    </li>
                ))}
            </ul>

            {errorMessage && (
                <div
                    style={{
                        padding: "0.75rem 1rem",
                        marginBottom: "1rem",
                        background: "rgba(239,68,68,0.15)",
                        color: "#ff8a8a",
                        border: "1px solid rgba(239,68,68,0.3)",
                        borderRadius: 6,
                        lineHeight: 1.4,
                    }}
                >
                    {errorMessage}
                </div>
            )}

            {(isRunning || isDone) && (
                <div style={{ marginBottom: "1rem" }}>
                    <div style={{ color: "var(--text-dim)", marginBottom: "0.4rem" }}>
                        {isRunning && currentId ? `Live SteamCMD log (${rows.find((r) => r.workshopId === currentId)?.title ?? currentId}):` : "Live SteamCMD log:"}
                    </div>
                    <pre
                        ref={scrollRef}
                        style={{
                            background: "rgba(0,0,0,0.45)",
                            color: "var(--text-main)",
                            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                            fontSize: "0.8rem",
                            padding: "0.75rem",
                            margin: 0,
                            borderRadius: 6,
                            border: "1px solid var(--border-dim, rgba(255,255,255,0.12))",
                            minHeight: "120px",
                            maxHeight: "240px",
                            overflow: "auto",
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-word",
                        }}
                    >
                        {currentLog.length === 0 ? <span style={{ color: "var(--text-dim)" }}>(waiting for SteamCMD output...)</span> : currentLog.map((l) => <div key={l.seq}>{l.line}</div>)}
                    </pre>
                </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem" }}>
                {phase === "confirming" && (
                    <>
                        <button onClick={handleClose} className="btn btn-outline">
                            Cancel
                        </button>
                        <button onClick={handlePublishAll} disabled={!canPublish} className="btn btn-primary">
                            Publish All
                        </button>
                    </>
                )}
                {(isRunning || isDone) && (
                    <button onClick={handleClose} disabled={isRunning} className="btn btn-outline">
                        Close
                    </button>
                )}
            </div>
        </Modal>
    )
}

/** Props for `StatusBadge`. */
interface StatusBadgeProps {
    row: ModRow
}

const BADGE_COLORS: Record<ModStatus, { bg: string; fg: string; label: string }> = {
    pending: { bg: "rgba(148,163,184,0.22)", fg: "#cbd5e1", label: "pending" },
    publishing: { bg: "rgba(59,130,246,0.25)", fg: "#93c5fd", label: "publishing" },
    done: { bg: "rgba(34,197,94,0.22)", fg: "#86efac", label: "done" },
    failed: { bg: "rgba(239,68,68,0.22)", fg: "#fca5a5", label: "failed" },
    skipped: { bg: "rgba(148,163,184,0.18)", fg: "#94a3b8", label: "skipped" },
}

/**
 * Color-coded status badge, with exit code, duration, or reason once the row finishes.
 *
 * @param row Row whose status drives the badge.
 * @returns The badge.
 */
const StatusBadge = ({ row }: StatusBadgeProps) => {
    const style = BADGE_COLORS[row.status]
    let extra = ""
    if (row.status === "done" || row.status === "failed") {
        if (row.exitCode != null) extra += ` exit ${row.exitCode}`
        if (row.durationSeconds != null) extra += ` ${row.durationSeconds.toFixed(1)}s`
    } else if (row.status === "skipped" && row.reason) {
        extra = ` (${row.reason})`
    }
    return (
        <span
            style={{
                background: style.bg,
                color: style.fg,
                padding: "0.15rem 0.55rem",
                borderRadius: 999,
                fontSize: "0.75rem",
                fontWeight: 600,
                whiteSpace: "nowrap",
            }}
            title={row.error ?? undefined}
        >
            {style.label}
            {extra}
        </span>
    )
}

export default PublishAllDialog
