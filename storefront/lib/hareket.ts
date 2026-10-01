// "Hareketi azalt" sorgusu — tema ayarına göre (animations.hareket_tercihi).
//  uy:        ziyaretçinin işletim sistemi tercihine uyulur. Windows'ta
//             "Animasyon efektleri" kapalıysa (sık görülür) tarayıcı
//             prefers-reduced-motion: reduce bildirir → animasyonlar durur.
//  her_zaman: <html data-hareket="hep">; sistem tercihi yok sayılır,
//             animasyonlar her cihazda oynar. Ziyaretçi footer'daki
//             "Animasyonları durdur" ile yine durdurabilir.
// Gerçek bir MediaQueryList döner (.matches + change dinleyicisi çalışır).
export function hareketSorgusu(): MediaQueryList {
  const hep = typeof document !== "undefined" && document.documentElement.dataset.hareket === "hep";
  return matchMedia(hep ? "not all" : "(prefers-reduced-motion: reduce)");
}
