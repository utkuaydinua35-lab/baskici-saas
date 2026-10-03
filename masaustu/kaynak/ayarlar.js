/**
 * Uygulamanın baktığı adres ve zamanlamalar.
 *
 * PANEL_URL geliştirme için ortam değişkeniyle değiştirilebilir:
 *   BERNZ_PANEL_URL=http://localhost:5174/bayii npm run basla
 */
const PANEL_URL = process.env.BERNZ_PANEL_URL
  || 'https://studio.bernzcompany.com/bayii'

// Uygulama kabuğu olduğumuzu panele söyleyen işaret (ileride gerekirse
// panel "uygulamadasın" diye davranış değiştirebilsin).
const KULLANICI_ARACI_EKI = 'BernzBayiMasaustu/1.0'

module.exports = {
  PANEL_URL,
  KULLANICI_ARACI_EKI,
  // Bildirim yoklama aralığı. 60 sn: kargo/mesaj bildirimi için fazlasıyla
  // hızlı, sunucuya yük değil (bayi başına saatte 60 küçük istek).
  YOKLAMA_MS: 60 * 1000,
  // Oturum açılmadan yoklama anlamsız — token gelene kadar bu aralıkla bakılır
  TOKEN_BEKLEME_MS: 10 * 1000,
}
