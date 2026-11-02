import { render, screen } from "@/testUtils"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import SupportedModCard from "@/games/total_war_warhammer_3/components/SupportedModCard"
import type { SupportedMod, ValidationIssue } from "@/games/total_war_warhammer_3/lib/types"

const BASE_MOD: SupportedMod = {
    name: "Nanu's Cool Mod",
    package_name: "pak_nanu_cool",
    path: "F:\\SteamLibrary\\steamapps\\workshop\\content\\1142710\\3475123987\\pak_nanu_cool.pack",
    workshop_id: "3475123987",
}

const MOD_WITHOUT_WORKSHOP_ID: SupportedMod = {
    ...BASE_MOD,
    path: "C:\\custom\\path\\thing.pack",
    workshop_id: null,
}

const MOD_WITH_ATTRS: SupportedMod = {
    ...BASE_MOD,
    modified_attributes: ["melee_attack_speed", "firing_arc"],
}

const ISSUE: ValidationIssue = {
    mod_package_name: "pak_nanu_cool",
    kind: "missing_effect_category",
    message: "Effect category 'foo' is not in SUPPORTED_EFFECTS",
} as unknown as ValidationIssue

describe("SupportedModCard", () => {
    it("renders the mod name, package_name subtitle, idBadge, and open-folder button", () => {
        const { container } = render(<SupportedModCard mod={BASE_MOD} issues={[]} />)
        expect(screen.getByRole("heading", { name: BASE_MOD.name, level: 3 })).toBeInTheDocument()
        expect(screen.getByText(BASE_MOD.package_name)).toBeInTheDocument()
        const badge = container.querySelector(".id-badge")
        expect(badge?.textContent).toBe(BASE_MOD.workshop_id)
        expect(screen.getByRole("button", { name: /Open Workshop Folder/i })).toBeInTheDocument()
    })

    it("renders the preview image url when workshop_id is set", () => {
        render(<SupportedModCard mod={BASE_MOD} issues={[]} />)
        const img = screen.getByAltText(BASE_MOD.name) as HTMLImageElement
        expect(img.src).toContain(`/api/games/total_war_warhammer_3/packs/${BASE_MOD.workshop_id}/preview`)
    })

    it("omits the preview slot when workshop_id is null", () => {
        render(<SupportedModCard mod={MOD_WITHOUT_WORKSHOP_ID} issues={[]} />)
        expect(screen.queryByRole("img")).not.toBeInTheDocument()
        expect(screen.queryByTestId("workshop-card-placeholder")).not.toBeInTheDocument()
    })

    it("renders the modified_attributes line when non-empty", () => {
        render(<SupportedModCard mod={MOD_WITH_ATTRS} issues={[]} />)
        expect(screen.getByText(/Modified attributes:/i)).toBeInTheDocument()
        expect(screen.getByText(/melee_attack_speed/)).toBeInTheDocument()
        expect(screen.getByText(/firing_arc/)).toBeInTheDocument()
    })

    it("pins the modified_attributes line and the actions to the bottom of the card body in one footer", () => {
        render(<SupportedModCard mod={MOD_WITH_ATTRS} issues={[ISSUE]} onEdit={vi.fn()} />)
        const footer = screen.getByTestId("supported-mod-card-footer")
        expect(footer.style.marginTop).toBe("auto")
        expect(footer).toContainElement(screen.getByText(/Modified attributes:/i))
        expect(footer).toContainElement(screen.getByRole("button", { name: /Edit/i }))
    })

    it("does not render the modified_attributes line when empty", () => {
        render(<SupportedModCard mod={BASE_MOD} issues={[]} />)
        expect(screen.queryByText(/Modified attributes:/i)).not.toBeInTheDocument()
    })

    it("renders the ValidationBadge when issues are present", () => {
        render(<SupportedModCard mod={BASE_MOD} issues={[ISSUE]} />)
        expect(screen.getByLabelText(/validation issue/i)).toBeInTheDocument()
    })

    it("does not render the ValidationBadge when issues are empty", () => {
        render(<SupportedModCard mod={BASE_MOD} issues={[]} />)
        expect(screen.queryByLabelText(/validation issue/i)).not.toBeInTheDocument()
    })

    it("renders each issue message inside the expandable details element", () => {
        const issues: ValidationIssue[] = [
            { ...ISSUE, message: "Effect category 'foo' is not in SUPPORTED_EFFECTS" },
            { ...ISSUE, message: "Path '/x.pack' does not exist on disk" },
        ]
        render(<SupportedModCard mod={BASE_MOD} issues={issues} />)
        expect(screen.getByText(issues[0].message)).toBeInTheDocument()
        expect(screen.getByText(issues[1].message)).toBeInTheDocument()
    })

    it("omits the Open Workshop Folder button when workshop_id is null", () => {
        render(<SupportedModCard mod={MOD_WITHOUT_WORKSHOP_ID} issues={[]} />)
        expect(screen.queryByRole("button", { name: /Open Workshop Folder/i })).not.toBeInTheDocument()
    })

    it("renders an Edit button and calls onEdit with package_name when clicked", async () => {
        const onEdit = vi.fn()
        render(<SupportedModCard mod={BASE_MOD} issues={[]} onEdit={onEdit} />)
        const editBtn = screen.getByRole("button", { name: /Edit/i })
        await userEvent.click(editBtn)
        expect(onEdit).toHaveBeenCalledWith(BASE_MOD.package_name)
    })

    it("omits the Edit button when onEdit is not provided", () => {
        render(<SupportedModCard mod={BASE_MOD} issues={[]} />)
        expect(screen.queryByRole("button", { name: /Edit/i })).not.toBeInTheDocument()
    })
})
