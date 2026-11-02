import type { CSSProperties, ReactNode } from "react"
import { StringsTable } from "@/components/TranslationPage/StringsTable"
import { FeedbackBanner } from "@/components/TranslationPage/FeedbackBanner"
import { TranslatingBanner } from "@/components/TranslationPage/TranslatingBanner"
import type { ColumnDef } from "@/components/TranslationPage/types"
import PageHeader from "@/components/ui/PageHeader"
import SearchInput from "@/components/ui/SearchInput"
import "@/components/TranslationPage/styles.css"

/** One status filter pill. */
interface StatusFilter {
    value: string
    label: string
}

/** In-progress translation state for the banner. */
interface TranslatingState {
    /** Zero-based current batch index. */
    batchIndex: number
    totalBatches: number
    /** Live streaming stats. */
    streaming?: { tokensGenerated: number; tokensPerSec: number; elapsedSec: number }
}

/** Props for the shared TranslationPage shell. */
interface TranslationPageProps<Row> {
    title: string
    /** Progress text, e.g. "3 / 10 total strings translated". */
    progressLabel: string
    /** Status filter pills (including the "all" pill). */
    statusFilters: StatusFilter[]
    activeFilter: string
    onFilterChange: (value: string) => void
    search: string
    onSearchChange: (value: string) => void
    columns: ColumnDef<Row>[]
    /** Rows to display (already filtered/sorted by the caller). */
    rows: Row[]
    getRowKey: (row: Row) => string
    sortField: string | null
    sortDirection: "asc" | "desc" | null
    onSort: (field: string) => void
    /** Per-field width overrides. Omit to use each column's default `width`. */
    columnWidths?: Record<string, number>
    /** Called with the new pixel width while dragging a resizer. Omit to make columns fixed. */
    onResizeColumn?: (field: string, width: number) => void
    /** Per-row CSS class (e.g. to tint AI rows). */
    getRowClassName?: (row: Row) => string | undefined
    /** Per-row inline style (e.g. status background). */
    getRowStyle?: (row: Row) => CSSProperties | undefined
    banner?: { type: "success" | "error"; message: string } | null
    onDismissBanner?: () => void
    translating?: TranslatingState | null
    onCancelTranslate?: () => void
    /** Game-specific action toolbar in the header. */
    toolbar?: ReactNode
    emptyMessage?: string
    /** Back handler. Renders a "Back to Dashboard" button when given. */
    onBack?: () => void
    /** Preview image URL, shown as an 80x80 thumbnail left of the title. */
    previewImage?: string | null
    /** Inline elements next to the title (e.g. Steam link, pending-sync badge). */
    titleBadges?: ReactNode
    /** Line under the title (e.g. "by author"). */
    subtitle?: ReactNode
    /** Source/target language controls in the header. */
    languageControls?: ReactNode
    /** Extra banners below the built-in ones (e.g. batch paused). */
    extraBanners?: ReactNode
    /** Inline panels between the banners and the search bar (e.g. context panel). */
    panels?: ReactNode
    /** Game-specific modals rendered at the end of the page. */
    modals?: ReactNode
}

/**
 * Shared translation page shell. Presentational: each game's container owns the data and state and supplies columns, rows, slots and handlers.
 * @param props - See `TranslationPageProps`.
 * @returns The translation page.
 */
export function TranslationPage<Row>(props: TranslationPageProps<Row>) {
    const {
        title,
        progressLabel,
        statusFilters,
        activeFilter,
        onFilterChange,
        search,
        onSearchChange,
        columns,
        rows,
        getRowKey,
        sortField,
        sortDirection,
        onSort,
        columnWidths,
        onResizeColumn,
        getRowClassName,
        getRowStyle,
        banner,
        onDismissBanner,
        translating,
        onCancelTranslate,
        toolbar,
        emptyMessage,
        onBack,
        previewImage,
        titleBadges,
        subtitle,
        languageControls,
        extraBanners,
        panels,
        modals,
    } = props
    return (
        <div className="mod-detail">
            <PageHeader
                title={title}
                onBack={onBack}
                image={previewImage}
                imageAlt={title}
                adornments={titleBadges}
                subtitle={subtitle}
                meta={
                    <>
                        {languageControls}
                        <p className="page-header-progress">{progressLabel}</p>
                    </>
                }
                actions={toolbar}
            />

            {translating && <TranslatingBanner batchIndex={translating.batchIndex} totalBatches={translating.totalBatches} streaming={translating.streaming} onCancel={() => onCancelTranslate?.()} />}

            {extraBanners}

            {banner && <FeedbackBanner type={banner.type} message={banner.message} onDismiss={() => onDismissBanner?.()} />}

            {panels}

            <div className="glass-card" style={{ padding: "1.5rem", marginBottom: "2rem" }}>
                <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                    <SearchInput value={search} onChange={onSearchChange} placeholder="Search keys or text..." />
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                        {statusFilters.map((f) => (
                            <button key={f.value} className={`filter-pill btn ${activeFilter === f.value ? "btn-primary" : "btn-outline"}`} onClick={() => onFilterChange(f.value)}>
                                {f.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <StringsTable
                rows={rows}
                columns={columns}
                getRowKey={getRowKey}
                sortField={sortField}
                sortDirection={sortDirection}
                onSort={onSort}
                columnWidths={columnWidths}
                onResizeColumn={onResizeColumn}
                getRowClassName={getRowClassName}
                getRowStyle={getRowStyle}
                emptyMessage={emptyMessage}
            />

            {modals}
        </div>
    )
}
