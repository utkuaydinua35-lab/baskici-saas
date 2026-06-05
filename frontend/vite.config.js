import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite dev server config.
// /api/* → backend (port 8000) — bu sayede CORS sorunu yok, frontend
// fetch('/api/auth/login') der gibi yazar.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/storage': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
