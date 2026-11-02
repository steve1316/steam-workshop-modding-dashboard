import type { ReactNode } from "react"
import { FaBook } from "react-icons/fa"

/** A toolbar button's click handler. */
interface ToolbarAction {
    onClick: () => void
}

/** A toolbar button that shows a count. */
interface CountedAction extends ToolbarAction {
    count: number
}

/** The Scan for Terms button. */
interface ScanAction extends ToolbarAction {
    /** True while a scan runs. The button reads "Scanning..." and is disabled. */
    scanning: boolean
}

/** The context toggle (Character Context or Mod Context). */
interface ContextAction extends ToolbarAction {
    label: string
    /** Shows a teal dot while any context field is filled in. */
    hasContext: boolean
}

/** Props for TranslationToolbar. Every action is optional, and an omitted action hides its button. */
interface TranslationToolbarProps {
    /** Opens the mod glossary. */
    glossary?: CountedAction
    /** Opens the pending suggestions review. Hidden while the count is zero. */
    suggestions?: CountedAction
    /** Scans the mod for glossary terms. */
    scan?: ScanAction
    apiResponses?: ToolbarAction
    /** Toggles the inline context panel. */
    context?: ContextAction
    history?: ToolbarAction
    reset?: ToolbarAction
    /** Clears every English translation. */
    clearEnglish?: ToolbarAction
    /** Game-specific buttons placed before Translate, such as WH3's Translate Names. */
    extraActions?: ReactNode
    translate?: ReactNode
    sync?: ReactNode
}

/**
 * The translation page's stateless action row, laid out in three groups (glossary tools, history and destructive actions, translate and sync).
 *
 * @param props - See `TranslationToolbarProps`.
 * @returns The toolbar.
 */
export function TranslationToolbar({ glossary, suggestions, scan, apiResponses, context, history, reset, clearEnglish, extraActions, translate, sync }: TranslationToolbarProps) {
    return (
        <>
            <div className="mod-actions-group">
                {glossary && (
                    <button type="button" className="btn btn-outline" onClick={glossary.onClick}>
                        <FaBook /> Mod Glossary ({glossary.count})
                    </button>
                )}
                {suggestions && suggestions.count > 0 && (
                    <button type="button" className="btn btn-outline btn-suggestions" onClick={suggestions.onClick}>
                        <FaBook /> Suggestions
                        <span className="btn-badge">{suggestions.count}</span>
                    </button>
                )}
                {scan && (
                    <button type="button" className="btn btn-outline" onClick={scan.onClick} disabled={scan.scanning}>
                        <FaBook /> {scan.scanning ? "Scanning..." : "Scan for Terms"}
                    </button>
                )}
                {apiResponses && (
                    <button type="button" className="btn btn-outline" onClick={apiResponses.onClick}>
                        API Responses
                    </button>
                )}
                {context && (
                    <button type="button" className="btn btn-outline tone-teal" onClick={context.onClick}>
                        {context.label}
                        {context.hasContext && <span className="btn-dot" aria-hidden="true" />}
                    </button>
                )}
            </div>

            <div className="mod-actions-group">
                {history && (
                    <button type="button" className="btn btn-outline" onClick={history.onClick}>
                        History
                    </button>
                )}
                {reset && (
                    <button type="button" className="btn btn-outline tone-danger" onClick={reset.onClick}>
                        Reset
                    </button>
                )}
                {clearEnglish && (
                    <button type="button" className="btn btn-outline tone-warning" onClick={clearEnglish.onClick}>
                        Clear English
                    </button>
                )}
            </div>

            <div className="mod-actions-group">
                {extraActions}
                {translate}
                {sync}
            </div>
        </>
    )
}
