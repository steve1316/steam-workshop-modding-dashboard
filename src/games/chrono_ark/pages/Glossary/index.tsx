import React from "react"

import { gameApi } from "@/lib/api"
import GlossaryBrowser, { type GlossaryColumn } from "@/components/GlossaryBrowser"
import type { Glossary } from "@/lib/types"

/**
 * Load the base-game glossary.
 *
 * @returns The glossary.
 */
async function loadChronoArkGlossary(): Promise<Glossary> {
    const res = await gameApi("chrono_ark").get("/glossary")
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
}

/** Chrono Ark columns after English Term and Category: the source file (opens in the editor), the key and every source-language mapping. */
const COLUMNS: GlossaryColumn[] = [
    {
        header: "Source File",
        width: 150,
        className: "cell-dim cell-small",
        render: (_key, term) => {
            const file = term.source_file
            if (!file) return "—"
            return (
                <a
                    href="#"
                    onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        gameApi("chrono_ark").post(`/open-base-game-file/${encodeURIComponent(file)}`)
                    }}
                >
                    {file}
                </a>
            )
        },
    },
    { header: "Key", width: 250, className: "cell-dim cell-mono", render: (_key, term) => term.key || "—" },
    {
        header: "Source Mappings",
        className: "cell-dim cell-small",
        render: (_key, term) =>
            Object.entries(term.source_mappings).map(([lang, text]) => (
                <span key={lang} className="term-mapping">
                    <strong>{lang}:</strong> {text}
                </span>
            )),
    },
]

/**
 * Base-game glossary in a searchable table.
 *
 * @returns The glossary page.
 */
const GlossaryPage: React.FC = () => <GlossaryBrowser load={loadChronoArkGlossary} englishWidth={200} categoryWidth={120} columns={COLUMNS} />

export default GlossaryPage
