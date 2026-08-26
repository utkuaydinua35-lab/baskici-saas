import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './index.css'
import { AuthProvider } from './lib/auth'
import { ToastProvider } from './components/Toast'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)

// PWA — "ana ekrana ekle" için service worker (hiçbir şeyi ele geçirmez)
//
// updateViaCache: 'none' — sw.js HTTP önbelleğinden ASLA okunmasın. Aksi halde
// Cloudflare .js dosyalarını önbelleğe aldığı için eski bir service worker
// saatlerce etkin kalabiliyor. Bu somut bir soruna yol açtı: araya giren eski
// SW, iOS Safari'de dosya yüklemeli isteklerin gövdesini düşürüyordu.
// update() ile her açılışta yeni sürüm sorulur; yenisi varsa skipWaiting +
// clients.claim sayesinde hemen devralır.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js', { updateViaCache: 'none' })
      .then((reg) => { reg.update().catch(() => {}) })
      .catch(() => {})
  })
}
