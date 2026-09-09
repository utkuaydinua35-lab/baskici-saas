import { StrictMode, useState } from 'react'
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
import PlatformSecici, { secilenPlatform, STUDIO_ADRES } from './PlatformSecici'
nativeKur()

/**
 * Uygulamada iki panel tek pakette duruyor; hangisinin açılacağı bir kez
 * sorulur ve hatırlanır. Web'de `secilenPlatform()` her zaman 'magaza'
 * döndüğü için bu sarmalayıcı hiçbir şey değiştirmez.
 */
function Kok() {
  const [platform, setPlatform] = useState(secilenPlatform)

  // Daha önce Studio seçilmişse doğrudan oraya git — panel hiç çizilmesin.
  // Zaten /studio altındaysak yönlendirme YAPMA: Capacitor uzantısız yolları
  // köke düşürdüğü için bu, boş ekranla sonuçlanan bir döngü olurdu.
  if (platform === 'studio' && !location.pathname.startsWith('/studio')) {
    location.replace(STUDIO_ADRES)
    return null
  }
  if (!platform) return <PlatformSecici onSec={setPlatform} />

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
