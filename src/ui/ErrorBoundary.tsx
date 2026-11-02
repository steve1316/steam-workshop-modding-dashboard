import { Component } from "react"
import type { ErrorInfo, ReactNode } from "react"

import ErrorState from "@/ui/ErrorState"

/** Props for ErrorBoundary. */
interface ErrorBoundaryProps {
    children: ReactNode
}

/** State for ErrorBoundary. */
interface ErrorBoundaryState {
    /** The error thrown while rendering, or null while everything renders. */
    error: Error | null
}

/**
 * Catches render errors in its children and shows an error state instead of a blank app. App keys it by pathname, so navigating away recovers.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { error: null }

    /**
     * Store the error so the next render shows the fallback.
     *
     * @param error The thrown error.
     * @returns The new state.
     */
    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { error }
    }

    /**
     * Log the crash with its component stack.
     *
     * @param error The thrown error.
     * @param info React's component stack.
     */
    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error("Page crashed:", error, info.componentStack)
    }

    /**
     * Render the children, or the error state after a crash.
     *
     * @returns The children or the fallback.
     */
    render() {
        if (this.state.error) {
            return (
                <ErrorState
                    title="This page hit an error"
                    message={`${this.state.error.message}. Reload the page, or go back and try again.`}
                    action={{ label: "Reload", onClick: () => window.location.reload() }}
                />
            )
        }
        return this.props.children
    }
}
