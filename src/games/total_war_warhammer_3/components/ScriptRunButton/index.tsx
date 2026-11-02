import { useNavigate } from "react-router-dom"
import { useGameSlug } from "@/hooks/useGameSlug"
import { startRun } from "@/games/total_war_warhammer_3/lib/registryApi"
import { kickPoll, useCurrentRun } from "@/games/total_war_warhammer_3/hooks/useCurrentRun"
import StepIndicator from "@/games/total_war_warhammer_3/components/StepIndicator"

/** Props for `ScriptRunButton`. */
interface Props {
    scriptId: string
    label: string
    style?: React.CSSProperties
    className?: string
}

/**
 * Button that posts to `/run/{scriptId}` and navigates to the Runner page. Disabled during another run, or replaced by a `StepIndicator` while `update` rebuilds this script.
 *
 * @param scriptId Backend script id.
 * @param label Idle button label.
 * @param style Inline style overrides.
 * @param className Extra classes after `btn btn-primary`.
 * @returns The button, or the pipeline step indicator.
 */
export default function ScriptRunButton({ scriptId, label, style, className }: Props) {
    const run = useCurrentRun()
    const navigate = useNavigate()
    const slug = useGameSlug()
    const disabled = run.status === "running"
    const step = run.status === "running" ? run.steps?.[scriptId] : undefined

    const handleClick = async () => {
        try {
            await startRun(scriptId)
            navigate(`/${slug}/runner`)
        } catch (err) {
            console.error("Failed to start run", err)
        } finally {
            kickPoll()
        }
    }

    if (step) return <StepIndicator status={step} className={className} />

    return (
        <button className={`btn btn-primary${className ? ` ${className}` : ""}`} disabled={disabled} onClick={handleClick} style={style}>
            {disabled ? "Run in progress..." : label}
        </button>
    )
}
