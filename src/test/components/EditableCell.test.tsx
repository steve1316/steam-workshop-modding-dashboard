import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import EditableCell from "@/components/EditableCell"

describe("EditableCell", () => {
    it("renders value text in display mode", () => {
        render(<EditableCell value="Hello" onSave={vi.fn()} />)
        expect(screen.getByText("Hello")).toBeInTheDocument()
    })

    it("renders placeholder when value is empty", () => {
        render(<EditableCell value="" onSave={vi.fn()} placeholder="Enter text..." />)
        expect(screen.getByText("Enter text...")).toBeInTheDocument()
    })

    it("clicking enters edit mode with textarea", async () => {
        const user = userEvent.setup()
        render(<EditableCell value="Hello" onSave={vi.fn()} />)
        await user.click(screen.getByText("Hello"))
        expect(screen.getByRole("textbox")).toHaveValue("Hello")
    })

    it("typing updates the textarea", async () => {
        const user = userEvent.setup()
        render(<EditableCell value="Hello" onSave={vi.fn()} />)
        await user.click(screen.getByText("Hello"))
        const textarea = screen.getByRole("textbox")
        await user.clear(textarea)
        await user.type(textarea, "World")
        expect(textarea).toHaveValue("World")
    })

    it("blur commits changed value via onSave", async () => {
        const onSave = vi.fn()
        const user = userEvent.setup()
        render(<EditableCell value="Hello" onSave={onSave} />)
        await user.click(screen.getByText("Hello"))
        const textarea = screen.getByRole("textbox")
        await user.clear(textarea)
        await user.type(textarea, "World")
        await user.tab()
        expect(onSave).toHaveBeenCalledWith("World")
    })

    it("blur does NOT call onSave when value unchanged", async () => {
        const onSave = vi.fn()
        const user = userEvent.setup()
        render(<EditableCell value="Hello" onSave={onSave} />)
        await user.click(screen.getByText("Hello"))
        await user.tab()
        expect(onSave).not.toHaveBeenCalled()
    })

    it("escape reverts to original value and exits edit mode", async () => {
        const onSave = vi.fn()
        const user = userEvent.setup()
        render(<EditableCell value="Hello" onSave={onSave} />)
        await user.click(screen.getByText("Hello"))
        const textarea = screen.getByRole("textbox")
        await user.clear(textarea)
        await user.type(textarea, "Changed")
        await user.keyboard("{Escape}")
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
        expect(screen.getByText("Hello")).toBeInTheDocument()
        expect(onSave).not.toHaveBeenCalled()
    })

    it("ctrl+enter commits value", async () => {
        const onSave = vi.fn()
        const user = userEvent.setup()
        render(<EditableCell value="Hello" onSave={onSave} />)
        await user.click(screen.getByText("Hello"))
        const textarea = screen.getByRole("textbox")
        await user.clear(textarea)
        await user.type(textarea, "New")
        await user.keyboard("{Control>}{Enter}{/Control}")
        expect(onSave).toHaveBeenCalledWith("New")
    })
})
