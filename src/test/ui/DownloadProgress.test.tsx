import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import DownloadProgress from "@/ui/DownloadProgress"

const MB = 1024 * 1024

describe("DownloadProgress", () => {
    it("shows the bar at the rounded percent and the size in megabytes", () => {
        render(<DownloadProgress completed={512 * MB} total={1024 * MB} />)
        expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50")
        expect(screen.getByText("50% (512 / 1024 MB)")).toBeInTheDocument()
    })
})
