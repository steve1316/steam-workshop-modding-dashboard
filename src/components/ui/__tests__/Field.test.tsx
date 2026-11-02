import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import Field from "@/components/ui/Field"

describe("Field", () => {
    it("links its label to the control so getByLabelText finds it", () => {
        render(
            <Field label="Source Game" htmlFor="source-game">
                <input id="source-game" className="input" />
            </Field>
        )
        expect(screen.getByLabelText("Source Game")).toHaveClass("input")
    })

    it("renders the label with the shared field-label class", () => {
        render(
            <Field label="Character Name" htmlFor="character-name">
                <input id="character-name" />
            </Field>
        )
        expect(screen.getByText("Character Name")).toHaveClass("field-label")
    })
})
