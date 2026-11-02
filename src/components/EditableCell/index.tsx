import React, { useState, useEffect, useRef } from "react"

import HighlightText from "@/ui/HighlightText"

/** Props for EditableCell. */
interface EditableCellProps {
    value: string
    onSave: (val: string) => void
    /** Shown in dim italic when the value is empty. */
    placeholder?: string
    highlight?: string
}

/**
 * Inline-editable table cell. Commits on blur or Ctrl+Enter, reverts on Escape, and only calls `onSave` when the value changed.
 *
 * @param value - Persisted value.
 * @param onSave - Called with the committed value.
 * @param placeholder - Shown when empty.
 * @param highlight - Search query to highlight.
 * @returns The editable cell.
 */
const EditableCell: React.FC<EditableCellProps> = ({ value, onSave, placeholder, highlight = "" }) => {
    const [isEditing, setIsEditing] = useState(false)
    const [tempValue, setTempValue] = useState(value)
    const [cellHeight, setCellHeight] = useState<number | undefined>(undefined)
    const inputRef = useRef<HTMLTextAreaElement>(null)
    const cellRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus()
        }
    }, [isEditing])

    /** Handle focus loss on the input. */
    const handleBlur = () => {
        setIsEditing(false)
        if (tempValue !== value) {
            onSave(tempValue)
        }
    }

    /**
     * Handles key down events within the editing input.
     * @param e - Keyboard event.
     */
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault()
            handleBlur()
        } else if (e.key === "Escape") {
            setTempValue(value)
            setIsEditing(false)
        }
    }

    if (isEditing) {
        return (
            <textarea
                ref={inputRef}
                value={tempValue}
                onChange={(e) => setTempValue(e.target.value)}
                onBlur={handleBlur}
                onKeyDown={handleKeyDown}
                className="edit-input"
                style={{
                    width: "100%",
                    minHeight: cellHeight ?? "1.2em",
                    padding: "4px 8px",
                    background: "rgba(0,0,0,0.4)",
                    border: "1px solid var(--accent-primary)",
                    color: "var(--text-main)",
                    borderRadius: "4px",
                    outline: "none",
                    resize: "vertical",
                    fontFamily: "inherit",
                    fontSize: "inherit",
                    boxSizing: "border-box",
                }}
            />
        )
    }

    return (
        <div
            ref={cellRef}
            onClick={() => {
                setCellHeight(cellRef.current?.offsetHeight)
                setIsEditing(true)
                setTempValue(value)
            }}
            className="clickable-cell"
            style={{ minHeight: "1.2em", cursor: "text", whiteSpace: "pre-wrap" }}
        >
            {value ? (
                <span>
                    <HighlightText text={value} query={highlight} />
                </span>
            ) : (
                <span style={{ color: "var(--text-dim)", fontStyle: "italic" }}>{placeholder}</span>
            )}
        </div>
    )
}

export default EditableCell
