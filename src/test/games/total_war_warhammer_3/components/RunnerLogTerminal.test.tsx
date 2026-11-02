import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"
import RunnerLogTerminal from "@/games/total_war_warhammer_3/components/RunnerLogTerminal"
import { _resetUseRunnerLogForTests, appendLine } from "@/games/total_war_warhammer_3/hooks/useRunnerLog"

afterEach(() => _resetUseRunnerLogForTests())

describe("RunnerLogTerminal", () => {
    it("renders the empty placeholder when the log has no entries", () => {
        render(<RunnerLogTerminal />)
        expect(screen.getByText(/No output yet/i)).toBeInTheDocument()
    })

    it("renders a data entry's line text", () => {
        appendLine({ kind: "data", line: "compiling pack...", ts: "" })
        render(<RunnerLogTerminal />)
        expect(screen.getByText("compiling pack...")).toBeInTheDocument()
    })

    it("renders separators with a distinct test id", () => {
        appendLine({ kind: "separator", text: "--- Starting Dynamic RoR ---" })
        render(<RunnerLogTerminal />)
        const sep = screen.getByText("--- Starting Dynamic RoR ---")
        expect(sep).toBeInTheDocument()
        expect(sep).toHaveAttribute("data-testid", "log-separator")
    })

    it("Clear button empties the log", async () => {
        appendLine({ kind: "data", line: "row 1", ts: "" })
        appendLine({ kind: "data", line: "row 2", ts: "" })
        render(<RunnerLogTerminal />)
        expect(screen.getByText("row 1")).toBeInTheDocument()
        await userEvent.setup().click(screen.getByRole("button", { name: /clear/i }))
        expect(screen.queryByText("row 1")).not.toBeInTheDocument()
        expect(screen.getByText(/No output yet/i)).toBeInTheDocument()
    })
})
