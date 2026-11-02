import type { ReactNode } from "react"

import PageHeader from "@/ui/PageHeader"
import SearchInput from "@/ui/SearchInput"

/** Props for DashboardHeader. */
interface DashboardHeaderProps {
    /** e.g. "Workshop Dashboard". */
    title: string
    tagline: string
    search: string
    /** Called with the new search text on every keystroke, and with "" when cleared. */
    onSearchChange: (value: string) => void
    searchPlaceholder: string
    /** Pixels, from `useCardWidth`. Falls back to 320px before a card has rendered. */
    searchWidth?: number
    actions?: ReactNode
}

/**
 * Shared dashboard header: the page title and tagline, then one row with a search field as wide as a card column and the page's actions.
 *
 * @param title Page title.
 * @param tagline Line under the title.
 * @param search Current search text.
 * @param onSearchChange Search change handler.
 * @param searchPlaceholder Search placeholder.
 * @param searchWidth Card column width for the search field.
 * @param actions Buttons after the search field.
 * @returns The dashboard header.
 */
export default function DashboardHeader({ title, tagline, search, onSearchChange, searchPlaceholder, searchWidth, actions }: DashboardHeaderProps) {
    return (
        <PageHeader
            title={title}
            meta={<p className="dashboard-tagline">{tagline}</p>}
            actionsClassName="dashboard-toolbar"
            actions={
                <>
                    <SearchInput value={search} onChange={onSearchChange} placeholder={searchPlaceholder} width={searchWidth ?? 320} />
                    {actions}
                </>
            }
        />
    )
}
