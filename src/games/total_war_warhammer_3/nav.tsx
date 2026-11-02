import { MdDashboard, MdPlayArrow } from "react-icons/md"
import { FaList, FaBook } from "react-icons/fa"
import type { GameNavEntry } from "@/games/registry"

export const tw3Nav: GameNavEntry[] = [
    { to: "/dashboard", label: "Dashboard", icon: <MdDashboard /> },
    { to: "/supported-mods", label: "Supported Mods", icon: <FaList /> },
    { to: "/glossary", label: "Glossary", icon: <FaBook /> },
    { to: "/runner", label: "Runner", icon: <MdPlayArrow /> },
]
