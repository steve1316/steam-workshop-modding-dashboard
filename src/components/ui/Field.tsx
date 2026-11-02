import type { ReactNode } from "react"

/** Props for Field. */
interface FieldProps {
    /** Visible label text. */
    label: ReactNode
    /** Id of the control inside `children`, linking the label to it. */
    htmlFor: string
    children: ReactNode
    /** Extra classes for the wrapper, e.g. a flex sizing class. */
    className?: string
}

/**
 * A labeled form control using Chrono Ark's field style: a small uppercase dim label above a dark input.
 *
 * @param label Visible label text.
 * @param htmlFor Id of the control the label describes.
 * @param children The form control.
 * @param className Extra wrapper classes.
 * @returns The labeled field.
 */
export default function Field({ label, htmlFor, children, className }: FieldProps) {
    return (
        <div className={`field${className ? ` ${className}` : ""}`}>
            <label className="field-label" htmlFor={htmlFor}>
                {label}
            </label>
            {children}
        </div>
    )
}
