import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Mağaza Paneli dev server — /api ve /storage backend'e proxy'lenir (CORS yok).
// PROXY_HEDEF: paralel çalışırken başka porttaki backend'e bağlanmak için
const HEDEF = process.env.PROXY_HEDEF || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    proxy: {
      '/api': {
        target: HEDEF,
        changeOrigin: true,
      },
      '/storage': HEDEF,
    },
  },
  preview: {
    port: 5177,
    proxy: {
      '/api': { target: HEDEF, changeOrigin: true },
      '/storage': HEDEF,
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
