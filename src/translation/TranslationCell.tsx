import EditableCell from "@/components/EditableCell"

/** Props for `TranslationCell`. */
interface TranslationCellProps {
    value: string
    /** Synced text, struck through above the editor when it differs from `value`. */
    previous?: string | null
    /** Tints the strikethrough green. */
    synced: boolean
    /** Shown instead of the editor when the row can't be translated. */
    untranslatableReason?: string
    placeholder?: string
    highlight?: string
    onSave: (value: string) => void
}

/**
 * Translation table cell: an inline editor with the previous translation struck through above it, or an untranslatable hint.
 * @param value - Current text.
 * @param previous - Synced text.
 * @param synced - Whether the row is synced.
 * @param untranslatableReason - Shown instead of the editor.
 * @param placeholder - Empty-editor placeholder.
 * @param highlight - Search query to highlight.
 * @param onSave - Persists a new value.
 * @returns The cell.
 */
export function TranslationCell({ value, previous, synced, untranslatableReason, placeholder, highlight, onSave }: TranslationCellProps) {
    if (untranslatableReason) {
        return (
            <span className="untranslatable-hint" title={untranslatableReason}>
                {untranslatableReason}
            </span>
        )
    }
    return (
        <>
            {previous && previous !== value && (
                <div className="prev-translation" style={synced ? { color: "rgba(52, 211, 153, 0.6)" } : undefined}>
                    {previous}
                </div>
            )}
            <EditableCell value={value} onSave={onSave} placeholder={placeholder ?? ""} highlight={highlight} />
        </>
    )
}
