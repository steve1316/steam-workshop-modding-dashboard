import React from "react"

import Modal from "@/ui/Modal"

/** Props for ConfirmModal. */
interface ConfirmModalProps {
    title: string
    /** Body content: plain text (newlines preserved) or JSX such as a bullet list. */
    message: string | React.ReactNode
    /** Defaults to "Confirm". */
    confirmLabel?: string
    /** Defaults to "Cancel". */
    cancelLabel?: string
    /** Confirm button tone: red for danger, amber for warning, the accent gradient for default. */
    variant?: "danger" | "warning" | "default"
    onConfirm: () => void
    /** Also fires on Escape and backdrop click. */
    onCancel: () => void
}

const VARIANT_CLASS: Record<NonNullable<ConfirmModalProps["variant"]>, string> = {
    danger: "btn btn-danger",
    warning: "btn btn-caution",
    default: "btn btn-primary",
}

/**
 * Confirmation dialog replacing native `window.confirm()`, built on the shared `Modal`.
 *
 * @param props See `ConfirmModalProps`.
 * @returns The confirmation dialog.
 */
const ConfirmModal: React.FC<ConfirmModalProps> = ({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", variant = "default", onConfirm, onCancel }) => {
    return (
        <Modal
            title={title}
            size="sm"
            onClose={onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-outline" onClick={onCancel}>
                        {cancelLabel}
                    </button>
                    <button type="button" className={VARIANT_CLASS[variant]} onClick={onConfirm}>
                        {confirmLabel}
                    </button>
                </>
            }
        >
            <div className="confirm-message">{message}</div>
        </Modal>
    )
}

export default ConfirmModal
