import type { StepStatus } from "@/games/total_war_warhammer_3/api"
import StepIndicator from "@/games/total_war_warhammer_3/components/StepIndicator"

/** One helper-script entry rendered as a `ScriptCard`. */
export interface ScriptEntry {
    id: string
    label: string
    description: string
}

/** Props for `ScriptCard`. */
interface Props {
    script: ScriptEntry
    running: boolean
    disabled: boolean
    /** Replaces the Run button when set. */
    step?: StepStatus
    onRun: (scriptId: string) => void
    onCancel: () => void
}

/**
 * Runner page card for one helper script. The footer button toggles between Run, Cancel and disabled, or becomes a `StepIndicator` during the `update` pipeline.
 *
 * @param script Script metadata.
 * @param running This script is the active run.
 * @param disabled Another script is running.
 * @param step Progress inside a running `update` pipeline.
 * @param onRun Called with the script id on Run.
 * @param onCancel Called on Cancel.
 * @returns The card.
 */
export default function ScriptCard({ script, running, disabled, step, onRun, onCancel }: Props) {
    return (
        <div className="glass-card script-card">
            <h3 className="script-card-title">{script.label}</h3>
            <p className="script-card-description">{script.description}</p>
            {running ? (
                <button className="btn btn-outline" onClick={onCancel}>
                    Cancel
                </button>
            ) : step ? (
                <StepIndicator status={step} />
            ) : (
                <button className="btn btn-primary" onClick={() => onRun(script.id)} disabled={disabled}>
                    Run
                </button>
            )}
        </div>
    )
}
