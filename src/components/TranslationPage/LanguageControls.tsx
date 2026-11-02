import { useId } from "react"

/** One selectable language: the value the backend stores and the label shown. */
interface LanguageOption {
    /** Stored language value, e.g. "Chinese-TW [zh-tw]". */
    value: string
    label: string
}

/** Languages a mod's source text can be written in. */
const SOURCE_LANGUAGES: LanguageOption[] = [
    { value: "Chinese", label: "Chinese" },
    { value: "Korean", label: "Korean" },
    { value: "Japanese", label: "Japanese" },
    { value: "Chinese-TW [zh-tw]", label: "Chinese-TW" },
    { value: "English", label: "English" },
]

/** Languages offered as the target when the source is English. */
const TARGET_LANGUAGES: LanguageOption[] = SOURCE_LANGUAGES.filter((l) => l.value !== "English")

/** Props for LanguageControls. */
interface LanguageControlsProps {
    source: string
    /** Selected target language value. Only shown when `source` is English. */
    target: string
    /** Source language changed. */
    onSourceChange: (value: string) => void
    /** Target language changed. */
    onTargetChange: (value: string) => void
}

/**
 * Source language dropdown in the page header, plus a target dropdown when the source is English.
 *
 * @param source - Selected source language.
 * @param target - Selected target language.
 * @param onSourceChange - Source change handler.
 * @param onTargetChange - Target change handler.
 * @returns The language controls.
 */
export function LanguageControls({ source, target, onSourceChange, onTargetChange }: LanguageControlsProps) {
    const id = useId()
    return (
        <div className="language-controls">
            <label htmlFor={`${id}-source`} className="language-controls-label">
                Source Language:
            </label>
            <select id={`${id}-source`} className="lang-select" value={source} onChange={(e) => onSourceChange(e.target.value)}>
                {SOURCE_LANGUAGES.map((l) => (
                    <option key={l.value} value={l.value}>
                        {l.label}
                    </option>
                ))}
            </select>
            {source === "English" && (
                <>
                    <span className="language-controls-arrow" aria-hidden="true">
                        &rarr;
                    </span>
                    <select aria-label="Target Language" className="lang-select" value={target} onChange={(e) => onTargetChange(e.target.value)}>
                        {TARGET_LANGUAGES.map((l) => (
                            <option key={l.value} value={l.value}>
                                {l.label}
                            </option>
                        ))}
                    </select>
                </>
            )}
        </div>
    )
}
