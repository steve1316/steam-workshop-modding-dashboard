import React, { useState } from "react"
import { FaTimes } from "react-icons/fa"
import Panel from "@/components/ui/Panel"

/** Props for IgnoredModsPanel. */
interface IgnoredModsPanelProps {
    /** Workshop ids hidden from the dashboard. */
    mods: string[]
    onChange: (mods: string[]) => void
}

/**
 * Settings panel for the workshop ids the dashboard hides, shown as removable chips.
 *
 * @param props The ignored ids and their change handler.
 * @returns The ignored mods panel.
 */
const IgnoredModsPanel: React.FC<IgnoredModsPanelProps> = ({ mods, onChange }) => {
    const [newMod, setNewMod] = useState("")
    const canAdd = newMod !== "" && !mods.includes(newMod)

    const add = () => {
        if (!canAdd) return
        onChange([...mods, newMod])
        setNewMod("")
    }

    return (
        <Panel
            className="settings-panel"
            title="Ignored Mods"
            help="Workshop mod IDs listed here will be hidden from the dashboard. Useful for system mods, English-only mods, or mods you don't need to translate."
        >
            <div className="settings-inline-row">
                <input
                    type="text"
                    aria-label="Workshop mod ID"
                    className="input"
                    placeholder="Workshop mod ID"
                    value={newMod}
                    onChange={(e) => setNewMod(e.target.value.trim())}
                    onKeyDown={(e) => {
                        if (e.key === "Enter") add()
                    }}
                />
                <button className="btn btn-primary" disabled={!canAdd} onClick={add}>
                    Add
                </button>
            </div>
            {mods.length > 0 && (
                <div className="chip-list">
                    {mods.map((id) => (
                        <span key={id} className="chip">
                            {id}
                            <button type="button" className="chip-remove" aria-label={`Remove ${id}`} title="Remove" onClick={() => onChange(mods.filter((m) => m !== id))}>
                                <FaTimes />
                            </button>
                        </span>
                    ))}
                </div>
            )}
        </Panel>
    )
}

export default IgnoredModsPanel
