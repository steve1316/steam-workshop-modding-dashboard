import { useEffect, useMemo, useRef, useState } from "react"

import DashboardHeader from "@/dashboard/DashboardHeader"
import DashboardSection from "@/dashboard/DashboardSection"
import { progressLabel } from "@/dashboard/progressLabel"
import { useCardWidth } from "@/dashboard/useCardWidth"
import { useScrollRestore } from "@/dashboard/useScrollRestore"
import type { WH3TranslationModSummary } from "@/shared_types"
import Banner from "@/ui/Banner"
import Panel from "@/ui/Panel"
import { matchesSearch } from "@/utils/modFilters"
import PackCard, { type PackEntry } from "@/games/total_war_warhammer_3/components/PackCard"
import PublishAllDialog from "@/games/total_war_warhammer_3/components/PublishAllDialog"
import ScriptRunButton from "@/games/total_war_warhammer_3/components/ScriptRunButton"
import TranslationModCard from "@/games/total_war_warhammer_3/components/TranslationModCard"
import { useRescanAll } from "@/games/total_war_warhammer_3/hooks/useRescanAll"
import { listTranslationMods } from "@/games/total_war_warhammer_3/translationApi"

const PACKS: PackEntry[] = [
    { title: "Nanu's Dynamic RoR Compat", workshopId: "3513364573", scriptId: "update_dynamic_rors" },
    { title: "Nanu's Dynamic RoR Leftover Vanilla", workshopId: "3532864014", scriptId: "update_dynamic_rors_vanilla" },
    { title: "2x Unit Size Compat", workshopId: "3621939685", scriptId: "update_double_unit_size" },
    { title: "50% Melee Attack Speed Compat", workshopId: "3311361199", scriptId: "update_modified_attribute_mods", sharedNote: "Rebuilds with the other modified-attribute packs." },
    { title: "120 Firing Arc Compat", workshopId: "3311361345", scriptId: "update_modified_attribute_mods", sharedNote: "Rebuilds with the other modified-attribute packs." },
    { title: "Double Projectile Velocity Compat", workshopId: "3311361464", scriptId: "update_modified_attribute_mods", sharedNote: "Rebuilds with the other modified-attribute packs." },
    { title: "Land Encounters And Points Of Interest + MCT Support + IEE", workshopId: "3397481450", scriptId: "process_main_units_tables" },
    { title: "Kadons Scrolls of Binding", workshopId: "3398096688" },
    { title: "[GLF] Battle Mage", workshopId: "3387635246", scriptId: "glf_inner_join" },
    { title: "Tabletop Caps - Yet Another Compatibility Megapack", workshopId: "3310629727", scriptId: "update_ttc_compat" },
]

/**
 * TW3 Dashboard: searchable header with Rebuild All and Publish All, an intro panel, then pack and translation mod cards. Last-run timestamps are session-only.
 *
 * @returns The dashboard page.
 */
