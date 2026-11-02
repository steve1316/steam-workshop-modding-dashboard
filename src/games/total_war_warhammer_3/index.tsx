import { registerGame } from "@/games/registry"
import { tw3Nav } from "@/games/total_war_warhammer_3/nav"
import { TotalWarWarhammer3Routes } from "@/games/total_war_warhammer_3/routes"

registerGame({
    id: "total_war_warhammer_3",
    slug: "warhammer_3",
    displayName: "Warhammer III",
    icon: "total_war_warhammer_3",
    nav: tw3Nav,
    routes: () => <TotalWarWarhammer3Routes />,
})

export {}
