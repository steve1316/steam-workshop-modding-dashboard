/// <reference types="vitest/config" />
import fs from "fs"
import { fileURLToPath } from "url"
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"

// Read SWMT_API_PORT from backend/.env so the port is shared with Python.
let apiPort = "8008"
try {
  const envFile = fs.readFileSync("backend/.env", "utf-8")
  const match = envFile.match(/^SWMT_API_PORT\s*=\s*(.+)/m)
  if (match) apiPort = match[1].trim()
} catch {
  // No .env file so use the default.
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  define: {
    __API_PORT__: JSON.stringify(apiPort),
  },
  server: {
    watch: {
      // steamcmd writes locked temp files under backend/storage that crash the watcher with EBUSY on Windows.
      ignored: ["**/backend/**", "**/vanilla_text_*/**"],
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
  },
})
