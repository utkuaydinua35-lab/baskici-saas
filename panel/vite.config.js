import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Mağaza Paneli dev server — /api ve /storage backend'e proxy'lenir (CORS yok).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
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
