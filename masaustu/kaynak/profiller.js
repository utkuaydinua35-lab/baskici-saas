/**
 * Uygulama PROFİLLERİ — aynı kabuk, iki uygulama.
 *
 * bayi   → BERNZ Bayi    (bayi paneli, bayiye verilir)
 * studio → BERNZ Stüdyo  (yönetim paneli, atölye ekibine)
 *
 * Kod tek: pencere, bildirim yoklaması, menü ve güvenlik ayarları ortak.
 * Değişen yalnız açılan adres, uygulama adı/kimliği ve bildirimlerin
 * sorulduğu uç. Hangi profilin paketlendiği package.json'a yazılır
 * (electron-builder extraMetadata.bernzProfil) — çalışırken oradan okunur.
 */
const PROFILLER = {
  bayi: {
    ad: 'BERNZ Bayi',
    appId: 'com.bernzcompany.bayi',
    url: 'https://studio.bernzcompany.com/bayii',
    // Bayi olay akışı: kargoya verilen siparişler + atölyeden mesajlar
    bildirimUcu: '/api/bayii/bildirimler',
  },
  studio: {
    ad: 'BERNZ Stüdyo',
    appId: 'com.bernzcompany.studio',
    url: 'https://studio.bernzcompany.com/',
    // Yönetim olay akışı: panelin kendi bildirim kayıtları
    bildirimUcu: '/api/notifications/akis',
  },
}

function profilSec() {
  // 1) Geliştirmede ortam değişkeni, 2) pakette package.json'a gömülen değer
  const istenen = process.env.BERNZ_PROFIL
    || (() => {
      try { return require('../package.json').bernzProfil } catch { return null }
    })()
  return PROFILLER[istenen] || PROFILLER.bayi
}

module.exports = { PROFILLER, profilSec }
