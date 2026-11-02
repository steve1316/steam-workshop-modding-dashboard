import { MdDashboard } from "react-icons/md"
import { FaBook, FaChartLine } from "react-icons/fa"
import type { GameNavEntry } from "@/games/registry"

/** Sidebar entries for Chrono Ark. Settings is excluded because it is cross-game. */
export const chronoArkNav: GameNavEntry[] = [
    { to: "/dashboard", label: "Dashboard", icon: <MdDashboard /> },
    { to: "/glossary", label: "Glossary", icon: <FaBook /> },
    { to: "/statistics", label: "Statistics", icon: <FaChartLine /> },
]
