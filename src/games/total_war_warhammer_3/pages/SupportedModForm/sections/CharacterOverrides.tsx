import Panel from "@/ui/Panel"

/** One character entry inside `allowed_lords` or `allowed_heroes`. */
export interface CharacterRow {
    land_unit: string
    agent_subtype: string
    /** Comma-separated skill ids. */
    skill_overrides: string
}

/** One faction section with its allowed lord and hero lists. */
export interface FactionEntry {
    /** Faction code such as `vmp`. */
    faction: string
    allowed_lords: CharacterRow[]
    allowed_heroes: CharacterRow[]
}

/** Props for `CharacterOverridesSection`. */
interface Props {
    value: FactionEntry[]
    onChange: (next: FactionEntry[]) => void
}

/**
 * Section 4 of the SupportedModForm: a nested editor of factions, each with allowed lord and hero rows.
 *
 * @param value Current faction entries.
 * @param onChange Called with the next entries.
 * @returns The section.
 */
const CharacterOverridesSection = ({ value, onChange }: Props) => {
    const updateFaction = (idx: number, patch: Partial<FactionEntry>) => onChange(value.map((f, i) => (i === idx ? { ...f, ...patch } : f)))
    const updateRow = (fIdx: number, key: "allowed_lords" | "allowed_heroes", rIdx: number, patch: Partial<CharacterRow>) =>
        updateFaction(fIdx, {
            [key]: value[fIdx][key].map((row, i) => (i === rIdx ? { ...row, ...patch } : row)),
        } as Partial<FactionEntry>)
    const addRow = (fIdx: number, key: "allowed_lords" | "allowed_heroes") =>
        updateFaction(fIdx, { [key]: [...value[fIdx][key], { land_unit: "", agent_subtype: "", skill_overrides: "" }] } as Partial<FactionEntry>)
    const removeRow = (fIdx: number, key: "allowed_lords" | "allowed_heroes", rIdx: number) => updateFaction(fIdx, { [key]: value[fIdx][key].filter((_, i) => i !== rIdx) } as Partial<FactionEntry>)

    const renderRows = (fIdx: number, key: "allowed_lords" | "allowed_heroes", label: string) => (
        <div className="form-stack">
            <h4 className="form-subheading">{label}</h4>
            {value[fIdx][key].map((row, rIdx) => (
                <div key={rIdx} className="form-row">
                    <input
                        className="input form-grow-2"
                        type="text"
                        aria-label={`${label} ${rIdx + 1} land_unit`}
                        placeholder="land_unit"
                        value={row.land_unit}
                        onChange={(e) => updateRow(fIdx, key, rIdx, { land_unit: e.target.value })}
                    />
                    <input
                        className="input form-grow-2"
                        type="text"
                        aria-label={`${label} ${rIdx + 1} agent_subtype`}
                        placeholder="agent_subtype"
                        value={row.agent_subtype}
                        onChange={(e) => updateRow(fIdx, key, rIdx, { agent_subtype: e.target.value })}
                    />
                    <input
                        className="input form-grow-3"
                        type="text"
                        aria-label={`${label} ${rIdx + 1} skill_overrides`}
                        placeholder="skill_overrides (comma-separated)"
                        value={row.skill_overrides}
                        onChange={(e) => updateRow(fIdx, key, rIdx, { skill_overrides: e.target.value })}
                    />
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => removeRow(fIdx, key, rIdx)}>
                        Remove
                    </button>
                </div>
            ))}
            <button type="button" className="btn btn-outline btn-sm" onClick={() => addRow(fIdx, key)}>
                + Add {label.slice(0, -1).toLowerCase()}
            </button>
        </div>
    )

    return (
        <Panel as="fieldset" title="Character Overrides">
            <div className="form-stack">
                {value.map((faction, fIdx) => (
                    <div key={fIdx} className="form-group-block">
                        <div className="form-row">
                            <label className="field">
                                <span className="field-label">Faction</span>
                                <input className="input" type="text" value={faction.faction} onChange={(e) => updateFaction(fIdx, { faction: e.target.value })} />
                            </label>
                            <button type="button" className="btn btn-outline btn-sm" onClick={() => onChange(value.filter((_, i) => i !== fIdx))}>
                                Remove faction
                            </button>
                        </div>
                        {renderRows(fIdx, "allowed_lords", "Allowed Lords")}
                        {renderRows(fIdx, "allowed_heroes", "Allowed Heroes")}
                    </div>
                ))}
                <button type="button" className="btn btn-outline btn-sm" onClick={() => onChange([...value, { faction: "", allowed_lords: [], allowed_heroes: [] }])}>
                    + Add faction
                </button>
            </div>
        </Panel>
    )
}

export default CharacterOverridesSection
