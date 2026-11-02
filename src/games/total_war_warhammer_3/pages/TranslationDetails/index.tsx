import React, { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import GlossarySuggestionModal from "@/components/GlossarySuggestionModal"
import TranslationConfirmModal from "@/components/TranslationConfirmModal"
import { API_BASE } from "@/lib/api"
import { useGameSlug } from "@/hooks/useGameSlug"
import { useLanguageOverrides } from "@/hooks/useLanguageOverrides"
import { useModContext } from "@/hooks/useModContext"
import { useTableView } from "@/hooks/useTableView"
import { useTranslationRun } from "@/hooks/useTranslationRun"
import { StatusBadge } from "@/components/TranslationPage/StatusBadge"
import { TranslationPage } from "@/components/TranslationPage"
import { TranslationToolbar } from "@/components/TranslationPage/TranslationToolbar"
import { SyncButton } from "@/components/TranslationPage/SyncButton"
import { BatchReviewBanner } from "@/components/TranslationPage/BatchReviewBanner"
import { ContextPanel } from "@/components/TranslationPage/ContextPanel"
import SplitButton from "@/components/ui/SplitButton"
import { LanguageControls } from "@/components/TranslationPage/LanguageControls"
import { OpenFolderButton, PendingSyncPill, SteamLink } from "@/components/TranslationPage/TitleAdornments"
import { TranslationCell } from "@/components/TranslationPage/TranslationCell"
import { canonicalRowStyle, TRANSLATION_COLUMN_WIDTHS, translationColumns } from "@/components/TranslationPage/helpers"
import HighlightText from "@/components/ui/HighlightText"
import LoadingState from "@/components/ui/LoadingState"
import type { RowStatus, TermSuggestion } from "@/lib/types"
import type { WH3DriftRow, WH3ModContext, WH3RescanSummary, WH3TranslationModSummary } from "@/games/total_war_warhammer_3/lib/types"
import ApiResponsesModal from "@/games/total_war_warhammer_3/components/ApiResponsesModal"
import HistoryModal from "@/games/total_war_warhammer_3/components/HistoryModal"
import ModGlossaryModal from "@/games/total_war_warhammer_3/components/ModGlossaryModal"
import {
    clearTranslations,
    fetchModContext,
    fetchStrings,
    listTranslationMods,
    loadGlossary,
    loadNameSuggestions,
    openModFolder,
    openSourceFile,
    previewTranslation,
    acceptChanged,
    rescanMod,
    saveModContext,
    saveString,
    syncChanges,
    type WH3NameStage,
    type WH3TranslationPreview,
} from "@/games/total_war_warhammer_3/lib/translationApi"
import { useConfirm } from "@/hooks/useConfirm"

// Canonical status filter pills. WH3 never emits "untouched", but the pill is kept for parity with Chrono Ark.
const STATUS_FILTERS: Array<{ value: RowStatus | "all"; label: string }> = [
    { value: "all", label: "All" },
    { value: "missing", label: "Missing" },
    { value: "untouched", label: "Untouched" },
    { value: "pending", label: "Pending" },
    { value: "changed", label: "Changed" },
    { value: "synced", label: "Synced" },
]

type ModalKey = "glossary" | "responses" | "history" | "reset" | null

/** A staged Translate Names run in progress. */
type NamesRun = {
    stages: WH3NameStage[]
    /** Index of the running or just-reviewed stage. */
    index: number
    provider: string
    translated: number
}

/** The finished stage a review dialog or paused banner describes. */
type StageStep = {
    /** Zero-based. */
    index: number
    total: number
    label: string
    /** Null when the finished stage was the last. */
    nextLabel: string | null
}

/**
 * Describe the stage a names run just finished.
 *
 * @param run The names run.
 * @returns The finished stage's position and labels.
 */
function stageStep(run: NamesRun): StageStep {
    return { index: run.index, total: run.stages.length, label: run.stages[run.index].label, nextLabel: run.stages[run.index + 1]?.label ?? null }
}

/** Providers the web app can run, for the Translate menu. Manual is CLI-only. */
const WEB_PROVIDERS = ["claude", "openai", "deepl", "ollama", "llamacpp"]

/**
 * Capitalize a provider id for a button label.
 *
 * @param id Provider id.
 * @returns The label.
 */
const providerLabel = (id: string) => id.charAt(0).toUpperCase() + id.slice(1)

type SortField = "status" | "provider" | "source_filename" | "key" | "parent_text" | "translation_text"

/**
 * Confirm text for WH3's Sync button.
 *
 * @param resync True for a re-sync with nothing new pending.
 * @returns The dialog body.
 */
const wh3SyncMessage = (resync: boolean) =>
    `${resync ? "Nothing has changed since the last sync. Re-syncing writes every translation again.\n\n" : ""}This will overwrite the mod's .loc.tsv files with your translations and rebuild the translation pack. Continue?`

const EMPTY_MOD_CONTEXT: WH3ModContext = { source_game: "", character_name: "", background: "", source_language_override: null, target_language_override: null }

const COLUMN_WIDTH_KEY = "wh3-translation-column-widths"

const DEFAULT_COLUMN_WIDTHS: Record<SortField, number> = {
    status: TRANSLATION_COLUMN_WIDTHS.status,
    provider: TRANSLATION_COLUMN_WIDTHS.mode,
    source_filename: TRANSLATION_COLUMN_WIDTHS.source,
    key: TRANSLATION_COLUMN_WIDTHS.key,
    parent_text: TRANSLATION_COLUMN_WIDTHS.original,
    translation_text: TRANSLATION_COLUMN_WIDTHS.translation,
}

/**
 * Keep the rows the status filter and search allow.
 *
 * @param rows All rows.
 * @param filter Status pill, or `all`.
 * @param search Text matched against the key, original and translation.
 * @returns The matching rows.
 */
function selectRows(rows: WH3DriftRow[], filter: RowStatus | "all", search: string): WH3DriftRow[] {
    let picked = rows
    if (filter !== "all") picked = picked.filter((r) => (r.canonical_status ?? "missing") === filter)
    const needle = search.trim().toLowerCase()
    if (!needle) return picked
    return picked.filter((r) => r.key.toLowerCase().includes(needle) || (r.parent_text ?? "").toLowerCase().includes(needle) || (r.translation_text ?? "").toLowerCase().includes(needle))
}

/**
 * Sort rows by a column. Status sorts by the canonical status.
 *
 * @param rows Rows to sort.
 * @param key Column to sort by.
 * @param direction Sort direction.
 * @returns The sorted copy.
 */
function sortRows(rows: WH3DriftRow[], key: SortField, direction: "asc" | "desc"): WH3DriftRow[] {
    const dir = direction === "asc" ? 1 : -1
    const val = (r: WH3DriftRow) => (key === "status" ? (r.canonical_status ?? "") : String(r[key] ?? ""))
    return [...rows].sort((a, b) => val(a).localeCompare(val(b)) * dir)
}

/**
 * Per-mod WH3 translation review page. Renders the shared `<TranslationPage>` shell so it mirrors Chrono Ark 1-to-1.
 *
 * @returns The page.
 */
const TranslationDetailsPage: React.FC = () => {
    const { workshopId = "" } = useParams<{ workshopId: string }>()
    const navigate = useNavigate()
    const slug = useGameSlug()

    const [mod, setMod] = useState<WH3TranslationModSummary | null>(null)
    const [progress, setProgress] = useState<WH3RescanSummary | null>(null)
    const [strings, setStrings] = useState<WH3DriftRow[]>([])
    const [loading, setLoading] = useState(true)
    const [openModal, setOpenModal] = useState<ModalKey>(null)
    const [showContext, setShowContext] = useState(false)
    const [showSuggestions, setShowSuggestions] = useState(false)

    // Keep the Mod Glossary count current after suggestions are accepted.
    const refreshGlossaryCount = useCallback(() => {
        loadGlossary(workshopId)
            .then((d) => setGlossaryCount(Object.keys(d).length))
            .catch(() => {})
    }, [workshopId])
    const { confirm, confirmDialog } = useConfirm()
    // Translate Names runs one stage at a time. namesRunRef tracks the stage as a ref, so advancing it does not re-render the page.
    // stageReview is the finished stage's review, and pausedStep is a finished stage whose review was closed.
    const [pendingScope, setPendingScope] = useState<"all" | "names" | "changed">("all")
    const namesRunRef = useRef<NamesRun | null>(null)
    const run = useTranslationRun<WH3TranslationPreview>({
        gameId: "total_war_warhammer_3",
        modId: workshopId,
        // Show each completed batch's translations in the table while the run continues.
        onBatchTranslated: (translations, provider) =>
            setStrings((prev) =>
                prev.map((r) => (translations[r.key] !== undefined ? { ...r, translation_text: translations[r.key], provider, status: "translated", canonical_status: "pending" } : r))
            ),
        // When the run finishes, refresh counts and rows and show a result banner. A names run reviews each stage's names instead.
        onSettled: (state) => {
            // A names run does not pause for per-batch provider suggestions. Each stage's names are reviewed once the stage finishes.
            if (state.phase === "reviewing") {
                if (namesRunRef.current) continueAfterReview()
            } else if (state.phase === "error") {
                namesRunRef.current = null
            } else if (state.phase === "complete") {
                const total = state.totalTranslated
                const namesRun = namesRunRef.current
                ;(async () => {
                    try {
                        const summary = await rescanMod(workshopId)
                        setProgress(summary)
                        await loadStrings()
                    } catch {
                        /* ignore refresh errors */
                    }
                    if (!namesRun) {
                        setBanner({ type: "success", message: `Translated ${total} strings` })
                        return
                    }
                    namesRun.translated += total
                    let names: TermSuggestion[] = []
                    try {
                        names = await loadNameSuggestions(workshopId, namesRun.stages[namesRun.index].categories)
                    } catch {
                        /* skip this stage's review */
                    }
                    // A stage with nothing new to review moves straight on to the next one.
                    if (names.length > 0) {
                        refreshSuggestions()
                        setStageReview({ step: stageStep(namesRun), suggestions: names })
                    } else {
                        advanceNamesRun()
                    }
                })()
            }
        },
    })
    const { banner, setBanner, start: startTranslation, continueAfterReview } = run
    const { suggestions, refresh: refreshSuggestions, scan, scanning } = run.pending
    const [stageReview, setStageReview] = useState<{ step: StageStep; suggestions: TermSuggestion[] } | null>(null)
    const [pausedStep, setPausedStep] = useState<StageStep | null>(null)
    const [nameReviewSuggestions, setNameReviewSuggestions] = useState<TermSuggestion[] | null>(null)
    const {
        context: modContext,
        loading: contextLoading,
        hasContext,
        save: saveModContextFields,
    } = useModContext(["total_war_warhammer_3", "mod-context", workshopId], { load: () => fetchModContext(workshopId), save: (next) => saveModContext(workshopId, next) }, EMPTY_MOD_CONTEXT)
    const [glossaryCount, setGlossaryCount] = useState<number>(0)
    const { search, viewProps: tableView } = useTableView<WH3DriftRow, SortField, RowStatus>({
        rows: strings,
        storageKey: COLUMN_WIDTH_KEY,
        defaultWidths: DEFAULT_COLUMN_WIDTHS,
        initialSort: { key: "key", direction: null },
        select: selectRows,
        sortRows,
    })
    const loadStrings = useCallback(async () => {
        if (!workshopId) return
        const rows = await fetchStrings(workshopId)
        setStrings(rows)
    }, [workshopId])

    // Reload counts and rows after accepting a glossary suggestion under an edited English renamed existing translations.
    const reloadAfterRename = useCallback(async () => {
        try {
            setProgress(await rescanMod(workshopId))
            await loadStrings()
        } catch {
            /* keep the current table */
        }
    }, [workshopId, loadStrings])

    useEffect(() => {
        let cancelled = false
        ;(async () => {
            try {
                const [allMods, summary] = await Promise.all([listTranslationMods(), rescanMod(workshopId)])
                if (cancelled) return
                setMod(allMods.find((m) => m.workshop_id === workshopId) ?? null)
                setProgress(summary)
                await loadStrings()
            } catch (e) {
                setBanner({ type: "error", message: `Failed to load: ${(e as Error).message}` })
            } finally {
                if (!cancelled) setLoading(false)
            }
        })()
        return () => {
            cancelled = true
        }
    }, [workshopId, loadStrings, setBanner])

    useEffect(() => {
        let cancelled = false
        ;(async () => {
            try {
                const dict = await loadGlossary(workshopId)
                if (!cancelled) setGlossaryCount(Object.keys(dict).length)
            } catch {
                /* leave at 0 */
            }
        })()
        return () => {
            cancelled = true
        }
    }, [workshopId, openModal])

    const onRowSave = useCallback(
        async (key: string, text: string) => {
            try {
                await saveString(workshopId, key, text)
                setStrings((prev) =>
                    prev.map((r) =>
                        r.key === key
                            ? { ...r, translation_text: text, provider: "manual", status: r.status === "untranslated" || r.status === "stale" ? "translated" : r.status, canonical_status: "pending" }
                            : r
                    )
                )
                setBanner({ type: "success", message: `Saved ${key}` })
            } catch (e) {
                setBanner({ type: "error", message: `Save failed: ${(e as Error).message}` })
            }
        },
        [workshopId, setBanner]
    )

    const isTranslating = run.state.phase === "translating"

    // Translate previews the run and opens the confirm modal. Confirming starts the batch loop.
    const handleTranslateClick = (provider = "") => {
        setPendingScope("all")
        run.openPreview(provider, (p) => previewTranslation(workshopId, p))
    }

    // Translate name strings first, then review them into the glossary so the bulk run reuses them.
    const handleTranslateNamesClick = (provider = "") => {
        setPendingScope("names")
        run.openPreview(provider, (p) => previewTranslation(workshopId, p, "names"), { empty: "All names are already translated.", failure: "Names preview failed" })
    }

    // Update Changed revises the previous translations of changed rows only.
    const handleUpdateChangedClick = (provider = "") => {
        setPendingScope("changed")
        run.openPreview(provider, (p) => previewTranslation(workshopId, p, "changed"), { empty: "No changed strings to update.", failure: "Update preview failed" })
    }

    const onAcceptChanged = useCallback(async () => {
        const ok = await confirm({
            title: "Accept All Changed",
            message: "Accept the current source text for all changed strings? Their translations stay as they are.",
            confirmLabel: "Accept",
        })
        if (!ok) return
        try {
            const n = await acceptChanged(workshopId)
            setBanner({ type: "success", message: `Accepted ${n} changed string${n === 1 ? "" : "s"}.` })
            await reloadAfterRename()
        } catch (e) {
            setBanner({ type: "error", message: `Accept failed: ${(e as Error).message}` })
        }
    }, [workshopId, reloadAfterRename, confirm, setBanner])

    const onConfirmTranslate = () =>
        run.confirmPreview((data, provider) => {
            const stages = pendingScope === "names" ? data.stages : undefined
            setPausedStep(null)
            if (stages?.length) {
                namesRunRef.current = { stages, index: 0, provider, translated: 0 }
                startTranslation(provider, stages[0].batch_plan)
            } else {
                namesRunRef.current = null
                startTranslation(provider, data.batch_plan ?? [], pendingScope === "changed" ? "update" : "translate")
            }
        })

    /**
     * End the names run and report how many names it translated.
     *
     * @param stoppedBefore The stage the user stopped before, or undefined when every stage ran.
     */
    const finishNamesRun = useCallback(
        (stoppedBefore?: string) => {
            const translated = namesRunRef.current?.translated ?? 0
            namesRunRef.current = null
            const names = `${translated} name${translated === 1 ? "" : "s"}`
            setBanner({ type: "success", message: stoppedBefore ? `Translated ${names}. Stopped before ${stoppedBefore}.` : `Translated ${names}.` })
        },
        [setBanner]
    )

    // Start the names run's next stage, or finish the run after the last one.
    const advanceNamesRun = useCallback(() => {
        const namesRun = namesRunRef.current
        if (!namesRun) return
        if (namesRun.index + 1 >= namesRun.stages.length) {
            finishNamesRun()
            return
        }
        namesRun.index += 1
        startTranslation(namesRun.provider, namesRun.stages[namesRun.index].batch_plan)
    }, [startTranslation, finishNamesRun])

    // Stop a translation run. A names run is dropped too, so its stages do not continue.
    const onCancelTranslate = () => {
        namesRunRef.current = null
        run.cancel()
    }

    // Suggest glossary terms from already-translated names without translating anything.
    const onSuggestFromNames = useCallback(async () => {
        try {
            const names = await loadNameSuggestions(workshopId)
            if (names.length === 0) {
                setBanner({ type: "success", message: "No new name terms found." })
                return
            }
            refreshSuggestions()
            setNameReviewSuggestions(names)
        } catch (e) {
            setBanner({ type: "error", message: `Name suggestions failed: ${(e as Error).message}` })
        }
    }, [workshopId, refreshSuggestions, setBanner])

    const onSyncChanges = useCallback(async () => {
        try {
            const result = await syncChanges(workshopId)
            const fileCount = Object.keys(result.per_file).length
            const keyCount = Object.values(result.per_file).reduce((a, b) => a + b, 0)
            const summary = await rescanMod(workshopId)
            setProgress(summary)
            await loadStrings()
            const orphanNote = result.removed_orphans > 0 ? `, removed ${result.removed_orphans} orphan${result.removed_orphans !== 1 ? "s" : ""}` : ""
            const packNote = result.pack_built ? ", rebuilt pack" : result.pack_error ? ` (pack rebuild failed: ${result.pack_error})` : ""
            setBanner({ type: "success", message: `Synced ${keyCount} keys across ${fileCount} files${orphanNote}${packNote}` })
        } catch (e) {
            setBanner({ type: "error", message: `Sync failed: ${(e as Error).message}` })
        }
    }, [workshopId, loadStrings, setBanner])

    const onClearEnglish = useCallback(async () => {
        const ok = await confirm({ title: "Clear English", message: "Clear all translation text? An auto-snapshot is taken before clearing.", confirmLabel: "Clear", variant: "danger" })
        if (!ok) return
        try {
            const result = await clearTranslations(workshopId)
            const summary = await rescanMod(workshopId)
            setProgress(summary)
            await loadStrings()
            setBanner({ type: "success", message: `Cleared ${result.cleared} translations` })
        } catch (e) {
            setBanner({ type: "error", message: `Clear failed: ${(e as Error).message}` })
        }
    }, [workshopId, loadStrings, confirm, setBanner])

    const onRestored = useCallback(async () => {
        const summary = await rescanMod(workshopId)
        setProgress(summary)
        await loadStrings()
        // Snapshots include the glossary and the dialog stays open after a restore, so refresh the count now.
        refreshGlossaryCount()
        setBanner({ type: "success", message: "Restored from snapshot" })
    }, [workshopId, loadStrings, refreshGlossaryCount, setBanner])

    const languages = useLanguageOverrides(
        { source: modContext.source_language_override, target: modContext.target_language_override },
        { source: mod?.source_language ?? "Chinese", target: mod?.target_language ?? "English" },
        (next) => saveModContextFields({ source_language_override: next.source, target_language_override: next.target }),
        (message) => setBanner({ type: "error", message })
    )

    // Save the translated-names prompt setting as soon as it is toggled, and put it back if the save fails.
    const onIncludeNamesChange = useCallback(
        async (checked: boolean) => {
            try {
                await saveModContextFields({ include_translated_names: checked })
            } catch (e) {
                setBanner({ type: "error", message: `Could not save the setting: ${(e as Error).message}` })
            }
        },
        [saveModContextFields, setBanner]
    )

    const onOpenFolder = useCallback(async () => {
        try {
            await openModFolder(workshopId)
        } catch (e) {
            setBanner({ type: "error", message: `Open folder failed: ${(e as Error).message}` })
        }
    }, [workshopId, setBanner])

    const translateCount = useMemo(() => progress?.counts.untranslated ?? 0, [progress])
    const changedCount = useMemo(() => progress?.canonical_counts.changed ?? 0, [progress])
    // Counted from the table rows so each translated batch shows up right away. Done = synced + pending + untouched, total adds missing.
    const done = useMemo(() => strings.filter((r) => r.canonical_status === "synced" || r.canonical_status === "pending" || r.canonical_status === "untouched").length, [strings])
    const total = useMemo(() => done + strings.filter((r) => r.canonical_status === "missing" || r.canonical_status === "changed").length, [strings, done])

    const columns = translationColumns<WH3DriftRow>(
        {
            status: { field: "status", render: (r) => <StatusBadge status={r.canonical_status ?? "missing"} /> },
            mode: { field: "provider", render: (r) => <span title={r.provider ?? ""}>{r.provider ?? ""}</span> },
            source: {
                field: "source_filename",
                render: (r) => (
                    <a
                        href="#"
                        title={r.source_filename}
                        onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            openSourceFile(workshopId, r.source_filename).catch(() => {})
                        }}
                    >
                        <HighlightText text={r.source_filename} query={search} />
                    </a>
                ),
            },
            key: { field: "key", render: (r) => <HighlightText text={r.key} query={search} /> },
            original: { field: "parent_text", render: (r) => (r.parent_text != null ? <HighlightText text={r.parent_text} query={search} /> : <em style={{ color: "var(--text-dim)" }}>orphan</em>) },
            translation: {
                field: "translation_text",
                render: (r) => (
                    <TranslationCell
                        value={r.translation_text ?? ""}
                        previous={r.previous_text}
                        synced={r.canonical_status === "synced"}
                        placeholder="(untranslated)"
                        highlight={search}
                        onSave={(text) => onRowSave(r.key, text)}
                    />
                ),
            },
        },
        { original: `Original (${languages.source})`, translation: languages.target }
    )

    if (loading || contextLoading) return <LoadingState message="Loading mod details..." />

    const titleBadges = (
        <>
            <SteamLink href={`https://steamcommunity.com/sharedfiles/filedetails/?id=${workshopId}`} />
            <OpenFolderButton onClick={onOpenFolder} />
            {progress?.has_unsynced_changes && <PendingSyncPill />}
        </>
    )

    const languageControls = <LanguageControls {...languages.controls} />

    const syncState = progress?.has_unsynced_changes ? "sync" : (progress?.canonical_counts.synced ?? 0) > 0 ? "resync" : "disabled"

    const toolbar = (
        <TranslationToolbar
            glossary={{ count: glossaryCount, onClick: () => setOpenModal("glossary") }}
            suggestions={{ count: suggestions.length, onClick: () => setShowSuggestions(true) }}
            scan={{ scanning, onClick: scan }}
            apiResponses={{ onClick: () => setOpenModal("responses") }}
            context={{ label: "Mod Context", hasContext, onClick: () => setShowContext((v) => !v) }}
            history={{ onClick: () => setOpenModal("history") }}
            reset={{ onClick: () => setOpenModal("reset") }}
            clearEnglish={{ onClick: onClearEnglish }}
            extraActions={
                <>
                    <SplitButton
                        variant="outline"
                        label={`Update Changed (${changedCount})`}
                        onClick={() => handleUpdateChangedClick()}
                        disabled={isTranslating || changedCount === 0}
                        menuDisabled={isTranslating || changedCount === 0}
                        menuLabel="Update Changed menu"
                        items={[{ label: "Accept All Changed", onSelect: onAcceptChanged }]}
                    />
                    <SplitButton
                        variant="outline"
                        label="Translate Names"
                        onClick={() => handleTranslateNamesClick()}
                        disabled={isTranslating || translateCount === 0}
                        menuDisabled={isTranslating}
                        menuLabel="Translate Names menu"
                        items={[{ label: "Suggest from Translated Names", onSelect: onSuggestFromNames }]}
                    />
                </>
            }
            translate={
                <SplitButton
                    label={`Translate${run.provider ? ` (${providerLabel(run.provider)})` : ""}`}
                    onClick={() => handleTranslateClick()}
                    disabled={isTranslating || translateCount === 0}
                    menuDisabled={isTranslating}
                    menuLabel="Translate provider menu"
                    items={WEB_PROVIDERS.map((p) => ({ label: providerLabel(p), onSelect: () => run.setProvider(p) }))}
                />
            }
            sync={<SyncButton state={syncState} confirmMessage={wh3SyncMessage} onSync={onSyncChanges} />}
        />
    )

    const modals = (
        <>
            {showSuggestions && (
                <GlossarySuggestionModal
                    gameId="total_war_warhammer_3"
                    onTranslationsChanged={reloadAfterRename}
                    modId={workshopId}
                    suggestions={suggestions}
                    onClose={() => setShowSuggestions(false)}
                    onUpdated={() => {
                        refreshSuggestions()
                        refreshGlossaryCount()
                    }}
                />
            )}
            {openModal === "glossary" && (
                <ModGlossaryModal workshopId={workshopId} onClose={() => setOpenModal(null)} onSuggestionsChanged={() => refreshSuggestions()} onTranslationsChanged={reloadAfterRename} />
            )}
            {openModal === "responses" && <ApiResponsesModal workshopId={workshopId} onClose={() => setOpenModal(null)} />}
            {(openModal === "history" || openModal === "reset") && (
                <HistoryModal workshopId={workshopId} onClose={() => setOpenModal(null)} defaultRestoreMode={openModal === "reset"} onRestored={onRestored} />
            )}
            {run.preview && (
                <TranslationConfirmModal
                    preview={run.preview.data}
                    title={pendingScope === "names" ? "Translate Names" : pendingScope === "changed" ? "Update Changed" : undefined}
                    onConfirm={onConfirmTranslate}
                    onCancel={run.closePreview}
                />
            )}

            {/* Review of the names stage that just finished. Continue starts the next stage, and closing pauses the run. */}
            {stageReview && (
                <GlossarySuggestionModal
                    key={stageReview.step.index}
                    gameId="total_war_warhammer_3"
                    onTranslationsChanged={reloadAfterRename}
                    modId={workshopId}
                    suggestions={stageReview.suggestions}
                    subtitle={`Stage ${stageReview.step.index + 1} of ${stageReview.step.total}: ${stageReview.step.label}`}
                    continueLabel={stageReview.step.nextLabel ? `Continue to ${stageReview.step.nextLabel}` : "Finish"}
                    onClose={() => {
                        const step = stageReview.step
                        setStageReview(null)
                        if (step.nextLabel) setPausedStep(step)
                        else finishNamesRun()
                    }}
                    onUpdated={() => {
                        refreshSuggestions()
                        refreshGlossaryCount()
                    }}
                    onContinue={() => {
                        setStageReview(null)
                        advanceNamesRun()
                    }}
                />
            )}

            {/* Suggest from Translated Names. */}
            {nameReviewSuggestions && (
                <GlossarySuggestionModal
                    gameId="total_war_warhammer_3"
                    onTranslationsChanged={reloadAfterRename}
                    modId={workshopId}
                    suggestions={nameReviewSuggestions}
                    onClose={() => setNameReviewSuggestions(null)}
                    onUpdated={() => {
                        refreshSuggestions()
                        refreshGlossaryCount()
                    }}
                />
            )}

            {/* Glossary suggestion review between batches. Closing pauses, and the paused banner resumes. */}
            {run.review && !namesRunRef.current && (
                <GlossarySuggestionModal
                    gameId="total_war_warhammer_3"
                    onTranslationsChanged={reloadAfterRename}
                    modId={workshopId}
                    {...run.review}
                    onUpdated={() => {
                        refreshSuggestions()
                        refreshGlossaryCount()
                    }}
                />
            )}
            {confirmDialog}
        </>
    )

    return (
        <TranslationPage<WH3DriftRow>
            title={mod?.display_name ?? workshopId}
            progressLabel={`${done} / ${total} total strings translated`}
            onBack={() => navigate(`/${slug}/dashboard`)}
            previewImage={mod?.preview_image_url ? `${API_BASE}${mod.preview_image_url}` : null}
            titleBadges={titleBadges}
            languageControls={languageControls}
            toolbar={toolbar}
            statusFilters={STATUS_FILTERS}
            {...tableView}
            columns={columns}
            getRowKey={(r) => `${r.source_filename}::${r.key}`}
            getRowStyle={(r) => canonicalRowStyle(r.canonical_status ?? "missing", { override: r.canonical_status === "pending" })}
            translating={run.translating}
            onCancelTranslate={onCancelTranslate}
            extraBanners={
                <>
                    {run.pausedBanner && !namesRunRef.current && <BatchReviewBanner {...run.pausedBanner} />}
                    {pausedStep && (
                        <div className="glass-card static batch-review-banner">
                            <span>Names paused after {pausedStep.label}.</span>
                            <div className="batch-review-banner-actions">
                                <button
                                    type="button"
                                    className="btn btn-primary"
                                    onClick={() => {
                                        setPausedStep(null)
                                        advanceNamesRun()
                                    }}
                                >
                                    Continue to {pausedStep.nextLabel}
                                </button>
                                <button
                                    type="button"
                                    className="btn btn-outline"
                                    onClick={() => {
                                        setPausedStep(null)
                                        finishNamesRun(pausedStep.nextLabel ?? undefined)
                                    }}
                                >
                                    Stop
                                </button>
                            </div>
                        </div>
                    )}
                </>
            }
            banner={banner}
            onDismissBanner={() => setBanner(null)}
            panels={
                showContext && (
                    <ContextPanel
                        title="Mod Context"
                        description="This context is included in the translation prompt to help the AI understand the mod's setting and lore."
                        value={modContext}
                        onSave={(fields) => saveModContextFields(fields)}
                        extra={
                            <label
                                className="checkbox-row"
                                title="Names you translated but have not accepted into the Mod Glossary are sent as glossary terms. Glossary terms win when both have the same name."
                            >
                                <input type="checkbox" checked={!!modContext.include_translated_names} onChange={(e) => onIncludeNamesChange(e.target.checked)} />
                                Also send translated names that aren't in the glossary
                            </label>
                        }
                        placeholders={{
                            source_game: "e.g. Total War: Warhammer III",
                            character_name: "e.g. Grand Cathay",
                            background: "Describe the factions, units and lore this mod adds, and any naming conventions the translation should follow...",
                        }}
                    />
                )
            }
            modals={modals}
        />
    )
}

export default TranslationDetailsPage
