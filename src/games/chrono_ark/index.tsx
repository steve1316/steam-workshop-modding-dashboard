import chronoArkLogo from "@/assets/games/chrono_ark.png"
import { registerGame } from "@/games/registry"
import { chronoArkNav } from "@/games/chrono_ark/nav"
import { ChronoArkRoutes } from "@/games/chrono_ark/routes"

/** Side-effect import that registers Chrono Ark before the router renders. */
registerGame({
    id: "chrono_ark",
    slug: "chrono_ark",
    displayName: "Chrono Ark",
    icon: "chrono_ark",
    branding: {
        logo: chronoArkLogo,
        accent: "#38bdf8",
        gradient: "linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)",
        subtitle: "Translation tools",
    },
    nav: chronoArkNav,
    routes: () => <ChronoArkRoutes />,
})

// Keeps TypeScript treating this file as a module.
export {}
