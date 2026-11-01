import React, { useState, useEffect, useCallback, useRef } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useGameSlug } from "../../../useGameSlug"
import type { GlossaryTerm, LocString } from "../../../../shared_types"
import { getRowStatus, filterStrings, sortStrings } from "../../../../utils/stringFilters"
import type { SortField, SortDirection } from "../../../../utils/stringFilters"
import { gameApi } from "../../../../api/games"
import { API_BASE } from "../../../../config"
import GlossarySuggestionModal from "../../../../components/GlossarySuggestionModal"
import TranslationConfirmModal from "../../../../components/TranslationConfirmModal"
import ApiResponsesModal from "../../components/ApiResponsesModal"
import BackupHistoryModal from "../../components/BackupHistoryModal"
import ChronoArkGlossaryModal from "../../components/ChronoArkGlossaryModal"
import ManualTranslateModal from "../../components/ManualTranslateModal"
import ConfirmModal from "../../../../components/ConfirmModal"
import { TranslationPage } from "../../../../translation/TranslationPage"
import ErrorState from "../../../../ui/ErrorState"
import LoadingState from "../../../../ui/LoadingState"
import { BatchReviewBanner } from "../../../../translation/BatchReviewBanner"
import { ContextPanel, type ContextFields } from "../../../../translation/ContextPanel"
import { SyncButton } from "../../../../translation/SyncButton"
import { TranslationToolbar } from "../../../../translation/TranslationToolbar"
import { usePendingSuggestions } from "../../../../translation/usePendingSuggestions"
import SplitButton from "../../../../ui/SplitButton"
import { LanguageControls } from "../../../../translation/LanguageControls"
import { OpenFolderButton, PendingSyncPill, SteamLink } from "../../../../translation/TitleAdornments"
import { StatusBadge } from "../../../../translation/StatusBadge"
import { TranslationCell } from "../../../../translation/TranslationCell"
import { canonicalRowStyle } from "../../../../translation/rowStyle"
import { translationColumns } from "../../../../translation/columns"
import HighlightText from "../../../../ui/HighlightText"
import { useIterativeTranslation } from "../../../../hooks/useIterativeTranslation"
import type { BatchDescriptor } from "../../../../hooks/useIterativeTranslation"

