import React from "react"

import GlossaryBrowser, { type GlossaryColumn } from "../../../../glossary/GlossaryBrowser"
import { fetchBaseGlossary } from "../../translationApi"

/** WH3 columns after English Term and Category: the Chinese and Korean base-game text. */
const COLUMNS: GlossaryColumn[] = [
    { header: "Chinese", className: "cell-dim", render: (_key, term) => term.source_mappings.Chinese || "—" },
    { header: "Korean", className: "cell-dim", render: (_key, term) => term.source_mappings.Korean || "—" },
]

/**
 * WH3 base-game terminology glossary in a searchable table.
 *
 * @returns The glossary page.
 */
const GlossaryPage: React.FC = () => <GlossaryBrowser load={fetchBaseGlossary} englishWidth={260} categoryWidth={140} columns={COLUMNS} />

export default GlossaryPage
