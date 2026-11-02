import { useState } from "react"

/** A mod's language overrides. Null falls back to the game's default. */
export interface LanguageOverrides {
    source: string | null
    target: string | null
}

/**
 * A mod's source and target language. A pick shows at once while it saves. A target only applies to an English source, so picking any other
 * source clears it.
 *
 * @param saved The overrides the backend holds.
 * @param defaults Languages used where an override is null.
 * @param save Persists new overrides.
 * @param onError Called with the reason a save failed.
 * @returns The languages in effect, and props for `<LanguageControls>`.
 */
export function useLanguageOverrides(saved: LanguageOverrides, defaults: { source: string; target: string }, save: (next: LanguageOverrides) => Promise<void>, onError: (message: string) => void) {
    const [pending, setPending] = useState<LanguageOverrides | null>(null)
    const current = pending ?? saved
    const source = current.source ?? defaults.source
    const target = current.target ?? defaults.target

    /**
     * Show and save new overrides.
     *
     * @param next The overrides to save.
     */
    const change = async (next: LanguageOverrides) => {
        setPending(next)
        try {
            await save(next)
        } catch (err) {
            onError(`Language save failed: ${err instanceof Error ? err.message : String(err)}`)
        } finally {
            setPending(null)
        }
    }

    return {
        source,
        target: source === "English" ? target : "English",
        controls: {
            source,
            target,
            onSourceChange: (value: string) => {
                const next = value || null
                change({ source: next, target: next === "English" ? current.target : null })
            },
            onTargetChange: (value: string) => change({ source: current.source, target: value || null }),
        },
    }
}