export default function DashboardPage() {
    // Null until the list request settles, so the section shows a skeleton instead of an empty grid.
    const [translationMods, setTranslationMods] = useState<WH3TranslationModSummary[] | null>(null)
    const [loadError, setLoadError] = useState<string | null>(null)
    const [refreshError, setRefreshError] = useState<string | null>(null)
    const [listing, setListing] = useState(false)
    const [publishAllOpen, setPublishAllOpen] = useState(false)
    const [search, setSearch] = useState("")
    const gridWrapperRef = useRef<HTMLDivElement>(null)
    // After the first list arrives, a failed refresh keeps the cards and shows a banner.
    const hasLoadedRef = useRef(false)
    const rescans = useRescanAll()
    const refreshing = listing || rescans.running

    /**
     * Lists the translation mods, then rescans each in turn for fresh counts. Failed rescans are counted into the error banner and keep their old numbers.
     */
    const refresh = async () => {
        setListing(true)
        setRefreshError(null)
        try {
            const mods = await listTranslationMods()
            // Read the ids first so a malformed response fails here, not while rendering.
            const ids = mods.map((mod) => mod.workshop_id)
            hasLoadedRef.current = true
            setTranslationMods(mods)
            setLoadError(null)
            setListing(false)
            const failed = await rescans.rescanAll(ids)
            if (failed > 0) setRefreshError(`Could not rescan ${failed} translation mod${failed === 1 ? "" : "s"}.`)
        } catch (e) {
            const message = (e as Error).message
            if (hasLoadedRef.current) setRefreshError(`Could not refresh translation mods: ${message}`)
            else setLoadError(`Failed to load translation mods: ${message}`)
            setListing(false)
        }
    }

    /** Clears the load error (bringing the skeleton back) and retries the first load. */
    const retryLoad = () => {
        setLoadError(null)
        refresh()
    }

    useEffect(() => {
        refresh()
        // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once on open
    }, [])

    const query = search.trim()
    const visiblePacks = useMemo(() => PACKS.filter((pack) => matchesSearch(search, pack.title, pack.workshopId)), [search])
    const visibleMods = useMemo(() => (translationMods ?? []).filter((mod) => matchesSearch(search, mod.display_name, mod.workshop_id)), [translationMods, search])
    const cardWidth = useCardWidth(gridWrapperRef, visiblePacks.length + visibleMods.length)

    // Scroll back to the mod the user opened once the list is on screen.
    useScrollRestore(translationMods !== null)

    return (
        <>
            <DashboardHeader
                title="Warhammer III Workshop"
                tagline="Manage and rebuild your compat packs."
                search={search}
                onSearchChange={setSearch}
                searchPlaceholder="Search by name or workshop ID..."
                searchWidth={cardWidth}
                actions={
                    <>
                        <button type="button" className="btn btn-outline" onClick={refresh} disabled={refreshing}>
                            {progressLabel("Refresh", "Refreshing", refreshing, rescans.progress)}
                        </button>
                        <ScriptRunButton scriptId="update" label="Rebuild All" />
                        <button type="button" className="btn btn-primary" onClick={() => setPublishAllOpen(true)}>
                            Publish All
                        </button>
                    </>
                }
            />

            <Panel
                title="About the Compat Packs"
                help={
                    <>
                        Each card below is one compat pack you maintain on the Steam Workshop. The <strong>Rebuild</strong> button regenerates that pack by running the matching helper script against
                        your local mod files. Use <strong>Rebuild All</strong> to run every pipeline in sequence.
                    </>
                }
            />

            {refreshError && (
                <Banner tone="error" onDismiss={() => setRefreshError(null)}>
                    {refreshError}
                </Banner>
            )}

            <div ref={gridWrapperRef}>
                <DashboardSection title="Pack Mods" loading={false} empty={visiblePacks.length === 0} emptyMessage={`No packs match "${query}".`}>
                    <div className="mod-grid">
                        {visiblePacks.map((pack) => (
                            <PackCard key={pack.workshopId} pack={pack} searchQuery={query} />
                        ))}
                    </div>
                </DashboardSection>

                <DashboardSection
                    title="Translation Mods"
                    loading={translationMods === null}
                    skeletonCount={3}
                    skeletonLabel="Loading translation mods"
                    error={loadError}
                    onRetry={retryLoad}
                    empty={visibleMods.length === 0}
                    emptyMessage={query ? `No translation mods match "${query}".` : "No translation mods found."}
                >
                    <div className="mod-grid">
                        {visibleMods.map((mod) => (
                            <TranslationModCard key={mod.workshop_id} mod={mod} searchQuery={query} progress={rescans.progressByMod[mod.workshop_id] ?? null} onRescan={rescans.rescanOne} />
                        ))}
                    </div>
                </DashboardSection>
            </div>

            {publishAllOpen && <PublishAllDialog packs={PACKS} onClose={() => setPublishAllOpen(false)} />}
        </>
    )
}
