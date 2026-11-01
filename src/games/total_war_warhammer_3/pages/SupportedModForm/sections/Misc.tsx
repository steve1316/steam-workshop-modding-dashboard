import Panel from "../../../../../ui/Panel"

/** Props for `MiscSection`. */
interface Props {
    ignoreGeneration: boolean
    onChange: (next: boolean) => void
}

/**
 * Section 5 of the SupportedModForm: the `ignore_generation` checkbox, and home for future single-field flags.
 *
 * @param ignoreGeneration Current flag value.
 * @param onChange Called with the next value.
 * @returns The section.
 */
const MiscSection = ({ ignoreGeneration, onChange }: Props) => (
    <Panel as="fieldset" title="Misc">
        <label className="checkbox-row">
            <input type="checkbox" checked={ignoreGeneration} onChange={(e) => onChange(e.target.checked)} /> ignore_generation
        </label>
    </Panel>
)

export default MiscSection
