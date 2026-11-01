import { createContext, useContext, useEffect, useId, useRef } from "react"
import type { MouseEvent, ReactNode } from "react"
import { createPortal } from "react-dom"

/** Width presets: sm 500px, md 700px, lg 900px, xl 75% of the viewport. */
export type ModalSize = "sm" | "md" | "lg" | "xl"

/** Props for Modal. */
interface ModalProps {
    /** Heading shown at the top of the panel. Also the dialog's accessible name. */
    title: ReactNode
    subtitle?: ReactNode
    size?: ModalSize
    onClose: () => void
    /** Ignore every close path, e.g. while a publish is running. */
    closeDisabled?: boolean
    closeDisabledReason?: string
    /** Controls rendered in the header, left of the X button. */
    headerActions?: ReactNode
    /** Right-aligned button row pinned under the body. */
    footer?: ReactNode
    /** Make the body a flex column filling the panel, for editors and lists that scroll themselves. */
    fill?: boolean
    children: ReactNode
}

/** One open dialog in the Escape stack. */
interface OpenDialog {
    id: string
    /** How many dialogs enclose this one in the React tree (0 for a top-level dialog). */
    depth: number
    /** Mount sequence number, used to break ties between dialogs at the same depth. */
    order: number
}

// The topmost dialog is the deepest in the React tree, then the most recent. Mount order alone fails because React runs a child's effects
// before its parent's.
const openDialogs: OpenDialog[] = []
let mountCounter = 0
const DialogDepth = createContext(0)

/**
 * Whether Escape should close this dialog.
 *
 * @param id - Dialog's `useId` value.
 * @returns True when it is the deepest, most recent dialog.
 */
function isTopDialog(id: string): boolean {
    const top = openDialogs.reduce<OpenDialog | null>((best, d) => (!best || d.depth > best.depth || (d.depth === best.depth && d.order > best.order) ? d : best), null)
    return top?.id === id
}

/**
 * Shared dialog. Portals to `document.body` so an ancestor's glass-card containment can't clip it, closes only the topmost on Escape,
 * and ignores backdrop clicks whose press started inside the panel (text-selection drags).
 *
 * @param title - Heading and accessible name.
 * @param subtitle - Dim line under the title.
 * @param size - Width preset.
 * @param onClose - Close handler.
 * @param closeDisabled - Block every close path.
 * @param closeDisabledReason - Tooltip for the disabled X button.
 * @param headerActions - Header controls left of the X button.
 * @param footer - Right-aligned button row.
 * @param fill - Make the body a height-filling flex column.
 * @param children - Dialog body.
 * @returns The dialog.
 */
export default function Modal({ title, subtitle, size = "md", onClose, closeDisabled = false, closeDisabledReason, headerActions, footer, fill = false, children }: ModalProps) {
    const id = useId()
    const depth = useContext(DialogDepth)
    const titleId = `${id}-title`
    const pressStartedOnBackdrop = useRef(false)
    const onCloseRef = useRef(onClose)
    const closeDisabledRef = useRef(closeDisabled)

    useEffect(() => {
        onCloseRef.current = onClose
        closeDisabledRef.current = closeDisabled
    }, [onClose, closeDisabled])

    useEffect(() => {
        openDialogs.push({ id, depth, order: ++mountCounter })
        const onKeyDown = (e: KeyboardEvent) => {
            // Escape during IME composition cancels the composition, not the dialog.
            if (e.key !== "Escape" || e.isComposing || !isTopDialog(id) || closeDisabledRef.current) return
            onCloseRef.current()
        }
        document.addEventListener("keydown", onKeyDown)
        return () => {
            document.removeEventListener("keydown", onKeyDown)
            openDialogs.splice(
                openDialogs.findIndex((d) => d.id === id),
                1
            )
        }
    }, [id, depth])

    const onBackdropMouseDown = (e: MouseEvent<HTMLDivElement>) => {
        pressStartedOnBackdrop.current = e.target === e.currentTarget
    }

    const onBackdropClick = (e: MouseEvent<HTMLDivElement>) => {
        const startedHere = pressStartedOnBackdrop.current
        pressStartedOnBackdrop.current = false
        if (e.target !== e.currentTarget || !startedHere || closeDisabled) return
        onClose()
    }

    return createPortal(
        // Deeper dialogs paint above their parents, the same order Escape closes them in.
        <div className="dialog-backdrop" style={{ zIndex: 1000 + depth }} onMouseDown={onBackdropMouseDown} onClick={onBackdropClick}>
            <div className={`glass-card dialog-panel dialog-${size}${fill ? " dialog-fill" : ""}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
                <DialogDepth.Provider value={depth + 1}>
                    <div className="dialog-header">
                        <div className="dialog-title-group">
                            <h2 id={titleId} className="dialog-title">
                                {title}
                            </h2>
                            {subtitle && <div className="dialog-subtitle">{subtitle}</div>}
                        </div>
                        <div className="dialog-header-actions">
                            {headerActions}
                            <button type="button" className="dialog-close" onClick={onClose} disabled={closeDisabled} aria-label="Close" title={closeDisabled ? closeDisabledReason : "Close"}>
                                &times;
                            </button>
                        </div>
                    </div>
                    <div className="dialog-body">{children}</div>
                    {footer && <div className="dialog-footer">{footer}</div>}
                </DialogDepth.Provider>
            </div>
        </div>,
        document.body
    )
}
