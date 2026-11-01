import { registerGame } from "../registry"
import { chronoArkNav } from "./nav"
import { ChronoArkRoutes } from "./routes"

/** Side-effect import that registers Chrono Ark before the router renders. */
registerGame({
    id: "chrono_ark",
    slug: "chrono_ark",
    displayName: "Chrono Ark",
    icon: "chrono_ark",
    nav: chronoArkNav,
    routes: () => <ChronoArkRoutes />,
})

// Keeps TypeScript treating this file as a module.
export {}
