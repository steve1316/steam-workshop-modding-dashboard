/**
 * Read a server-sent event stream, calling `onEvent` with each parsed `data:` line. Malformed lines are skipped.
 *
 * @param res The fetch response whose body carries the stream.
 * @param onEvent Handler for each event. Return `true` to stop reading early.
 */
export async function readEventStream<T = Record<string, unknown>>(res: Response, onEvent: (event: T) => boolean | void): Promise<void> {
    const reader = res.body?.getReader()
    if (!reader) return
    const decoder = new TextDecoder()
    // An event can arrive split across two chunks, so hold the trailing partial line until the next read.
    let buffer = ""
    while (true) {
        const { done, value } = await reader.read()
        if (done) return
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""
        for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            let event: T
            try {
                event = JSON.parse(line.slice(6))
            } catch {
                continue
            }
            if (onEvent(event) === true) {
                await reader.cancel()
                return
            }
        }
    }
}
