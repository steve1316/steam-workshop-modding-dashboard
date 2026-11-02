import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClientProvider } from "@tanstack/react-query"
import "@/index.css"
import App from "@/App.tsx"
import { createQueryClient } from "@/lib/queryClient"

createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <QueryClientProvider client={createQueryClient()}>
            <BrowserRouter>
                <App />
            </BrowserRouter>
        </QueryClientProvider>
    </StrictMode>
)
