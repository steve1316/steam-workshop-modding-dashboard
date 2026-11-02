import { API_BASE } from "@/lib/api"
import Panel from "@/components/ui/Panel"
import type { BasicsState } from "@/games/total_war_warhammer_3/pages/SupportedModForm/sections/basicsState"

/** Props for `BasicsSection`. */
interface Props {
    value: BasicsState
    onChange: (next: BasicsState) => void
    /** Makes `package_name` read-only, as in edit mode. */
    lockPackageName: boolean
}

/**
 * Section 1 of the SupportedModForm: Name, Package name, Workshop ID, the Custom-path toggle, and the preview image.
 *
 * @param value Current state.
 * @param onChange Called with the next state.
 * @param lockPackageName Disables `package_name` when editing.
 * @returns The section.
 */
const BasicsSection = ({ value, onChange, lockPackageName }: Props) => {
    const previewUrl = value.workshop_id ? `${API_BASE}/games/total_war_warhammer_3/packs/${value.workshop_id}/preview` : null
    return (
        <Panel as="fieldset" title="Basics">
            <div className="form-stack">
                <label className="field">
                    <span className="field-label">Name</span>
                    <input className="input" type="text" value={value.name} onChange={(e) => onChange({ ...value, name: e.target.value })} />
                </label>
                <label className="field">
                    <span className="field-label">Package name</span>
                    <input className="input" type="text" value={value.package_name} disabled={lockPackageName} onChange={(e) => onChange({ ...value, package_name: e.target.value })} />
                </label>
                <label className="field">
                    <span className="field-label">Workshop ID</span>
                    <input className="input" type="text" value={value.workshop_id} onChange={(e) => onChange({ ...value, workshop_id: e.target.value })} />
                </label>
                <label className="checkbox-row">
                    <input type="checkbox" checked={value.custom_path} onChange={(e) => onChange({ ...value, custom_path: e.target.checked })} /> Custom path (advanced)
                </label>
                {value.custom_path && (
                    <label className="field">
                        <span className="field-label">Custom path</span>
                        <input className="input input-mono" type="text" value={value.path} onChange={(e) => onChange({ ...value, path: e.target.value })} />
                    </label>
                )}
                {previewUrl && <img className="form-preview-image" src={previewUrl} alt={value.name || "Preview"} loading="lazy" />}
            </div>
        </Panel>
    )
}

export default BasicsSection
