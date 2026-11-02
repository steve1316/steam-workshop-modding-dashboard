import type { GlossaryTerm, LocString } from "@/shared_types"

/** A glossary term whose source text appears in the current row. */
export interface GlossaryMatch {
    source: string
    english: string
    category: string
}

/**
 * Find a row's partner, mapping a `_name` key to its `_Description` key and back.
 *
 * @param key The row's key.
 * @param allStrings Every row of the mod.
 * @returns The paired row, or undefined when there is none.
 */
export function findPairedRow(key: string, allStrings: LocString[]): LocString | undefined {
    let target: string
    if (/_name$/i.test(key)) target = key.replace(/_name$/i, "_description")
    else if (/_description$/i.test(key)) target = key.replace(/_description$/i, "_name")
    else return undefined
    // Chrono Ark mods mix `_name` and `_Name`, so the lookup ignores case.
    const wanted = target.toLowerCase()
    return allStrings.find((s) => s.key.toLowerCase() === wanted)
}

/**
 * List the glossary terms whose source text appears in `source`, longest first.
 *
 * @param source The row's original text.
 * @param glossary The mod glossary, keyed by English term.
 * @param sourceLanguage The mod's source language.
 * @returns The matching terms.
 */
export function findGlossaryMatches(source: string, glossary: Record<string, GlossaryTerm>, sourceLanguage: string): GlossaryMatch[] {
    const matches: GlossaryMatch[] = []
    for (const [key, term] of Object.entries(glossary)) {
        const termSource = term.source_mappings?.[sourceLanguage]
        if (termSource && source.includes(termSource)) matches.push({ source: termSource, english: term.english || key, category: term.category || "custom" })
    }
    return matches.sort((a, b) => b.source.length - a.source.length)
}
