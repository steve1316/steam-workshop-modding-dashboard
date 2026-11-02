import type { ReactNode } from "react"

/** Props for Panel. */
interface PanelProps {
    /** Heading rendered as an h3, or as the legend when `as` is `fieldset`. */
    title?: ReactNode
    /** Dim help line under the heading. */
    help?: ReactNode
    /** Extra class for page-specific layout, e.g. `context-panel`. */
    className?: string
    /** Element to render. A `fieldset` names its group of form controls by its legend. Defaults to `section`. */
    as?: "section" | "fieldset"
    children?: ReactNode
}

/**
 * Static glass card for inline page sections. Unlike the dashboard cards it never lifts on hover.
 *
 * @param title Heading.
 * @param help Help line under the heading.
 * @param className Extra class.
 * @param as Element to render.
 * @param children Panel body.
 * @returns The panel.
 */
export default function Panel({ title, help, className, as = "section", children }: PanelProps) {
    const classes = `glass-card static panel${className ? ` ${className}` : ""}`
    const helpLine = help && <p className="help-text panel-help">{help}</p>
    if (as === "fieldset") {
        return (
            <fieldset className={classes}>
                {title && <legend className="panel-title panel-legend">{title}</legend>}
                {helpLine}
                {children}
            </fieldset>
        )
    }
    return (
        <section className={classes}>
            {title && <h3 className="panel-title">{title}</h3>}
            {helpLine}
            {children}
        </section>
    )
}
