import { useState } from "react"
import Banner from "@/components/ui/Banner"
import Field from "@/components/ui/Field"
import Panel from "@/components/ui/Panel"
import type { GameSettingsPanelProps } from "@/games/registry"
import { API_BASE } from "@/lib/api"

/**
 * WH3's section of the Settings page: helper_scripts and translation mod paths, and the SteamCMD account for Workshop publishing.
 *
 * @param props - See `GameSettingsPanelProps`.
 * @returns The two settings panels.
 */
export default function SettingsPanels({ values, onChange, onSaved, fieldId }: GameSettingsPanelProps) {
    const [steamcmdInstalling, setSteamcmdInstalling] = useState(false)
    const [steamcmdInstallError, setSteamcmdInstallError] = useState<string | null>(null)

    return (
        <>
            <Panel
                className="settings-panel"
                title="Total War: Warhammer III"
                help="Paths used by the helper_scripts script runner and the translation mods' loose source files. Required before triggering rebuilds from the Runner page."
            >
                <div className="form-stack">
                    <Field label="helper_scripts directory" htmlFor={`${fieldId}-tw3-helper`}>
                        <input
                            id={`${fieldId}-tw3-helper`}
                            type="text"
                            className="input"
                            placeholder="C:\path\to\totalwar-modding\helper_scripts"
                            value={values.tw3_helper_path}
                            onChange={(e) => onChange("tw3_helper_path", e.target.value)}
                        />
                    </Field>
                    <Field label="rpfm_cli.exe path (optional, defaults to helper_scripts/rpfm_cli.exe)" htmlFor={`${fieldId}-tw3-rpfm`}>
                        <input
                            id={`${fieldId}-tw3-rpfm`}
                            type="text"
                            className="input"
                            placeholder="leave blank to use default"
                            value={values.tw3_rpfm_cli_path}
                            onChange={(e) => onChange("tw3_rpfm_cli_path", e.target.value)}
                        />
                    </Field>
                    <Field label="Steam library drive (e.g., F:)" htmlFor={`${fieldId}-tw3-drive`}>
                        <input
                            id={`${fieldId}-tw3-drive`}
                            type="text"
                            className="input"
                            placeholder="F:"
                            value={values.tw3_steam_library_drive}
                            onChange={(e) => onChange("tw3_steam_library_drive", e.target.value)}
                        />
                    </Field>
                    <Field label="Translation mods folder (one folder per translation mod)" htmlFor={`${fieldId}-tw3-translation-mods`}>
                        <input
                            id={`${fieldId}-tw3-translation-mods`}
                            type="text"
                            className="input"
                            placeholder="C:\path\to\totalwar-modding\warhammer3_mods"
                            value={values.tw3_translation_mods_path}
                            onChange={(e) => onChange("tw3_translation_mods_path", e.target.value)}
                        />
                    </Field>
                </div>
            </Panel>

            <Panel
                className="settings-panel"
                title="Steam Account"
                help={
                    <>
                        Used by the Publish to Workshop button on the TW3 Dashboard. After saving, run <code>steamcmd +login &lt;username&gt;</code> once in a terminal to complete Steam Guard
                        authentication. SteamCMD will cache the session for ~2 weeks.
                    </>
                }
            >
                <div className="field-label-row">
                    <label className="field-label" htmlFor={`${fieldId}-steamcmd`}>
                        SteamCMD path (steamcmd.exe)
                    </label>
                    <button
                        className="btn btn-outline btn-sm"
                        onClick={async () => {
                            setSteamcmdInstalling(true)
                            setSteamcmdInstallError(null)
                            try {
                                const res = await fetch(`${API_BASE}/steamcmd/install`, { method: "POST" })
                                const data = await res.json()
                                if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
                                onSaved("steamcmd_path", data.path)
                            } catch (err) {
                                setSteamcmdInstallError(err instanceof Error ? err.message : String(err))
                            } finally {
                                setSteamcmdInstalling(false)
                            }
                        }}
                        disabled={steamcmdInstalling}
                        title="Download and extract steamcmd.zip into backend storage, then auto-fill the path below."
                    >
                        {steamcmdInstalling ? "Installing..." : "Install SteamCMD"}
                    </button>
                </div>
                {steamcmdInstallError && (
                    <Banner tone="error" onDismiss={() => setSteamcmdInstallError(null)}>
                        Install failed: {steamcmdInstallError}
                    </Banner>
                )}
                <input
                    id={`${fieldId}-steamcmd`}
                    type="text"
                    className="input settings-field-gap"
                    placeholder="C:\\steamcmd\\steamcmd.exe"
                    value={values.steamcmd_path}
                    onChange={(e) => onChange("steamcmd_path", e.target.value)}
                />

                <Field label="Steam username" htmlFor={`${fieldId}-steam-username`}>
                    <input
                        id={`${fieldId}-steam-username`}
                        type="text"
                        className="input"
                        placeholder="your_steam_username"
                        value={values.steam_username}
                        onChange={(e) => onChange("steam_username", e.target.value)}
                        autoComplete="off"
                    />
                </Field>
            </Panel>
        </>
    )
}
