import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, HashRouter } from 'react-router-dom'
import App from './App.jsx'
import './index.css'
import { AuthProvider } from './lib/auth'
import { ToastProvider } from './components/Toast'
import { TEMEL, nativeMi } from './lib/taban'

// Uygulama derlemesinde (TEMEL dolu) hash tabanlı, web'de yol tabanlı.
const Router = TEMEL ? HashRouter : BrowserRouter

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* Uygulamada Studio, mağaza paneliyle aynı pakette `/studio/` altında
        duruyor. Orada YOL TABANLI yönlendirme kullanılamaz: Capacitor'ün
        yerel sunucusu `/studio/siparisler` gibi uzantısız bir yolu KÖKTEKİ
        index.html'e düşürüyor, yani mağaza paneli açılıyordu. Hash tabanlı
        yönlendiricide adres hep `/studio/index.html#/...` olduğu için böyle
        bir çözümleme hiç gerekmez. Web'de TEMEL boş → BrowserRouter, yani
        adresler ve davranış bugünküyle birebir aynı. */}
    <Router>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </Router>
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
// Uygulama kabuğunda service worker YOK: sayfa `capacitor://` şemasından
// açılıyor, kayıt zaten reddedilir; ayrıca paketlenmiş dosyaların önüne
// geçen bir SW eski sürümü kilitleyebilirdi.
if (!nativeMi() && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js', { updateViaCache: 'none' })
      .then((reg) => { reg.update().catch(() => {}) })
      .catch(() => {})
  })
}
