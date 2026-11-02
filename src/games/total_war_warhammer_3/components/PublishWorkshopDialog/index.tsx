import { useEffect, useRef, useState, type ReactNode } from "react"
import { fetchChangeNotes, publishPack, publishStreamUrl, RegistryError } from "@/games/total_war_warhammer_3/lib/registryApi"
import Modal from "@/components/ui/Modal"

/** A step the dialog runs before spawning SteamCMD, such as syncing a translation mod. */
export interface PublishPrepareStep {
    /** Shown under the dialog description. */
    note: ReactNode
    status: string
    /** Throwing aborts the publish and shows the error's message. */
    run: () => Promise<void>
}

/** Props for `PublishWorkshopDialog`. */
interface PublishWorkshopDialogProps {
    workshopId: string
    title: string
    onClose: () => void
    prepare?: PublishPrepareStep
}

/** One line of streamed SteamCMD output. */
interface LogEntry {
    seq: number
    /** Raw SteamCMD stdout, or a synthesized status line. */
    line: string
    /** Rendered dimmed and italic. */
    status?: boolean
}

/** Lifecycle of the publish dialog. */
type Phase = "idle" | "publishing" | "done" | "error"

/** Lifecycle of the generated changenote. */
type NoteState = "loading" | "ready" | "unchanged" | "error"

/**
 * Modal for pushing a TW3 compat pack update to the Workshop. Collects a changenote, calls `publishPack`, then streams SteamCMD output into a log panel.
 *
 * @param workshopId Workshop item id being published.
 * @param title Pack title for the header.
 * @param onClose Called when the user dismisses the dialog.
 * @param prepare Step run before the publish starts.
 * @returns The modal overlay.
 */
