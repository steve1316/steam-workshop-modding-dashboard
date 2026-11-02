import wh3Logo from "@/assets/games/wh3.png"
import { registerGame } from "@/games/registry"
import SettingsPanels from "@/games/total_war_warhammer_3/components/SettingsPanels"
import { SETTINGS_KEYS } from "@/games/total_war_warhammer_3/components/SettingsPanels/helpers"
import { tw3Nav } from "@/games/total_war_warhammer_3/nav"
import { TotalWarWarhammer3Routes } from "@/games/total_war_warhammer_3/routes"
import "@/games/total_war_warhammer_3/styles.css"

registerGame({
    id: "total_war_warhammer_3",
    slug: "warhammer_3",
    displayName: "Warhammer III",
    icon: "total_war_warhammer_3",
    branding: {
        logo: wh3Logo,
        accent: "#dc2626",
        gradient: "linear-gradient(135deg, #dc2626 0%, #f97316 100%)",
        subtitle: "Workshop tools",
    },
    nav: tw3Nav,
    routes: () => <TotalWarWarhammer3Routes />,
    settingsPanel: { keys: SETTINGS_KEYS, Panel: SettingsPanels },
})

export {}
