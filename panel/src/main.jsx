import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './lib/auth'
import { StoreProvider } from './lib/store'
import { ToastProvider } from './components/Toast'
import './index.css'

// Native kabuk davranışları (durum çubuğu, güvenli alan, geri tuşu).
// Web'de hemen çıkar; render'ı BEKLETMEZ.
import './native.css'
import { nativeKur } from './lib/native'
import { nativeMi } from './lib/kamera'
import KabukAkisi from './KabukAkisi'
nativeKur()

/**
 * Panelin tamamı (yönlendirici + sağlayıcılar). Kabuk akışı bunu bir
 * fonksiyon olarak alıyor; böylece giriş/kilit/seçim aşamalarında panel HİÇ
 * kurulmuyor, gereksiz istek atılmıyor.
 */
function Panel() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <StoreProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </StoreProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

/**
 * Web'de doğrudan panel açılır — bugünkü davranış birebir korunur.
 * Uygulamada araya giriş → kilit → platform seçimi akışı girer.
 */
function Kok() {
  if (!nativeMi()) return <Panel />
  return <KabukAkisi panel={() => <Panel />} />
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Kok />
  </StrictMode>,
)

// PWA: ana ekrana eklenebilirlik + Web Push. Service worker cache YAPMAZ
// (bkz. public/sw.js) — yalnız kurulabilirlik ve bildirim için.
// Uygulama kabuğunda service worker YOK — `capacitor://` şemasında kayıt
// zaten reddediliyor, sessizce denemenin de faydası yok.
if (!nativeMi() && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}
