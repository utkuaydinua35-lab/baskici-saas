/**
 * Uygulamanın baktığı adres ve zamanlamalar.
 *
 * Profil (bayi | studio) paketleme sırasında belirlenir; geliştirirken
 * ortam değişkeniyle seçilir:
 *   BERNZ_PROFIL=studio npm run basla
 *   BERNZ_PANEL_URL=http://localhost:5174/bayii npm run basla
 */
const { profilSec } = require('./profiller')

const PROFIL = profilSec()
const PANEL_URL = process.env.BERNZ_PANEL_URL || PROFIL.url

module.exports = {
  PROFIL,
  PANEL_URL,
  UYGULAMA_ADI: PROFIL.ad,
  BILDIRIM_UCU: PROFIL.bildirimUcu,
  // Uygulama kabuğu olduğumuzu panele söyleyen işaret
  KULLANICI_ARACI_EKI: 'BernzMasaustu/1.1',
  // Bildirim yoklama aralığı. 60 sn: kargo/mesaj bildirimi için fazlasıyla
  // hızlı, sunucuya yük değil.
  YOKLAMA_MS: 60 * 1000,
  // Oturum açılmadan yoklama anlamsız — token gelene kadar bu aralıkla bakılır
  TOKEN_BEKLEME_MS: 10 * 1000,
}