const PublishWorkshopDialog = ({ workshopId, title, onClose, prepare }: PublishWorkshopDialogProps) => {
    const [changenote, setChangenote] = useState("")
    const [phase, setPhase] = useState<Phase>("idle")
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [exitCode, setExitCode] = useState<number | null>(null)
    const [log, setLog] = useState<LogEntry[]>([])
    const seqRef = useRef(0)
    const sourceRef = useRef<EventSource | null>(null)
    const scrollRef = useRef<HTMLPreElement | null>(null)

    const [noteState, setNoteState] = useState<NoteState>("loading")
    const [noteMessage, setNoteMessage] = useState<string | null>(null)
    // Set once the user edits the textarea, so a note that arrives late never overwrites their text.
    const touchedRef = useRef(false)

    useEffect(() => {
        let cancelled = false
        fetchChangeNotes([workshopId])
            .then(({ notes, errors }) => {
                if (cancelled) return
                const result = notes[workshopId]
                if (!result) {
                    setNoteState("error")
                    setNoteMessage(errors.length > 0 ? `Couldn't generate a changenote: ${errors[0]}` : "No generated changenote for this pack.")
                } else if (!result.pending) {
                    setNoteState("unchanged")
                    setNoteMessage("No changes since the last recorded upload.")
                } else {
                    setNoteState("ready")
                    if (!touchedRef.current) setChangenote(result.note)
                }
            })
            .catch((err: unknown) => {
                if (cancelled) return
                setNoteState("error")
                setNoteMessage(`Couldn't generate a changenote: ${(err as RegistryError).detail || (err as Error).message || "request failed"}`)
            })
        return () => {
            cancelled = true
        }
    }, [workshopId])

    const append = (line: string, status = false) => {
        seqRef.current += 1
        setLog((prev) => [...prev, { seq: seqRef.current, line, status }])
    }

    useEffect(() => {
        const el = scrollRef.current
        if (el) el.scrollTop = el.scrollHeight
    }, [log.length])

    useEffect(() => {
        return () => {
            sourceRef.current?.close()
            sourceRef.current = null
        }
    }, [])

    const handlePublish = async () => {
        setPhase("publishing")
        setErrorMessage(null)
        setExitCode(null)
        setLog([])
        seqRef.current = 0

        if (prepare) {
            append(prepare.status, true)
            try {
                await prepare.run()
            } catch (err) {
                setErrorMessage((err as Error).message || "Failed to prepare the publish.")
                setPhase("error")
                return
            }
        }

        append(`Spawning SteamCMD for workshop item ${workshopId}...`, true)

        try {
            await publishPack(workshopId, changenote)
        } catch (err) {
            const reg = err as RegistryError
            if (reg.status === 400 && reg.missing && reg.missing.length > 0) {
                setErrorMessage(`Steam is not configured. Missing: ${reg.missing.join(", ")}. Open Settings -> Steam Account to fix this.`)
            } else if (reg.status === 409) {
                setErrorMessage("Another publish is already in progress. Wait for it to finish, then try again.")
            } else if (reg.status === 404) {
                setErrorMessage("The local workshop folder for this pack was not found. Check that the Steam library drive is correct in Settings.")
            } else {
                setErrorMessage(reg.detail || "Failed to start publish.")
            }
            setPhase("error")
            return
        }

        const es = new EventSource(publishStreamUrl(workshopId))
        sourceRef.current = es

        es.onmessage = (evt) => {
            try {
                const payload = JSON.parse(evt.data) as { line: string; ts: string }
                append(payload.line)
            } catch {
                /* ignore malformed lines */
            }
        }
        es.addEventListener("done", (evt) => {
            try {
                const info = JSON.parse((evt as MessageEvent).data) as { exit_code: number | null; duration_seconds: number | null }
                setExitCode(info.exit_code)
                const duration = info.duration_seconds != null ? `${info.duration_seconds.toFixed(1)}s` : "unknown time"
                append(`--- SteamCMD exited with code ${info.exit_code} in ${duration} ---`, true)
            } catch {
                /* ignore */
            }
            es.close()
            sourceRef.current = null
            setPhase("done")
        })
        es.onerror = () => {
            es.close()
            sourceRef.current = null
            append("--- Stream connection lost ---", true)
            setPhase("done")
        }
    }

    const isPublishing = phase === "publishing"
    const showLog = log.length > 0
    const success = phase === "done" && exitCode === 0

    return (
        <Modal title={`Publish "${title}" to Workshop`} size="md" onClose={onClose} closeDisabled={isPublishing} closeDisabledReason="Publish in progress">
            <p style={{ color: "var(--text-dim)", marginTop: 0, marginBottom: "1rem", lineHeight: 1.5 }}>
                Pushes the local workshop folder for item <code>{workshopId}</code> to Steam as an update. Existing title, description, visibility, tags, and preview are preserved.
            </p>
            {prepare && <p style={{ color: "var(--text-dim)", marginTop: 0, marginBottom: "1rem", lineHeight: 1.5 }}>{prepare.note}</p>}

            <label style={{ display: "block", marginBottom: "1rem" }}>
                <span style={{ display: "block", marginBottom: "0.4rem", color: "var(--text-main)" }}>Changenote (shown in the Workshop changelog)</span>
                <textarea
                    value={changenote}
                    onChange={(e) => {
                        touchedRef.current = true
                        setChangenote(e.target.value)
                    }}
                    disabled={phase !== "idle" && phase !== "error"}
                    rows={6}
                    style={{
                        width: "100%",
                        padding: "0.5rem",
                        background: "rgba(0,0,0,0.25)",
                        color: "var(--text-main)",
                        border: "1px solid var(--border-dim, rgba(255,255,255,0.15))",
                        borderRadius: 6,
                        fontFamily: "inherit",
                        fontSize: "0.9rem",
                        resize: "vertical",
                        boxSizing: "border-box",
                    }}
                    placeholder={noteState === "loading" ? "Generating changenote..." : "e.g. Resync against latest game patch"}
                />
            </label>
            {noteMessage && <p style={{ color: "var(--text-dim)", marginTop: "-0.5rem", marginBottom: "1rem", fontSize: "0.85rem", lineHeight: 1.4 }}>{noteMessage}</p>}

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

            {showLog && (
                <pre
                    ref={scrollRef}
                    style={{
                        margin: "0 0 1rem 0",
                        padding: "0.75rem",
                        background: "rgba(0,0,0,0.3)",
                        borderRadius: 6,
                        fontFamily: "monospace",
                        fontSize: "0.85rem",
                        maxHeight: 320,
                        overflowY: "auto",
                        whiteSpace: "pre-wrap",
                        color: "var(--text-main)",
                    }}
                >
                    {log.map((entry) =>
                        entry.status ? (
                            <div key={entry.seq} style={{ color: "var(--text-dim, #777)", fontStyle: "italic", margin: "0.25rem 0" }}>
                                {entry.line}
                            </div>
                        ) : (
                            <div key={entry.seq}>{entry.line}</div>
                        )
                    )}
                </pre>
            )}

            {phase === "done" && (
                <div style={{ marginBottom: "1rem", color: success ? "#7ee787" : "#ff8a8a", fontWeight: 600 }}>
                    {success ? "Publish succeeded." : `Publish failed (exit code ${exitCode}). Review the log above and your Steam Guard / sentry status.`}
                </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                {phase === "done" || phase === "error" ? (
                    <button className="btn btn-primary" onClick={onClose}>
                        Close
                    </button>
                ) : (
                    <>
                        <button className="btn btn-outline" onClick={onClose} disabled={isPublishing}>
                            Cancel
                        </button>
                        <button className="btn btn-primary" onClick={handlePublish} disabled={isPublishing}>
                            {isPublishing ? "Publishing..." : "Publish"}
                        </button>
                    </>
                )}
            </div>
        </Modal>
    )
}

export default PublishWorkshopDialog
