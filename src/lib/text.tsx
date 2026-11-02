import React from "react"

/**
 * Wrap the first substring matching `query` in a highlight span. Text is unchanged when the query is empty or not found.
 * @param text - Text to search within.
 * @param query - Substring to highlight.
 * @returns The text with the match highlighted.
 */
export function highlightMatch(text: string, query: string): React.ReactNode {
    if (!query) return text
    const lower = text.toLowerCase()
    const q = query.toLowerCase()
    const idx = lower.indexOf(q)
    if (idx === -1) return text
    return (
        <>
            {text.slice(0, idx)}
            <span style={{ background: "rgba(56, 189, 248, 0.3)", borderRadius: "2px" }}>{text.slice(idx, idx + query.length)}</span>
            {text.slice(idx + query.length)}
        </>
    )
}