/**
 * Detail view for a specific mod, showing all translatable strings.
 *
 * Reads the active mod id from the URL via React Router's `useParams` and
 * uses `useNavigate` to return to the dashboard.
 *
 * @returns The rendered mod detail view.
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
    // Only the first load may replace the page with an error. A failed refresh after an action keeps the page the user is looking at.
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
     * @param next The edited fields.
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

    /** Callback fired by the iterative translation hook after each batch completes. */
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

    // React to batch translation phase changes.
    useEffect(() => {
        if (batchState.phase === "reviewing") {
            // Auto-open the review modal when a batch finishes with suggestions.
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
     * Initiates the translation workflow by fetching a preview from the backend.
     *
     * The workflow is two-step:
     *   1. This function calls POST `/api/translate/preview` to get batch counts,
     *      prompt previews, and cost estimates without actually translating.
     *   2. If there are strings to translate, the preview data is stored in state
     *      which triggers the TranslationConfirmModal to open.
     *   3. The user reviews and confirms, which starts the iterative batch
     *      translation loop via the `useIterativeTranslation` hook.
     *
     * If all strings are already translated, a success banner is shown instead.
     *
     * @param provider - The AI provider identifier (e.g. "claude").
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
            // POST /api/games/chrono_ark/translate/preview — returns { total_strings, total_batches, batch_size, provider, previews, estimates }
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
            // Store the provider and preview so the confirmation modal can render.
            setPendingProvider(provider)
            setPendingRetranslate(retranslate)
            setTranslationPreview(data)
        } catch (err) {
            console.error("Failed to fetch translation preview:", err)
            setTranslateBanner({ type: "error", message: "Failed to reach the server for translation preview." })
        }
    }

    /**
     * Ref tracking the active column resize operation. Stores which column field
     * is being resized, the pointer's starting X position, and the column's width
     * at the start of the drag. Null when no resize is in progress.
     */

    /**
     * Fetches whether there are pending translation changes that can be exported
     * (synced) to the mod's CSV files.
     * GET `/api/mods/:modId/export-status` -> `{ has_changes: boolean }`.
     */
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

    /**
     * Fetches the mod-specific glossary terms.
     * GET `/api/mods/:modId/glossary` -> `{ terms: Record<string, { category, source_mappings }> }`.
     * Called when the glossary panel is opened.
     */
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
     * Fetches the full mod detail including all localization strings, mod metadata,
     * GET `/api/mods/:modId` -> `{ strings, name, author, preview_image, url }`.
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
        // When switching away from English source, clear target override
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

    // On mount (or when modId changes), fetch all required data in parallel.
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
     * Handles sorting when a column header is clicked.
     * @param field - The field to sort by.
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
     * Saves a manual translation for a specific string key.
     * POST `/api/mods/:modId/strings` -> `{ key, english }`.
     *
     * On success, updates the local `strings` state optimistically so the table
     * reflects the change immediately. A string is marked as translated if it has
     * a non-empty English value OR its source text is blank (nothing to translate).
     *
     * Also re-fetches export status since the new edit may enable the Sync button.
     *
     * @param key - The localization key to update.
     * @param newValue - The new English translation text.
     * @returns Whether the save succeeded.
     */
    const handleSaveString = async (key: string, newValue: string): Promise<boolean> => {
        if (!modId) return false
        try {
            const res = await gameApi("chrono_ark").post(`/mods/${modId}/strings`, { key, english: newValue })
            if (res.ok) {
                // Optimistic update: mark translated if English is non-empty or source is blank.
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

    // Uses pointer events with setPointerCapture for reliable cross-browser drag
    // behavior. The resizer div is a narrow handle rendered at the right edge of
    // each <th>. Minimum column width is clamped to 80px.

    /**
     * This memoized computation derives the visible rows from the full strings
     * array. It applies three stages in order:
     *   1. Filter by translation status (all / translated / untranslated)
     *   2. Filter by free-text search across key, source, and english fields
     *   3. Sort by the currently active column + direction
     *
     * Note: A string with blank source text is treated as "done" (nothing to
     * translate), matching the same logic used in `handleSaveString`.
     */
    const processedStrings = React.useMemo(() => {
        return sortStrings(filterStrings(strings, filter, search), sortConfig)
    }, [strings, filter, search, sortConfig])

    /**
     * Writes saved translations back to the mod's original CSV files on disk.
     * POST `/api/mods/:modId/export` -> `{ applied, files_written }`.
     *
     * On success, reports how many translations were applied and which files were
     * written.
     *
     * @param resync When true, restores the original files first and re-applies every translation.
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

    /**
     * Resets the mod by clearing all translation data and restoring the
     * original CSV files (if they were backed up before the first export).
     * POST `/api/mods/:modId/reset`.
     */
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

    /**
     * Clears only the English translations for all strings in this mod, resetting
     * them to empty. This allows all rows to be re-sent to the AI provider.
     * POST `/api/mods/:modId/clear-translations`.
     *
     * Unlike `handleClearCache`, this preserves the extracted source strings and
     * mod metadata — only the English column is wiped.
     */
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

    /**
     * Opens the mod's local folder in the system file explorer.
     * POST `/api/mods/:modId/open`.
     *
     * This is a convenience action so users can inspect or manually edit
     * the mod's CSV files on disk.
     */
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

                    {/* --- History Backup Modal --- */}
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

                    {/* --- API Response Viewer Modal --- */}
                    {showApiResponses && modId && <ApiResponsesModal modId={modId} onClose={() => setShowApiResponses(false)} />}

                    {/* --- Translation Confirmation Modal ---
                Shown after handleTranslateClick fetches a preview. Displays
                prompt previews, batch counts, and cost estimates. On confirm,
                starts the iterative batch translation loop via the hook. */}
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

                    {/* --- Batch Translation Review Modal ---
                Shown automatically when the iterative hook pauses for glossary
                suggestion review between batches. Closing the modal pauses the
                process; the user can resume via the paused banner below. */}
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

                    {/* --- Confirm Modal ---
                Single reusable confirmation modal that handles all destructive
                action confirmations. The `confirmModal` state determines which
                action to dispatch on confirm. */}
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
