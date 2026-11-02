import { describe, expect, it } from "vitest"
import { readEventStream } from "@/lib/stream"

/** Build a response whose body yields each chunk as a separate read. */
function streamOf(chunks: string[]): Response {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
        start(controller) {
            for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
            controller.close()
        },
    })
    return new Response(body)
}

describe("readEventStream", () => {
    it("parses each data line in order", async () => {
        const seen: unknown[] = []
        await readEventStream(streamOf(['data: {"n":1}\n\ndata: {"n":2}\n\n']), (e) => {
            seen.push(e)
        })
        expect(seen).toEqual([{ n: 1 }, { n: 2 }])
    })

    it("joins an event split across chunks", async () => {
        const seen: unknown[] = []
        await readEventStream(streamOf(['data: {"msg":"hel', 'lo"}\n\n']), (e) => {
            seen.push(e)
        })
        expect(seen).toEqual([{ msg: "hello" }])
    })

    it("skips malformed and non-data lines", async () => {
        const seen: unknown[] = []
        await readEventStream(streamOf([": ping\n", "data: {oops\n", 'data: {"ok":true}\n']), (e) => {
            seen.push(e)
        })
        expect(seen).toEqual([{ ok: true }])
    })

    it("stops when the handler returns true", async () => {
        const seen: unknown[] = []
        await readEventStream(streamOf(['data: {"n":1}\ndata: {"n":2}\n']), (e) => {
            seen.push(e)
            return true
        })
        expect(seen).toEqual([{ n: 1 }])
    })
})
