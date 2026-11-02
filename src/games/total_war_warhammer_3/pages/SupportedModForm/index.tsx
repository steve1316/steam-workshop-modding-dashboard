import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useGameSlug } from "@/games/useGameSlug"

import ConfirmModal from "@/components/ConfirmModal"
import { createSupportedMod, deleteSupportedMod, fetchSupportedEffectsCategories, fetchSupportedMods, updateSupportedMod } from "@/games/total_war_warhammer_3/api"
import Banner from "@/ui/Banner"
import PageHeader from "@/ui/PageHeader"
import BasicsSection from "@/games/total_war_warhammer_3/pages/SupportedModForm/sections/Basics"
import { emptyBasicsState, type BasicsState } from "@/games/total_war_warhammer_3/pages/SupportedModForm/sections/basicsState"
import CharacterOverridesSection, { type CharacterRow, type FactionEntry } from "@/games/total_war_warhammer_3/pages/SupportedModForm/sections/CharacterOverrides"
import ModifiedAttributesSection from "@/games/total_war_warhammer_3/pages/SupportedModForm/sections/ModifiedAttributes"
import PatternOverridesSection, { type PatternOverrideRow } from "@/games/total_war_warhammer_3/pages/SupportedModForm/sections/PatternOverrides"
import MiscSection from "@/games/total_war_warhammer_3/pages/SupportedModForm/sections/Misc"

/**
 * Add/edit page for one `SUPPORTED_MODS` entry. Mode comes from the route (`new` vs `edit/:packageName`).
 *
 * @returns The form page.
 */
