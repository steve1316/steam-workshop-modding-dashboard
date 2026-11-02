import { useState } from "react"
import { FaTimes } from "react-icons/fa"

import Panel from "@/components/ui/Panel"

/** Props for `ModifiedAttributesSection`. */
interface Props {
    value: string[]
    /** Top-level `SUPPORTED_EFFECTS` keys. */
    suggestions: string[]
    onChange: (next: string[]) => void
}

/**
 * Section 2 of the SupportedModForm: removable attribute chips and an input that adds one on Enter, with `<datalist>` suggestions.
 *
 * @param value Current attributes.
 * @param suggestions Autocomplete suggestions.
 * @param onChange Called with the next list.
 * @returns The section.
 */
const ModifiedAttributesSection = ({ value, suggestions, onChange }: Props) => {
    const [draft, setDraft] = useState("")
    const commit = () => {
        const trimmed = draft.trim()
        if (!trimmed || value.includes(trimmed)) {
            setDraft("")
            return
        }
        onChange([...value, trimmed])
        setDraft("")
    }
    return (
        <Panel as="fieldset" title="Modified Attributes">
            <div className="form-stack">
                {value.length > 0 && (
                    <div className="chip-list">
                        {value.map((attr) => (
                            <span key={attr} className="chip">
                                {attr}
                                <button type="button" className="chip-remove" aria-label={`Remove ${attr}`} onClick={() => onChange(value.filter((v) => v !== attr))}>
                                    <FaTimes />
                                </button>
                            </span>
                        ))}
                    </div>
                )}
                <input
                    className="input"
                    type="text"
                    list="modified-attribute-suggestions"
                    aria-label="Add attribute"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter") {
                            e.preventDefault()
                            commit()
                        }
                    }}
                    onBlur={commit}
                    placeholder="Add attribute (Enter to commit)"
                />
                <datalist id="modified-attribute-suggestions">
                    {suggestions.map((s) => (
                        <option key={s} value={s} />
                    ))}
                </datalist>
            </div>
        </Panel>
    )
}

export default ModifiedAttributesSection
