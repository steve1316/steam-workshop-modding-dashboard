import { useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"

/** One entry in a SplitButton's menu. */
export interface SplitButtonItem {
    /** Menu item text. */
    label: string
    /** Called when the item is chosen. The menu closes first. */
    onSelect: () => void
}

/** Props for SplitButton. */
interface SplitButtonProps {
    /** Main button content. */
    label: ReactNode
    onClick: () => void
    items: SplitButtonItem[]
    /** Accessible name of the chevron button. Defaults to "More options". */
    menuLabel?: string
    disabled?: boolean
    /** Disables the chevron. Defaults to `disabled`. */
    menuDisabled?: boolean
    /** Button style. Use `outline` for a secondary action next to a primary one. */
    variant?: "primary" | "outline"
}

/**
 * Button with an attached chevron menu of alternative actions. The menu closes on choice, Escape, or an outside press.
 *
 * @param label Main button content.
 * @param onClick Main button handler.
 * @param items Menu entries.
 * @param menuLabel Chevron accessible name.
 * @param disabled Disables the main button.
 * @param menuDisabled Disables the chevron.
 * @param variant Button style.
 * @returns The split button.
 */
export default function SplitButton({ label, onClick, items, menuLabel = "More options", disabled = false, menuDisabled = disabled, variant = "primary" }: SplitButtonProps) {
    const [open, setOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!open) return
        const onMouseDown = (e: MouseEvent) => {
            if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
        }
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") setOpen(false)
        }
        document.addEventListener("mousedown", onMouseDown)
        document.addEventListener("keydown", onKeyDown)
        return () => {
            document.removeEventListener("mousedown", onMouseDown)
            document.removeEventListener("keydown", onKeyDown)
        }
    }, [open])

    return (
        <div className="split-button" ref={rootRef}>
            <button type="button" className={`btn btn-${variant} split-button-main`} onClick={onClick} disabled={disabled}>
                {label}
            </button>
            <button
                type="button"
                className={`btn btn-${variant} split-button-toggle`}
                aria-label={menuLabel}
                aria-haspopup="menu"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
                disabled={menuDisabled}
            >
                &#9662;
            </button>
            {open && (
                <div className="split-button-menu" role="menu">
                    {items.map((item) => (
                        <button
                            key={item.label}
                            type="button"
                            role="menuitem"
                            className={`btn btn-${variant} split-button-item`}
                            onClick={() => {
                                setOpen(false)
                                item.onSelect()
                            }}
                        >
                            {item.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}