const SupportedModFormPage = () => {
    const { packageName } = useParams()
    const navigate = useNavigate()
    const slug = useGameSlug()
    const isEdit = Boolean(packageName)

    const [basics, setBasics] = useState<BasicsState>(emptyBasicsState)
    const [modifiedAttributes, setModifiedAttributes] = useState<string[]>([])
    const [effectCategories, setEffectCategories] = useState<string[]>([])
    const [patternOverrides, setPatternOverrides] = useState<PatternOverrideRow[]>([])
    const [characterOverrides, setCharacterOverrides] = useState<FactionEntry[]>([])
    const [ignoreGeneration, setIgnoreGeneration] = useState(false)
    const [confirmDelete, setConfirmDelete] = useState(false)
    const [submitting, setSubmitting] = useState(false)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)

    useEffect(() => {
        fetchSupportedEffectsCategories()
            .then(setEffectCategories)
            .catch(() => setEffectCategories([]))
    }, [])

    useEffect(() => {
        if (!isEdit || !packageName) return
        fetchSupportedMods()
            .then((mods) => {
                const target = mods.find((m) => m.package_name === packageName)
                if (!target) {
                    setErrorMessage(`Mod not found: ${packageName}`)
                    return
                }
                setBasics({
                    name: target.name,
                    package_name: target.package_name,
                    workshop_id: target.workshop_id ?? "",
                    custom_path: !target.workshop_id && Boolean(target.path),
                    path: target.path ?? "",
                })
                setModifiedAttributes(target.modified_attributes ?? [])
                const rows: PatternOverrideRow[] = Object.entries((target.pattern_overrides ?? {}) as Record<string, string>).map(([pattern, faction]) => ({ pattern, faction }))
                setPatternOverrides(rows)
                const factions: FactionEntry[] = Object.entries((target.character_overrides ?? {}) as Record<string, { allowed_lords?: CharacterRow[]; allowed_heroes?: CharacterRow[] }>).map(
                    ([faction, body]) => ({
                        faction,
                        allowed_lords: (body.allowed_lords ?? []).map((r) => ({ land_unit: r.land_unit ?? "", agent_subtype: r.agent_subtype ?? "", skill_overrides: r.skill_overrides ?? "" })),
                        allowed_heroes: (body.allowed_heroes ?? []).map((r) => ({ land_unit: r.land_unit ?? "", agent_subtype: r.agent_subtype ?? "", skill_overrides: r.skill_overrides ?? "" })),
                    })
                )
                setCharacterOverrides(factions)
                setIgnoreGeneration(Boolean((target as Record<string, unknown>).ignore_generation))
            })
            .catch((err: unknown) => setErrorMessage(err instanceof Error ? err.message : "Failed to load mod"))
    }, [isEdit, packageName])

    const serializeEntry = () => ({
        name: basics.name,
        package_name: basics.package_name,
        workshop_id: basics.custom_path ? undefined : basics.workshop_id,
        custom_path: basics.custom_path,
        path: basics.custom_path ? basics.path : undefined,
        modified_attributes: modifiedAttributes,
        pattern_overrides: patternOverrides.length > 0 ? Object.fromEntries(patternOverrides.map((r) => [r.pattern, r.faction])) : undefined,
        ignore_generation: ignoreGeneration ? true : undefined,
        character_overrides:
            characterOverrides.length > 0
                ? Object.fromEntries(
                      characterOverrides.map((f) => [
                          f.faction,
                          {
                              allowed_lords: f.allowed_lords
                                  .filter((r) => r.land_unit || r.agent_subtype)
                                  .map((r) => ({ land_unit: r.land_unit, agent_subtype: r.agent_subtype, ...(r.skill_overrides ? { skill_overrides: r.skill_overrides } : {}) })),
                              allowed_heroes: f.allowed_heroes
                                  .filter((r) => r.land_unit || r.agent_subtype)
                                  .map((r) => ({ land_unit: r.land_unit, agent_subtype: r.agent_subtype, ...(r.skill_overrides ? { skill_overrides: r.skill_overrides } : {}) })),
                          },
                      ])
                  )
                : undefined,
    })

    const handleDelete = async () => {
        if (!packageName) return
        setSubmitting(true)
        setErrorMessage(null)
        try {
            await deleteSupportedMod(packageName)
            navigate(`/${slug}/supported-mods`)
        } catch (err: unknown) {
            setErrorMessage(err instanceof Error ? err.message : "Delete failed")
        } finally {
            setSubmitting(false)
            setConfirmDelete(false)
        }
    }

    const handleSave = async () => {
        if (!basics.name.trim()) {
            setErrorMessage("Name is required")
            return
        }
        if (!basics.package_name.trim()) {
            setErrorMessage("Package name is required")
            return
        }
        setSubmitting(true)
        setErrorMessage(null)
        try {
            if (isEdit && packageName) {
                await updateSupportedMod(packageName, serializeEntry())
            } else {
                await createSupportedMod(serializeEntry())
            }
            navigate(`/${slug}/supported-mods`)
        } catch (err: unknown) {
            setErrorMessage(err instanceof Error ? err.message : "Save failed")
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <div className="form-page">
            <PageHeader
                title={isEdit ? `Edit Mod: ${packageName}` : "Add Mod"}
                actions={
                    <>
                        {isEdit && (
                            <button type="button" className="btn btn-danger" onClick={() => setConfirmDelete(true)} disabled={submitting}>
                                Delete
                            </button>
                        )}
                        <button type="button" className="btn btn-primary" onClick={handleSave} disabled={submitting}>
                            {submitting ? "Saving..." : "Save"}
                        </button>
                        <button type="button" className="btn btn-outline" onClick={() => navigate(`/${slug}/supported-mods`)} disabled={submitting}>
                            Cancel
                        </button>
                    </>
                }
            />
            {errorMessage && (
                <Banner tone="error" onDismiss={() => setErrorMessage(null)}>
                    {errorMessage}
                </Banner>
            )}
            <BasicsSection value={basics} onChange={setBasics} lockPackageName={isEdit} />
            <ModifiedAttributesSection value={modifiedAttributes} suggestions={effectCategories} onChange={setModifiedAttributes} />
            <PatternOverridesSection value={patternOverrides} onChange={setPatternOverrides} />
            <CharacterOverridesSection value={characterOverrides} onChange={setCharacterOverrides} />
            <MiscSection ignoreGeneration={ignoreGeneration} onChange={setIgnoreGeneration} />
            {confirmDelete && (
                <ConfirmModal
                    title="Delete mod?"
                    message={`Permanently remove ${packageName} from SUPPORTED_MODS?`}
                    confirmLabel="Confirm"
                    cancelLabel="Cancel"
                    onConfirm={handleDelete}
                    onCancel={() => setConfirmDelete(false)}
                />
            )}
        </div>
    )
}

export default SupportedModFormPage
