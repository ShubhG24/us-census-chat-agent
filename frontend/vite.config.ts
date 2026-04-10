import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Disable SPA fallback: unknown paths return 404 instead of index.html
  appType: 'mpa',
  plugins: [react()],
  server: {
    proxy: {
      // Same-origin fetches in dev (e.g. fetch('/health')) hit Vite; forward API routes to FastAPI.
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
