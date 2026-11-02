import { useSyncExternalStore } from "react"

/** An entry shown in the Runner terminal. */
export type LogEntry =
    | {
          kind: "data"
          line: string
          ts: string
      }
    | {
          kind: "separator"
          text: string
      }

/** Entries kept in the shared singleton. Older ones are dropped. */
export const MAX_LINES = 5000

let _lines: LogEntry[] = []
const listeners = new Set<() => void>()

function notify() {
    for (const listener of listeners) listener()
}

/**
 * Register a listener for log changes.
 *
 * @param listener Called after every change.
 * @returns The unsubscribe function.
 */
function subscribe(listener: () => void): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
}

/**
 * Append one entry to the shared log, trimmed to `MAX_LINES`.
 *
 * @param entry Entry to append.
 */
export function appendLine(entry: LogEntry) {
    _lines = [..._lines, entry].slice(-MAX_LINES)
    notify()
}

/** Empty the shared log. */
export function clearLog() {
    _lines = []
    notify()
}

/**
 * Subscribe to the shared runner log. A module-level singleton keeps the buffer across navigation.
 *
 * @returns The current entries.
 */
export function useRunnerLog(): LogEntry[] {
    return useSyncExternalStore(subscribe, () => _lines)
}

/** Test-only: reset the module singleton between tests. */
export function _resetUseRunnerLogForTests() {
    _lines = []
    listeners.clear()
}
