import type { CSSProperties } from "react"
import type { RowStatus } from "@/utils/stringFilters"

/**
 * Background tint for a translation table row.
 * @param status - Row status.
 * @param opts - `override` marks an unsynced edit, where the translation differs from the synced value.
 * @returns The style, or undefined for no tint.
 */
export function canonicalRowStyle(status: RowStatus, opts: { override?: boolean } = {}): CSSProperties | undefined {
    if (status === "untranslatable") return { backgroundColor: "rgba(148, 163, 184, 0.1)" }
    if (status === "synced") return { backgroundColor: "rgba(52, 211, 153, 0.1)" }
    if (status === "changed") return { backgroundColor: "rgba(249, 115, 22, 0.1)" }
    if (opts.override) return { backgroundColor: "rgba(255, 220, 40, 0.15)" }
    return undefined
}
