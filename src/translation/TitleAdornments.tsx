import { FaExclamationCircle, FaFolderOpen, FaSteam } from "react-icons/fa"

/** Props for SteamLink. */
interface SteamLinkProps {
    href: string
}

/**
 * Steam icon link to the mod's Workshop page.
 *
 * @param href - Workshop page URL.
 * @returns The link.
 */
export function SteamLink({ href }: SteamLinkProps) {
    return (
        <a href={href} target="_blank" rel="noopener noreferrer" className="icon-action icon-action-steam" title="Open on Steam Workshop" aria-label="Open on Steam Workshop">
            <FaSteam />
        </a>
    )
}

/** Props for OpenFolderButton. */
interface OpenFolderButtonProps {
    onClick: () => void
}

/**
 * Folder icon button that opens the mod's local folder.
 *
 * @param onClick - Click handler.
 * @returns The button.
 */
export function OpenFolderButton({ onClick }: OpenFolderButtonProps) {
    return (
        <button type="button" className="icon-action" onClick={onClick} title="Open local folder" aria-label="Open local folder">
            <FaFolderOpen />
        </button>
    )
}

/**
 * Amber pill shown while saved translations are not yet synced to the mod's files.
 *
 * @returns The pill.
 */
export function PendingSyncPill() {
    return (
        <span className="pill pill-warning">
            <FaExclamationCircle size={12} />
            Changes pending sync
        </span>
    )
}
