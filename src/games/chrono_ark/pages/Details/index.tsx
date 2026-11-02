import React, { useState, useEffect, useCallback, useRef } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useGameSlug } from "@/hooks/useGameSlug"
import type { GlossaryTerm, LocString } from "@/lib/types"
import { getRowStatus, filterStrings, sortStrings } from "@/lib/search"
import type { SortField, SortDirection } from "@/lib/search"
import { API_BASE, gameApi } from "@/lib/api"
import GlossarySuggestionModal from "@/components/GlossarySuggestionModal"
import TranslationConfirmModal from "@/components/TranslationConfirmModal"
import ApiResponsesModal from "@/games/chrono_ark/components/ApiResponsesModal"
import BackupHistoryModal from "@/games/chrono_ark/components/BackupHistoryModal"
import ChronoArkGlossaryModal from "@/games/chrono_ark/components/ChronoArkGlossaryModal"
import ManualTranslateModal from "@/games/chrono_ark/components/ManualTranslateModal"
import ConfirmModal from "@/components/ui/ConfirmModal"
import { TranslationPage } from "@/components/TranslationPage"
import ErrorState from "@/components/ui/ErrorState"
import LoadingState from "@/components/ui/LoadingState"
import { BatchReviewBanner } from "@/components/TranslationPage/BatchReviewBanner"
import { ContextPanel, type ContextFields } from "@/components/TranslationPage/ContextPanel"
import { SyncButton } from "@/components/TranslationPage/SyncButton"
import { TranslationToolbar } from "@/components/TranslationPage/TranslationToolbar"
import { usePendingSuggestions } from "@/hooks/usePendingSuggestions"
import SplitButton from "@/components/ui/SplitButton"
import { LanguageControls } from "@/components/TranslationPage/LanguageControls"
import { OpenFolderButton, PendingSyncPill, SteamLink } from "@/components/TranslationPage/TitleAdornments"
import { StatusBadge } from "@/components/TranslationPage/StatusBadge"
import { TranslationCell } from "@/components/TranslationPage/TranslationCell"
import { canonicalRowStyle, translationColumns } from "@/components/TranslationPage/helpers"
import HighlightText from "@/components/ui/HighlightText"
import { useIterativeTranslation } from "@/hooks/useIterativeTranslation"
import type { BatchDescriptor } from "@/hooks/useIterativeTranslation"

/**
 * Detail view for a specific mod, showing all translatable strings.
 *
 * @returns The mod detail view.
 */
