import { useCallback, useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"

import ConfirmModal from "@/components/ui/ConfirmModal"

/** What one confirmation prompt shows. Mirrors `ConfirmModal`'s props without the callbacks. */
export interface ConfirmOptions {
    title: string
    /** Plain text (newlines preserved) or JSX. */
    message: ReactNode
    /** Text for the confirm button. Defaults to "Confirm". */
    confirmLabel?: string
    /** Text for the cancel button. Defaults to "Cancel". */
    cancelLabel?: string
    /** Confirm button tone. Defaults to "default". */
    variant?: "danger" | "warning" | "default"
}

/** A prompt waiting for the user's answer. */
interface PendingConfirm {
    /** What the dialog shows. */
    options: ConfirmOptions
    /** Settles the promise returned by `confirm`. */
    resolve: (confirmed: boolean) => void
}

/**
 * Promise-based replacement for `window.confirm`. Call `confirm(options)` and await the answer, and render `confirmDialog` somewhere in the
 * component. A prompt that is still open when the component unmounts, or when a newer prompt replaces it, settles to `false`.
 *
 * @returns `confirm` to ask a question, and `confirmDialog` to render.
 */
export function useConfirm(): { confirm: (options: ConfirmOptions) => Promise<boolean>; confirmDialog: ReactNode } {
    const [pending, setPending] = useState<PendingConfirm | null>(null)
    const pendingRef = useRef<PendingConfirm | null>(null)

    useEffect(() => {
        pendingRef.current = pending
    }, [pending])

    // Never leave an awaiting caller hanging after unmount.
    useEffect(() => () => pendingRef.current?.resolve(false), [])

    const confirm = useCallback(
        (options: ConfirmOptions) =>
            new Promise<boolean>((resolve) => {
                pendingRef.current?.resolve(false)
                const next = { options, resolve }
                pendingRef.current = next
                setPending(next)
            }),
        []
    )

    const settle = (confirmed: boolean) => {
        pending?.resolve(confirmed)
        pendingRef.current = null
        setPending(null)
    }

    const confirmDialog = pending ? <ConfirmModal {...pending.options} onConfirm={() => settle(true)} onCancel={() => settle(false)} /> : null
    return { confirm, confirmDialog }
}
