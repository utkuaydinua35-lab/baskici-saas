/**
 * Native kabuk davranışları — yalnız uygulamada çalışır, web'i etkilemez.
 *
 * İki iş yapar:
 *  1) DURUM ÇUBUĞU. Panel koyu temalı; iOS varsayılanı koyu yazı olduğu için
 *     saat/pil koyu zeminde okunmuyordu. Açık içerik moduna alınır.
 *  2) GÜVENLİ ALAN. Uygulama tam ekran açılır; üstte çentik/Dynamic Island,
 *     altta home göstergesi vardır. Kök öğeye `native` sınıfı eklenir ve CSS
 *     env(safe-area-inset-*) ile dolgu verir (bkz. index.css).
 *
 * Web'de `nativeMi()` false döner; fonksiyon hemen çıkar, eklenti import bile
 * edilmez (dinamik import).
 */
import { nativeMi } from './kamera'

export async function nativeKur() {
  if (!nativeMi()) return
  document.documentElement.classList.add('native')

  try {
    const { StatusBar, Style } = await import('@capacitor/status-bar')
    await StatusBar.setStyle({ style: Style.Dark })   // Dark = AÇIK yazı
    // Android'de çubuğun arkası şeffaf kalırsa içerik altına giriyor.
    if (StatusBar.setOverlaysWebView) {
      await StatusBar.setOverlaysWebView({ overlay: false })
    }
  } catch { /* eklenti yoksa/desteklemiyorsa görünüm biraz farklı olur, akış bozulmaz */ }

  try {
    // Donanım geri tuşu (Android): geçmiş varsa geri git, yoksa uygulamadan
    // çıkma — kullanıcı yanlışlıkla kapatmasın diye ana sayfaya döner.
    const { App } = await import('@capacitor/app')
    App.addListener('backButton', ({ canGoBack }) => {
      if (canGoBack) window.history.back()
      else if (location.pathname !== '/') location.href = '/'
      else App.exitApp()
    })
  } catch { /* iOS'ta geri tuşu yok */ }
}