const ModDetail: React.FC = () => {
    const { modId } = useParams<{ modId: string }>()
    const navigate = useNavigate()
    const slug = useGameSlug()
    const onBack = useCallback(() => navigate(`/${slug}/dashboard`), [navigate, slug])
    const [strings, setStrings] = useState<LocString[]>([])
    const [modName, setModName] = useState<string>("")
    const [modAuthor, setModAuthor] = useState<string>("")
    const [modPreviewImage, setModPreviewImage] = useState<string | null>(null)
    const [modUrl, setModUrl] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<string | null>(null)
    // Only the first load may replace the page with an error. A failed refresh keeps the page the user is looking at.
    const hasLoadedRef = useRef(false)

    const [filter, setFilter] = useState<"all" | "missing" | "untouched" | "pending" | "synced">("all")
    const [search, setSearch] = useState("")

    const [sortConfig, setSortConfig] = useState<{ key: SortField; direction: SortDirection }>({
        key: "key",
        direction: "asc",
    })

    const [columnWidths, setColumnWidths] = useState<{ [key: string]: number }>({
        is_translated: 120,
        translated_by: 100,
        key: 200,
        source_file: 100,
        source: 400,
        english: 500,
    })

    const [hasExportChanges, setHasExportChanges] = useState(false)
    const [hasPreviousSync, setHasPreviousSync] = useState(false)

    const [showSuggestionModal, setShowSuggestionModal] = useState(false)
    const [showReviewModal, setShowReviewModal] = useState(false)
    const [modGlossary, setModGlossary] = useState<Record<string, GlossaryTerm>>({})

    const [translationPreview, setTranslationPreview] = useState<any>(null)
    const [pendingRetranslate, setPendingRetranslate] = useState(false)
    const [pendingProvider, setPendingProvider] = useState<string>("")
    const [activeProvider, setActiveProvider] = useState<string>("")
    const [showGlossary, setShowGlossary] = useState(false)
    const [manualQueue, setManualQueue] = useState<LocString[] | null>(null)
    const [translateBanner, setTranslateBanner] = useState<{ type: "success" | "error"; message: string } | null>(null)
    const { suggestions, refresh: fetchSuggestions, scan, scanning } = usePendingSuggestions("chrono_ark", modId ?? "", setTranslateBanner)

    const [showCharacterContext, setShowCharacterContext] = useState(false)
    const [characterContext, setCharacterContext] = useState<ContextFields>({ source_game: "", character_name: "", background: "" })
    const hasCharacterContext = !!(characterContext.source_game || characterContext.character_name || characterContext.background)

    // Load the character context once per mod so the toolbar dot shows before the panel opens.
    useEffect(() => {
        if (!modId) return
        gameApi("chrono_ark")
            .get(`/mods/${modId}/character-context`)
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
                if (data) setCharacterContext({ source_game: data.source_game ?? "", character_name: data.character_name ?? "", background: data.background ?? "" })
            })
            .catch(() => {})
    }, [modId])

    /**
     * Persist the character context and adopt it as the saved value.
     *
     * @param next - Edited fields.
     */
    const saveCharacterContext = async (next: ContextFields) => {
        const res = await gameApi("chrono_ark").post(`/mods/${modId}/character-context`, next)
        if (!res.ok) throw new Error("Failed to save character context.")
        setCharacterContext(next)
    }

    const [sourceLangOverride, setSourceLangOverride] = useState<string | null>(null)
    const [targetLangOverride, setTargetLangOverride] = useState<string | null>(null)

    const [showApiResponses, setShowApiResponses] = useState(false)
    const [showHistory, setShowHistory] = useState(false)
    const [historyRefreshKey, setHistoryRefreshKey] = useState(0)
    const [confirmModal, setConfirmModal] = useState<{
        type: "reset" | "clear-translations" | "delete-all-glossary" | "restore-backup" | "delete-backup"
        message: string | React.ReactNode
        entryId?: string
        entryDate?: string
    } | null>(null)

    /** Merge each finished batch's translations into the table. */
    const handleBatchTranslated = useCallback((translations: Record<string, string>) => {
        setStrings((prev) =>
            prev.map((s) => {
                if (s.key in translations) {
                    return { ...s, english: translations[s.key], is_translated: true }
                }
                return s
            })
        )
        fetchExportStatus()
    }, [])

    const { state: batchState, startTranslation, continueAfterReview, cancel: cancelTranslation } = useIterativeTranslation("chrono_ark", modId ?? "", handleBatchTranslated)

    useEffect(() => {
        if (batchState.phase === "reviewing") {
            setShowReviewModal(true)
        } else if (batchState.phase === "complete") {
            setShowReviewModal(false)
            setTranslateBanner({ type: "success", message: `Translated ${batchState.totalTranslated} strings.` })
            fetchSuggestions()
            fetchExportStatus()
            fetchModDetail(true)
        } else if (batchState.phase === "error") {
            setShowReviewModal(false)
            const partial = batchState.completedBatches > 0 ? ` ${batchState.completedBatches} batch(es) completed before the error.` : ""
            setTranslateBanner({ type: "error", message: `${batchState.message}${partial}` })
            fetchSuggestions()
            fetchModDetail(true)
        }
    }, [batchState.phase]) // eslint-disable-line react-hooks/exhaustive-deps

    /**
     * Fetch a translation preview, which opens the confirm modal. Confirming starts the batch loop in `useIterativeTranslation`.
     *
     * @param provider - AI provider id.
     * @param retranslate - Include already translated rows.
     */
    const handleTranslateClick = async (provider: string, retranslate = false) => {
        if (!modId) return
        setTranslateBanner(null)
        // Manual mode has no backend run. It steps through the rows in a dialog instead.
        if ((provider || activeProvider) === "manual") {
            const queue = strings.filter((s) => (retranslate ? s.source.trim() && !s.untranslatable_reason : getRowStatus(s) === "missing"))
            if (queue.length === 0) setTranslateBanner({ type: "success", message: "All strings are already translated." })
            else setManualQueue(queue)
            return
        }
        try {
            const res = await gameApi("chrono_ark").post("/translate/preview", { mod_id: modId, provider, retranslate })
            const data = await res.json()
            if (!res.ok) {
                setTranslateBanner({ type: "error", message: data.detail || "Failed to fetch translation preview." })
                return
            }
            if (data.total_strings === 0) {
                setTranslateBanner({ type: "success", message: "All strings are already translated." })
                return
            }
            setPendingProvider(provider)
            setPendingRetranslate(retranslate)
            setTranslationPreview(data)
        } catch (err) {
            console.error("Failed to fetch translation preview:", err)
            setTranslateBanner({ type: "error", message: "Failed to reach the server for translation preview." })
        }
    }

    /** Check whether there are unsynced changes to export. */
    const fetchExportStatus = async () => {
        if (!modId) return
        try {
            const res = await gameApi("chrono_ark").get(`/mods/${modId}/export-status`)
            if (res.ok) {
                const data = await res.json()
                setHasExportChanges(data.has_changes)
                setHasPreviousSync(data.has_previous_sync ?? false)
            }
        } catch {}
    }

    /** Load the mod glossary terms. */
    const fetchModGlossary = async () => {
        if (!modId) return
        try {
            const res = await gameApi("chrono_ark").get(`/mods/${modId}/glossary`)
            if (res.ok) {
                const data = await res.json()
                setModGlossary(data.terms || {})
            }
        } catch {}
    }

    /**
     * Load the mod's strings and metadata.
     *
     * @param silent - Skip the loading state and error page (background refresh).
     */
    const fetchModDetail = async (silent = false) => {
        if (!modId) return
        if (!silent) setLoading(true)
        try {
            const res = await gameApi("chrono_ark").get(`/mods/${modId}`)
            if (!res.ok) {
                if (!silent && !hasLoadedRef.current) setLoadError(res.status === 404 ? "not-found" : `The server returned HTTP ${res.status}.`)
                return
            }
            setLoadError(null)
            hasLoadedRef.current = true
            const data = await res.json()
            setStrings(data.strings)
            setModName(data.name ?? "")
            setModAuthor(data.author ?? "")
            setModPreviewImage(data.preview_image ?? null)
            setModUrl(data.url ?? null)
            setSourceLangOverride(data.source_language_override ?? null)
            setTargetLangOverride(data.target_language_override ?? null)
        } catch (err) {
            console.error("Failed to fetch mod detail:", err)
            if (!silent && !hasLoadedRef.current) setLoadError("Could not reach the server.")
        } finally {
            setLoading(false)
        }
    }

    const saveSourceLanguage = async (lang: string | null) => {
        setSourceLangOverride(lang)
        // A non-English source can't have a target override, so clear it.
        if (lang !== "English" && targetLangOverride) {
            setTargetLangOverride(null)
            gameApi("chrono_ark")
                .post(`/mods/${modId}/target-language`, { target_language: null })
                .catch(() => {})
        }
        try {
            await gameApi("chrono_ark").post(`/mods/${modId}/source-language`, { source_language: lang })
            fetchModDetail(true)
        } catch (err) {
            console.error("Failed to save source language:", err)
        }
    }

    const saveTargetLanguage = async (lang: string | null) => {
        setTargetLangOverride(lang)
        try {
            await gameApi("chrono_ark").post(`/mods/${modId}/target-language`, { target_language: lang })
            fetchModDetail(true)
        } catch (err) {
            console.error("Failed to save target language:", err)
        }
    }

    useEffect(() => {
        fetchModDetail()
        fetchExportStatus()
        fetchModGlossary()
        fetch(`${API_BASE}/settings`)
            .then((r) => r.json())
            .then((data) => setActiveProvider(data.provider))
            .catch(() => {})
    }, [modId])

    /**
     * Cycle a column's sort asc -> desc -> none.
     *
     * @param field - Column to sort by.
     */
    const handleSort = (field: SortField) => {
        let direction: SortDirection = "asc"
        if (sortConfig.key === field && sortConfig.direction === "asc") {
            direction = "desc"
        } else if (sortConfig.key === field && sortConfig.direction === "desc") {
            direction = null
        }
        setSortConfig({ key: field, direction })
    }

    /**
     * Save a manual translation and update the table locally.
     *
     * @param key - Localization key.
     * @param newValue - New translation text.
     * @returns Whether the save succeeded.
     */
    const handleSaveString = async (key: string, newValue: string): Promise<boolean> => {
        if (!modId) return false
        try {
            const res = await gameApi("chrono_ark").post(`/mods/${modId}/strings`, { key, english: newValue })
            if (res.ok) {
                // A blank source counts as translated since there is nothing to translate.
                setStrings((prev) =>
                    prev.map((s) =>
                        s.key === key
                            ? { ...s, english: newValue, is_translated: !!newValue || !s.source.trim(), is_synced: s.synced_english !== "" && newValue === s.synced_english, translated_by: "manual" }
                            : s
                    )
                )
                fetchExportStatus()
                return true
            }
        } catch (err) {
            console.error("Failed to save manual translation:", err)
        }
        return false
    }

    /** Visible rows after the status filter, search and sort. */
    const processedStrings = React.useMemo(() => {
        return sortStrings(filterStrings(strings, filter, search), sortConfig)
    }, [strings, filter, search, sortConfig])

    /**
     * Write saved translations back to the mod's files on disk.
     *
     * @param resync - Restore the original files first and re-apply every translation.
     */
    const handleExport = async (resync: boolean) => {
        if (!modId) return
        try {
            const path = resync ? `/mods/${modId}/export?resync=true` : `/mods/${modId}/export`
            const res = await gameApi("chrono_ark").post(path)
            if (res.ok) {
                const data = await res.json()
                const parts: string[] = []
                if (data.files_written?.length) {
                    parts.push(`${data.files_written.length} CSV file(s): ${data.files_written.join(", ")}`)
                }
                if (data.gdata_files_written?.length) {
                    parts.push(`${data.gdata_files_written.length} gdata JSON file(s): ${data.gdata_files_written.join(", ")}`)
                }
                if (data.keyed_overrides_written > 0) {
                    parts.push(`${data.keyed_overrides_written} keyed override(s)`)
                }
                if (data.text_overrides_written > 0) {
                    parts.push(`${data.text_overrides_written} DLL text override(s)`)
                }
                const hasInjector = data.keyed_overrides_written > 0 || data.text_overrides_written > 0
                const target = hasInjector ? " to ModTranslationInjector" : ""
                setTranslateBanner({ type: "success", message: `Synced ${data.applied} translation(s): ${parts.join(", ")}${target}` })
                fetchExportStatus()
                fetchModDetail()
            } else {
                const error = await res.json()
                setTranslateBanner({ type: "error", message: `Export failed: ${error.detail || "Unknown error"}` })
            }
        } catch (err) {
            console.error("Failed to export translations:", err)
            setTranslateBanner({ type: "error", message: "Failed to export translations. Check console for details." })
        }
    }

    /** Ask to confirm resetting the mod, which clears translations and restores the original CSV files. */
    const handleResetConfirm = () => {
        setConfirmModal({
            type: "reset",
            message: (
                <>
                    Are you sure you want to reset this mod? This will:
                    <ul style={{ margin: "0.75rem 0", paddingLeft: "1.25rem" }}>
                        <li>Delete all translation progress and extracted strings</li>
                        <li>Restore the original CSV and gdata JSON files (if previously synced)</li>
                    </ul>
                    Character context and glossary will be preserved.
                    <br />A backup will be created first.
                </>
            ),
        })
    }

    const handleReset = async () => {
        if (!modId) return
        try {
            const res = await gameApi("chrono_ark").post(`/mods/${modId}/reset`)
            if (res.ok) {
                const data = await res.json()
                const csvMsg = data.csv_restored ? " Original CSV files restored." : ""
                const gdataMsg = data.gdata_restored ? " Original gdata JSON files restored." : ""
                const overridesMsg = data.overrides_cleared ? " Translation overrides removed." : ""
                fetchModDetail()
                fetchExportStatus()
                fetchSuggestions()
                fetchModGlossary()
                setTranslateBanner({ type: "success", message: `Reset complete.${csvMsg}${gdataMsg}${overridesMsg}` })
            } else {
                const error = await res.json()
                setTranslateBanner({ type: "error", message: `Failed to reset: ${error.detail || "Unknown error"}` })
            }
        } catch (err) {
            console.error("Failed to reset:", err)
            setTranslateBanner({ type: "error", message: "Failed to reset. Check console for details." })
        }
    }

    /** Wipe only the English column so every row can be re-sent, keeping source strings and metadata. */
    const handleClearTranslationsConfirm = () => {
        setConfirmModal({
            type: "clear-translations",
            message: "Are you sure you want to clear all English translations? This will allow all rows to be sent to the AI provider.",
        })
    }

    const handleClearTranslations = async () => {
        if (!modId) return
        try {
            const res = await gameApi("chrono_ark").post(`/mods/${modId}/clear-translations`)
            if (res.ok) {
                setStrings((prev) => prev.map((s) => ({ ...s, english: "", is_translated: false, is_synced: false })))
                fetchExportStatus()
            } else {
                const error = await res.json()
                setTranslateBanner({ type: "error", message: `Failed to clear translations: ${error.detail || "Unknown error"}` })
            }
        } catch (err) {
            console.error("Failed to clear translations:", err)
            setTranslateBanner({ type: "error", message: "Failed to clear translations. Check console for details." })
        }
    }

    /** Open the mod's folder in the system file explorer. */
    const handleOpenFolder = async () => {
        if (!modId) return
        try {
            const res = await gameApi("chrono_ark").post(`/mods/${modId}/open`)
            if (!res.ok) {
                const error = await res.json()
                setTranslateBanner({ type: "error", message: `Failed to open folder: ${error.detail || "Unknown error"}` })
            }
        } catch (err) {
            console.error("Failed to open folder:", err)
        }
    }

    if (loading) return <LoadingState message="Loading mod details..." />

    if (!modId || loadError === "not-found") {
        return (
            <ErrorState
                title="Mod not found"
                message={`No Chrono Ark mod with ID ${modId ?? ""} was found. It may have been unsubscribed or moved.`}
                action={{ label: "Back to Dashboard", onClick: onBack }}
            />
        )
    }

    if (loadError) return <ErrorState title="Could not load this mod" message={loadError} action={{ label: "Back to Dashboard", onClick: onBack }} />

    const columns = translationColumns<LocString>(
        {
            status: { field: "is_translated", render: (s) => <StatusBadge status={getRowStatus(s)} reason={s.untranslatable_reason} /> },
            mode: { field: "translated_by", render: (s) => <span title={s.translated_by}>{s.translated_by || "\u2014"}</span> },
            source: {
                field: "source_file",
                render: (s) => (
                    <a
                        href="#"
                        title={s.source_file}
                        onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            gameApi("chrono_ark").post(`/mods/${modId}/open-source-file/${encodeURIComponent(s.source_file)}`)
                        }}
                    >
                        <HighlightText text={s.source_file} query={search} />
                    </a>
                ),
            },
            key: {
                field: "key",
                render: (s) => (
                    <span title={s.key}>
                        <HighlightText text={s.key} query={search} />
                    </span>
                ),
            },
            original: { field: "source", render: (s) => <HighlightText text={s.source} query={search} /> },
            translation: {
                field: "english",
                render: (s) => (
                    <TranslationCell
                        value={s.english}
                        previous={s.original_english}
                        synced={s.is_synced}
                        untranslatableReason={getRowStatus(s) === "untranslatable" ? s.untranslatable_reason : undefined}
                        placeholder={!s.source ? "" : s.is_translated ? "" : "Pending translation..."}
                        highlight={search}
                        onSave={(val) => handleSaveString(s.key, val)}
                    />
                ),
            },
        },
        { original: `Original (${sourceLangOverride || "Chinese"})`, translation: targetLangOverride || "English" }
    )

    return (
        <TranslationPage<LocString>
            onBack={onBack}
            previewImage={modPreviewImage ? `${API_BASE}${modPreviewImage}` : null}
            title={modName || modId}
            titleBadges={
                <>
                    {modUrl && <SteamLink href={modUrl} />}
                    <OpenFolderButton onClick={handleOpenFolder} />
                    {hasExportChanges && <PendingSyncPill />}
                </>
            }
            subtitle={modAuthor ? `by ${modAuthor}` : undefined}
            languageControls={
                <LanguageControls source={sourceLangOverride || "Chinese"} target={targetLangOverride || "Chinese"} onSourceChange={saveSourceLanguage} onTargetChange={saveTargetLanguage} />
            }
            progressLabel={`${strings.filter((s) => s.source.trim() && !s.untranslatable_reason && s.is_translated).length} / ${strings.filter((s) => s.source.trim() && !s.untranslatable_reason).length} total strings translated`}
            toolbar={
                <TranslationToolbar
                    glossary={{
                        count: Object.keys(modGlossary).length,
                        onClick: () => {
                            setShowGlossary(true)
                            fetchModGlossary()
                        },
                    }}
                    suggestions={{ count: suggestions.length, onClick: () => setShowSuggestionModal(true) }}
                    scan={{ scanning, onClick: scan }}
                    apiResponses={{ onClick: () => setShowApiResponses(true) }}
                    context={{ label: "Character Context", hasContext: hasCharacterContext, onClick: () => setShowCharacterContext(!showCharacterContext) }}
                    history={{ onClick: () => setShowHistory(true) }}
                    reset={{ onClick: handleResetConfirm }}
                    clearEnglish={{ onClick: handleClearTranslationsConfirm }}
                    translate={
                        <SplitButton
                            label={`Translate${activeProvider ? ` (${activeProvider.charAt(0).toUpperCase() + activeProvider.slice(1)})` : ""}`}
                            onClick={() => handleTranslateClick("")}
                            disabled={batchState.phase === "translating" || batchState.phase === "reviewing"}
                            menuLabel="Translate options"
                            items={[{ label: "Re-Translate All", onSelect: () => handleTranslateClick("", true) }]}
                        />
                    }
                    sync={
                        <SyncButton
                            state={hasExportChanges ? "sync" : hasPreviousSync ? "resync" : "disabled"}
                            confirmMessage={(resync) =>
                                `${resync ? "This will restore the original files and re-apply all translations from scratch.\n\n" : ""}This will overwrite the mod's localization files (CSVs and/or gdata JSONs) with your translations. Continue?`
                            }
                            onSync={handleExport}
                        />
                    }
                />
            }
            statusFilters={[
                { value: "all", label: "All" },
                { value: "missing", label: "Missing" },
                { value: "untouched", label: "Untouched" },
                { value: "pending", label: "Pending" },
                { value: "synced", label: "Synced" },
            ]}
            activeFilter={filter}
            onFilterChange={(v) => setFilter(v as typeof filter)}
            search={search}
            onSearchChange={setSearch}
            columns={columns}
            rows={processedStrings}
            getRowKey={(s) => s.key}
            getRowStyle={(s) => canonicalRowStyle(getRowStatus(s), { override: !s.is_synced && s.english !== s.original_english })}
            sortField={sortConfig.direction ? sortConfig.key : null}
            sortDirection={sortConfig.direction}
            onSort={(f) => handleSort(f as SortField)}
            columnWidths={columnWidths}
            onResizeColumn={(field, width) => setColumnWidths((prev) => ({ ...prev, [field]: width }))}
            translating={batchState.phase === "translating" ? { batchIndex: batchState.batchIndex, totalBatches: batchState.totalBatches, streaming: batchState.streamingProgress } : null}
            onCancelTranslate={() => {
                cancelTranslation()
                setTranslateBanner({ type: "success", message: "Translation cancelled." })
            }}
            extraBanners={
                batchState.phase === "reviewing" &&
                !showReviewModal && (
                    <BatchReviewBanner
                        batchIndex={batchState.batchIndex}
                        totalBatches={batchState.totalBatches}
                        onReview={() => setShowReviewModal(true)}
                        onContinue={continueAfterReview}
                        onCancel={() => {
                            cancelTranslation()
                            setTranslateBanner({ type: "success", message: `Translation cancelled. ${batchState.batchIndex} of ${batchState.totalBatches} batches completed.` })
                        }}
                    />
                )
            }
            banner={translateBanner}
            onDismissBanner={() => setTranslateBanner(null)}
            panels={<>{showCharacterContext && <ContextPanel title="Character Context" value={characterContext} onSave={saveCharacterContext} />}</>}
            modals={
                <>
                    {showSuggestionModal && (
                        <GlossarySuggestionModal
                            gameId="chrono_ark"
                            onTranslationsChanged={() => fetchModDetail(true)}
                            modId={modId!}
                            suggestions={suggestions}
                            onClose={() => setShowSuggestionModal(false)}
                            onUpdated={() => {
                                fetchSuggestions()
                                fetchModGlossary()
                            }}
                        />
                    )}

                    {showHistory && modId && (
                        <BackupHistoryModal
                            modId={modId}
                            refreshKey={historyRefreshKey}
                            onClose={() => setShowHistory(false)}
                            onRestore={(entry) =>
                                setConfirmModal({
                                    type: "restore-backup",
                                    message: `Restore to backup from ${new Date(entry.created_at).toLocaleString()}? A backup of the current state will be created first.`,
                                    entryId: entry.id,
                                    entryDate: new Date(entry.created_at).toLocaleString(),
                                })
                            }
                            onDelete={(entry) => setConfirmModal({ type: "delete-backup", message: "Delete this backup?", entryId: entry.id })}
                        />
                    )}

                    {manualQueue && (
                        <ManualTranslateModal
                            queue={manualQueue}
                            allStrings={strings}
                            glossary={modGlossary}
                            sourceLanguage={sourceLangOverride || "Chinese"}
                            targetLanguage={targetLangOverride || "English"}
                            onSave={handleSaveString}
                            onClose={() => setManualQueue(null)}
                        />
                    )}

                    {showApiResponses && modId && <ApiResponsesModal modId={modId} onClose={() => setShowApiResponses(false)} />}

                    {translationPreview && (
                        <TranslationConfirmModal
                            preview={translationPreview}
                            title={pendingRetranslate ? "Confirm Re-Translation" : undefined}
                            onConfirm={() => {
                                const plan: BatchDescriptor[] = translationPreview.batch_plan || []
                                setTranslationPreview(null)
                                setTranslateBanner(null)
                                startTranslation(pendingProvider || activeProvider, plan)
                            }}
                            onCancel={() => setTranslationPreview(null)}
                        />
                    )}

                    {/* Closing this modal pauses the run. The paused banner resumes it. */}
                    {batchState.phase === "reviewing" && showReviewModal && (
                        <GlossarySuggestionModal
                            gameId="chrono_ark"
                            onTranslationsChanged={() => fetchModDetail(true)}
                            modId={modId!}
                            suggestions={batchState.suggestions}
                            onClose={() => setShowReviewModal(false)}
                            onUpdated={() => {
                                fetchSuggestions()
                                fetchModGlossary()
                            }}
                            batchProgress={{ current: batchState.batchIndex + 1, total: batchState.totalBatches }}
                            onContinue={() => {
                                setShowReviewModal(false)
                                continueAfterReview()
                            }}
                        />
                    )}

                    {showGlossary && (
                        <ChronoArkGlossaryModal
                            glossary={modGlossary}
                            modId={modId!}
                            strings={strings}
                            onClose={() => setShowGlossary(false)}
                            onChanged={fetchModGlossary}
                            onApplied={(message) => {
                                setTranslateBanner({ type: "success", message })
                                fetchModDetail(true)
                                fetchExportStatus()
                            }}
                            onTranslationsChanged={() => {
                                fetchModDetail(true)
                                fetchExportStatus()
                            }}
                            onRequestDeleteAll={() => setConfirmModal({ type: "delete-all-glossary", message: `Delete all ${Object.keys(modGlossary).length} glossary term(s)?` })}
                            onSuggestionsChanged={fetchSuggestions}
                        />
                    )}

                    {confirmModal && (
                        <ConfirmModal
                            title={
                                {
                                    reset: "Reset Mod",
                                    "clear-translations": "Clear Translations",
                                    "delete-all-glossary": "Delete All Glossary Terms",
                                    "restore-backup": "Restore Backup",
                                    "delete-backup": "Delete Backup",
                                }[confirmModal.type]
                            }
                            message={confirmModal.message}
                            variant={
                                {
                                    reset: "danger" as const,
                                    "clear-translations": "danger" as const,
                                    "delete-all-glossary": "danger" as const,
                                    "restore-backup": "warning" as const,
                                    "delete-backup": "danger" as const,
                                }[confirmModal.type]
                            }
                            confirmLabel={
                                {
                                    reset: "Reset",
                                    "clear-translations": "Clear",
                                    "delete-all-glossary": "Delete All",
                                    "restore-backup": "Restore",
                                    "delete-backup": "Delete",
                                }[confirmModal.type]
                            }
                            onCancel={() => setConfirmModal(null)}
                            onConfirm={async () => {
                                const type = confirmModal.type
                                const entryId = confirmModal.entryId
                                setConfirmModal(null)
                                switch (type) {
                                    case "reset":
                                        handleReset()
                                        break
                                    case "clear-translations":
                                        handleClearTranslations()
                                        break
                                    case "delete-all-glossary":
                                        await gameApi("chrono_ark").post(`/mods/${modId}/glossary/delete`, { all: true })
                                        fetchModGlossary()
                                        break
                                    case "restore-backup":
                                        try {
                                            const res = await gameApi("chrono_ark").post(`/mods/${modId}/history/${entryId}/restore`)
                                            if (res.ok) {
                                                setShowHistory(false)
                                                setTranslateBanner({ type: "success", message: "Restored from backup successfully." })
                                                fetchModDetail()
                                                fetchExportStatus()
                                                fetchSuggestions()
                                                fetchModGlossary()
                                            }
                                        } catch (err) {
                                            console.error("Failed to restore backup:", err)
                                        }
                                        break
                                    case "delete-backup":
                                        try {
                                            await fetch(gameApi("chrono_ark").url(`/mods/${modId}/history/${entryId}`), { method: "DELETE" })
                                            setHistoryRefreshKey((k) => k + 1)
                                        } catch (err) {
                                            console.error("Failed to delete backup:", err)
                                        }
                                        break
                                }
                            }}
                        />
                    )}
                </>
            }
        />
    )
}

export default ModDetail
