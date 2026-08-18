import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build straight into ../static/app so FastAPI serves the built site itself.
// One process, one command, no second server in production.
// In development, /api is proxied to FastAPI so `npm run dev` still talks to real data.
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  build: { outDir: '../static/app', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
