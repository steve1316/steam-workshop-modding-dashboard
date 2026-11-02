import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"

import DashboardHeader from "@/components/Dashboard/DashboardHeader"
import DashboardSection from "@/components/Dashboard/DashboardSection"
import { useCardWidth } from "@/hooks/useCardWidth"
import PageHeader from "@/components/ui/PageHeader"
import { matchesSearch } from "@/lib/modFilters"
import { useGameSlug } from "@/hooks/useGameSlug"
import { fetchSupportedMods, RegistryError } from "@/games/total_war_warhammer_3/lib/registryApi"
import type { SupportedMod, ValidationIssue } from "@/games/total_war_warhammer_3/lib/registryApi"
import RegistryErrorBanner from "@/games/total_war_warhammer_3/components/RegistryErrorBanner"
import SupportedModCard from "@/games/total_war_warhammer_3/components/SupportedModCard"
import ValidationPanel from "@/games/total_war_warhammer_3/components/ValidationPanel"
import { useValidation } from "@/games/total_war_warhammer_3/hooks/useValidation"

/**
 * Searchable card grid over `SUPPORTED_MODS` with add and edit, filtering on `name` and `package_name`. A `ValidationPanel` lists broken references.
 *
 * @returns The grid, or a `RegistryErrorBanner` on a backend configuration error.
 */
export default function SupportedModsPage() {
    const navigate = useNavigate()
    const slug = useGameSlug()
    const [mods, setMods] = useState<SupportedMod[] | null>(null)
    const [error, setError] = useState<RegistryError | null>(null)
    // A non-registry load failure such as the backend being down.
    const [loadError, setLoadError] = useState<string | null>(null)
    const [attempt, setAttempt] = useState(0)
    const [search, setSearch] = useState("")
    const gridWrapperRef = useRef<HTMLDivElement>(null)
    const { issues: validationIssues, refresh: refreshValidation } = useValidation()

    useEffect(() => {
        let cancelled = false
        fetchSupportedMods()
            .then((data) => {
                if (!cancelled) setMods(data)
            })
            .catch((err: unknown) => {
                if (cancelled) return
                if (err instanceof RegistryError) setError(err)
                else setLoadError(`Could not load supported mods: ${err instanceof Error ? err.message : String(err)}`)
            })
        return () => {
            cancelled = true
        }
    }, [attempt])

    const issuesByMod = useMemo(() => {
        const map = new Map<string, ValidationIssue[]>()
        for (const issue of validationIssues ?? []) {
            const list = map.get(issue.mod_package_name) ?? []
            list.push(issue)
            map.set(issue.mod_package_name, list)
        }
        return map
    }, [validationIssues])

    const filtered = useMemo(() => (mods ?? []).filter((m) => m.package_name !== "vanilla" && matchesSearch(search, m.name, m.package_name)), [mods, search])
    const cardWidth = useCardWidth(gridWrapperRef, filtered.length)
    const query = search.trim()

    /** Clears the load error (bringing the skeleton back) and reloads. */
    const retry = () => {
        setLoadError(null)
        setAttempt((n) => n + 1)
    }

    if (error) {
        return (
            <>
                <PageHeader title="Supported Mods" />
                <RegistryErrorBanner detail={error.detail} missing={error.missing} />
            </>
        )
    }

    return (
        <>
            <DashboardHeader
                title="Supported Mods"
                tagline="Manage `SUPPORTED_MODS` entries in helper_scripts/data/supported_mods.py."
                search={search}
                onSearchChange={setSearch}
                searchPlaceholder="Search by name or package_name..."
                searchWidth={cardWidth}
                actions={
                    <button type="button" className="btn btn-primary" onClick={() => navigate(`/${slug}/supported-mods/new`)}>
                        + Add Mod
                    </button>
                }
            />
            <ValidationPanel issues={validationIssues} onRefresh={refreshValidation} />
            <div ref={gridWrapperRef}>
                <DashboardSection
                    loading={mods === null}
                    error={loadError}
                    onRetry={retry}
                    empty={filtered.length === 0}
                    emptyMessage={query ? `No mods match "${query}".` : "No supported mods yet. Use + Add Mod to add one."}
                >
                    <div className="mod-grid">
                        {filtered.map((m) => (
                            <SupportedModCard
                                key={m.package_name}
                                mod={m}
                                issues={issuesByMod.get(m.package_name) ?? []}
                                onEdit={(pn) => navigate(`/${slug}/supported-mods/edit/${encodeURIComponent(pn)}`)}
                            />
                        ))}
                    </div>
                </DashboardSection>
            </div>
        </>
    )
}
