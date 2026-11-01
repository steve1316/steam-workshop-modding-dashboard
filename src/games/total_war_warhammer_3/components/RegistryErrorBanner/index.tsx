import { Link } from "react-router-dom"

/** Props for `RegistryErrorBanner`. */
interface Props {
    detail: string
    missing?: string[] | null
}

/**
 * Banner for TW3 registry pages when helper_scripts is missing, misconfigured, or has a syntax error. Links to Settings.
 *
 * @param detail Error detail from the API.
 * @param missing Missing settings.
 * @returns The banner.
 */
export default function RegistryErrorBanner({ detail, missing }: Props) {
    return (
        <div className="glass-card" style={{ padding: "1rem", borderLeft: "4px solid var(--warning)" }}>
            <h3 style={{ marginTop: 0 }}>Helper scripts not configured</h3>
            <p>{detail}</p>
            {missing && missing.length > 0 && (
                <ul>
                    {missing.map((m) => (
                        <li key={m}>{m}</li>
                    ))}
                </ul>
            )}
            <Link to="/settings" style={{ color: "var(--accent-primary)" }}>
                Configure in Settings
            </Link>
        </div>
    )
}
