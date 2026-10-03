/**
 * Panel sayfasına açılan TEK kapı.
 *
 * Bilinçli olarak neredeyse boş: panel kabuğun içinde de dışında da aynı
 * çalışsın istiyoruz. Yalnız "uygulamadayım" bilgisi veriliyor; ileride
 * gerekirse panel buna bakıp davranış değiştirebilir.
 */
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('bernzMasaustu', {
  surum: '1.0.0',
  platform: process.platform,
})
