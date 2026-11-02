import { render, screen } from "@/testUtils"
import { MemoryRouter } from "react-router-dom"
import userEvent from "@testing-library/user-event"
import ModCard, { NeedsSyncBadge } from "@/components/Dashboard/ModCard"

/**
 * Build a baseline ModCard props object representing a Chrono-Ark-style mod.
 * Individual tests override only the fields they care about.
 */
function baseProps(overrides: Partial<React.ComponentProps<typeof ModCard>> = {}): React.ComponentProps<typeof ModCard> {
    return {
        id: "12345",
        title: "Test Mod",
        idBadge: "12345",
        subtitle: <>by TestAuthor</>,
        previewImageUrl: null,
        progress: {
            leftLabel: "75% Translated",
            rightLabel: "75 / 100 strings",
            segments: [
                { widthPercent: 50, background: "var(--accent-gradient)", title: "50 translated by you" },
                { widthPercent: 25, background: "rgba(148, 163, 184, 0.5)", title: "25 untouched" },
            ],
        },
        stats: [
            { value: 25, label: "Remaining" },
            { value: "CSV", label: "Format" },
        ],
        primaryAction: { label: "View", variant: "warning", onClick: () => undefined },
        ...overrides,
    }
}

const wrap = (ui: React.ReactNode) => <MemoryRouter>{ui}</MemoryRouter>

describe("ModCard", () => {
    it("uses the shared icon-button class for the Steam and rescan actions", () => {
        render(wrap(<ModCard {...baseProps({ steamUrl: "https://example.com", onSync: () => undefined })} />))
        expect(screen.getByTitle("Open mod page")).toHaveClass("btn-icon")
        expect(screen.getByTitle("Rescan workshop folder")).toHaveClass("btn-icon")
    })

    it("renders title, subtitle, and the left progress label", () => {
        render(wrap(<ModCard {...baseProps()} />))
        expect(screen.getByText("Test Mod")).toBeInTheDocument()
        expect(screen.getByText(/TestAuthor/)).toBeInTheDocument()
        expect(screen.getByText("75% Translated")).toBeInTheDocument()
    })

    it("pins progress, stats, and actions to the bottom of the card body in one footer", () => {
        const { container } = render(wrap(<ModCard {...baseProps({ onSync: () => undefined })} />))
        const footer = container.querySelector(".mod-card-footer") as HTMLElement
        expect(footer).not.toBeNull()
        expect(footer.parentElement).toHaveClass("mod-card-content")
        expect(footer.querySelector(".progress-section")).not.toBeNull()
        expect(footer.querySelector(".mod-stats")).not.toBeNull()
        expect(footer.querySelector(".mod-actions")).not.toBeNull()
    })

    it("renders progress bar segments with the correct widths", () => {
        const { container } = render(wrap(<ModCard {...baseProps()} />))
        const segments = container.querySelectorAll(".progress-bar-bg > div")
        expect(segments).toHaveLength(2)
        expect((segments[0] as HTMLElement).style.width).toBe("50%")
        expect((segments[1] as HTMLElement).style.width).toBe("25%")
    })

    it("renders each stat box value and label", () => {
        render(
            wrap(
                <ModCard
                    {...baseProps({
                        stats: [
                            { value: 25, label: "Remaining" },
                            { value: "DLL", label: "Format" },
                        ],
                    })}
                />
            )
        )
        expect(screen.getByText("DLL")).toBeInTheDocument()
        expect(screen.getByText("Remaining")).toBeInTheDocument()
    })

    it("renders the NeedsSyncBadge when passed via badges", () => {
        render(wrap(<ModCard {...baseProps({ badges: <NeedsSyncBadge /> })} />))
        expect(screen.getByText("Needs Sync")).toBeInTheDocument()
    })

    it("omits the NeedsSyncBadge when badges is undefined", () => {
        render(wrap(<ModCard {...baseProps()} />))
        expect(screen.queryByText("Needs Sync")).not.toBeInTheDocument()
    })

    it("calls primaryAction.onClick when the button is clicked", async () => {
        const user = userEvent.setup()
        const onClick = vi.fn()
        render(wrap(<ModCard {...baseProps({ primaryAction: { label: "View", variant: "warning", onClick } })} />))
        await user.click(screen.getByText("View"))
        expect(onClick).toHaveBeenCalled()
    })

    it("renders the secondary action as an outline button and fires its onClick", async () => {
        const user = userEvent.setup()
        const onClick = vi.fn()
        render(wrap(<ModCard {...baseProps({ secondaryAction: { label: "Publish", onClick, title: "Push to Steam" } })} />))
        const button = screen.getByRole("button", { name: "Publish" })
        expect(button).toHaveClass("btn-outline")
        expect(button).toHaveAttribute("title", "Push to Steam")
        await user.click(button)
        expect(onClick).toHaveBeenCalled()
    })

    it("omits the secondary action when it is not set", () => {
        render(wrap(<ModCard {...baseProps()} />))
        expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument()
    })

    it("renders the primary action as a Link when primaryAction.to is set", () => {
        render(wrap(<ModCard {...baseProps({ primaryAction: { label: "Translate ->", variant: "primary", to: "/translation/3315737452" } })} />))
        const link = screen.getByRole("link", { name: /Translate/i })
        expect(link).toHaveAttribute("href", "/translation/3315737452")
    })

    it("renders the Steam link when steamUrl is provided", () => {
        render(wrap(<ModCard {...baseProps({ steamUrl: "https://steam.example" })} />))
        const link = screen.getByTitle("Open mod page")
        expect(link).toHaveAttribute("href", "https://steam.example")
    })

    it("hides the sync button when onSync is undefined", () => {
        render(wrap(<ModCard {...baseProps()} />))
        expect(screen.queryByTitle("Rescan workshop folder")).not.toBeInTheDocument()
    })

    it("renders the sync button and fires onSync when clicked", async () => {
        const user = userEvent.setup()
        const onSync = vi.fn()
        render(wrap(<ModCard {...baseProps({ onSync })} />))
        await user.click(screen.getByTitle("Rescan workshop folder"))
        expect(onSync).toHaveBeenCalled()
    })

    it("renders the hide button only with onHide and fires it when clicked", async () => {
        const user = userEvent.setup()
        const onHide = vi.fn()
        const { rerender } = render(wrap(<ModCard {...baseProps()} />))
        expect(screen.queryByRole("button", { name: "Hide from dashboard" })).not.toBeInTheDocument()
        rerender(wrap(<ModCard {...baseProps({ onHide })} />))
        await user.click(screen.getByRole("button", { name: "Hide from dashboard" }))
        expect(onHide).toHaveBeenCalled()
    })
})
