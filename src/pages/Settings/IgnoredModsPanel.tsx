import React, { useState } from "react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { FaQuestion, FaSteam, FaTimes } from "react-icons/fa"
import Panel from "@/components/ui/Panel"
import { API_BASE, fetchJson } from "@/lib/api"

/** One ignored mod as described by GET /api/settings/ignored-mods. */
export interface IgnoredModInfo {
    id: string
    /** The mod's name, or its id when it is not installed. */
    name: string
    author: string
    /** Cover image path under `/workshop`. */
    preview_image: string | null
    url: string | null
    /** Whether the mod's Workshop folder is on disk. */
    installed: boolean
}

/** Props for IgnoredModsPanel. */
interface IgnoredModsPanelProps {
    /** Workshop ids hidden from the dashboard. */
    mods: string[]
    onChange: (mods: string[]) => void
}

/** Props for IgnoredModRow. */
interface IgnoredModRowProps {
    id: string
    /** Undefined until the lookup answers, or when it fails. */
    info?: IgnoredModInfo
    onRemove: () => void
}

/**
 * One ignored mod with its cover, name and author, falling back to the bare id until the lookup answers.
 *
 * @param props The mod's id, its looked-up details and the remove handler.
 * @returns The row.
 */
const IgnoredModRow: React.FC<IgnoredModRowProps> = ({ id, info, onRemove }) => {
    const [imageFailed, setImageFailed] = useState(false)
    const name = info?.name ?? id
    return (
        <li className="ignored-mod" data-mod-id={id}>
            <div className="ignored-mod-cover">
                {info?.preview_image && !imageFailed ? <img src={`${API_BASE}${info.preview_image}`} alt="" loading="lazy" onError={() => setImageFailed(true)} /> : <FaQuestion />}
            </div>
            <div className="ignored-mod-info">
                <span className="ignored-mod-name">{name}</span>
                {info?.author && <span className="ignored-mod-author">by {info.author}</span>}
                {info && !info.installed && <span className="ignored-mod-missing">Not installed</span>}
            </div>
            {name !== id && <span className="ignored-mod-id">{id}</span>}
            {info?.url && (
                <a href={info.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-icon" title="Open mod page" aria-label={`Open ${name} on Steam`}>
                    <FaSteam />
                </a>
            )}
            <button type="button" className="btn btn-outline btn-icon" aria-label={`Remove ${id}`} title="Stop ignoring" onClick={onRemove}>
                <FaTimes />
            </button>
        </li>
    )
}

/**
 * Settings panel for the workshop ids the dashboard hides, shown with each mod's name and cover so the ids are recognizable.
 *
 * @param props The ignored ids and their change handler.
 * @returns The ignored mods panel.
 */
const IgnoredModsPanel: React.FC<IgnoredModsPanelProps> = ({ mods, onChange }) => {
    const [newMod, setNewMod] = useState("")
    const canAdd = newMod !== "" && !mods.includes(newMod)
    // Keyed on the draft list so an added id resolves before the form is saved. The previous answer stays up meanwhile.
    const { data } = useQuery({
        queryKey: ["ignored-mods", mods],
        queryFn: () => fetchJson<IgnoredModInfo[]>(`${API_BASE}/settings/ignored-mods?ids=${encodeURIComponent(mods.join(","))}`),
        enabled: mods.length > 0,
        placeholderData: keepPreviousData,
    })
    const infoById = new Map((Array.isArray(data) ? data : []).map((info) => [info.id, info]))

    const add = () => {
        if (!canAdd) return
        onChange([...mods, newMod])
        setNewMod("")
    }

    return (
        <Panel
            className="settings-panel"
            title="Ignored Mods"
            help="Mods listed here are hidden from the dashboard. Useful for system mods, English-only mods, or mods you don't need to translate. You can also hide a mod from its dashboard card."
        >
            <div className="settings-inline-row">
                <input
                    type="text"
                    aria-label="Workshop mod ID"
                    className="input"
                    placeholder="Workshop mod ID"
                    value={newMod}
                    onChange={(e) => setNewMod(e.target.value.trim())}
                    onKeyDown={(e) => {
                        if (e.key === "Enter") add()
                    }}
                />
                <button className="btn btn-primary" disabled={!canAdd} onClick={add}>
                    Add
                </button>
            </div>
            {mods.length > 0 && (
                <ul className="ignored-mod-list">
                    {mods.map((id) => (
                        <IgnoredModRow key={id} id={id} info={infoById.get(id)} onRemove={() => onChange(mods.filter((m) => m !== id))} />
                    ))}
                </ul>
            )}
        </Panel>
    )
}

export default IgnoredModsPanel
