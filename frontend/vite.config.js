import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite dev server config.
// /api/* → backend (port 8000) — bu sayede CORS sorunu yok, frontend
// fetch('/api/auth/login') der gibi yazar.
// VITE_ALT_YOL: uygulama (Capacitor) derlemesinde Studio, mağaza paneliyle
// AYNI paketin içinde `/studio/` alt klasöründe duruyor; varlık adresleri ve
// yönlendirici kökü buna göre kurulmalı. Web derlemesinde değişken YOK, base
// '/' kalır ve bugünkü davranış birebir korunur.
const ALT_YOL = process.env.VITE_ALT_YOL || '/'

export default defineConfig({
  base: ALT_YOL,
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
  // `vite preview` URETIM derlemesini servis eder. Ayni vekil buraya da
  // gerekiyor, yoksa performansi yalnizca dev sunucusunda olcebiliyoruz —
  // dev, lazy chunk'lari istek aninda derledigi icin yaniltici yavas.
  preview: {
    port: 5175,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/storage': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
