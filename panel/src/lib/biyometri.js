/**
 * Face ID / Touch ID — yalnız uygulama kabuğunda.
 *
 * NEDEN BU, GEÇİŞ ANAHTARI DEĞİL: WebAuthn (passkey) sayfanın origin'inin
 * RP ID ile aynı alan adında ve https olmasını şart koşuyor. Uygulamada sayfa
 * `capacitor://localhost` üzerinden açıldığı için tarayıcı isteği daha
 * sunucuya gitmeden reddediyor. Passkey'i uygulamada açmanın tek yolu
 * Associated Domains + iOS'un yerel ASAuthorization API'si; o da ÜCRETLİ Apple
 * Developer takım kimliği istiyor (ücretsiz kişisel takımlar bu yetkiyi
 * alamıyor). Web'de passkey aynen çalışmaya devam ediyor.
 *
 * NE YAPIYOR: parolayla bir kez girildikten sonra oturum hatırlanıyor;
 * sonraki açılışlarda parola yerine parmak izi/yüz soruluyor. Kilit, telefonu
 * eline geçiren birinin açık oturumu kullanmasını engeller. Token uygulamanın
 * kendi kum havuzundaki localStorage'ta durur — başka uygulamalar okuyamaz.
 *
 * Web'de bu modülün tamamı devre dışı: `nativeMi()` false döner ve eklenti
 * import bile edilmez (dinamik import).
 */
import { nativeMi } from './kamera'

/** Cihazda kayıtlı bir parmak izi/yüz var mı? */
export async function biyometriVarMi() {
  if (!nativeMi()) return false
  try {
    const { BiometricAuth } = await import('@aparajita/capacitor-biometric-auth')
    const d = await BiometricAuth.checkBiometry()
    return !!(d?.isAvailable && d?.biometryType)
  } catch {
    // Eklenti yoksa/desteklenmiyorsa kilit hiç devreye girmesin — kullanıcıyı
    // dışarıda bırakmaktansa parolayla devam etmek doğrusu.
    return false
  }
}

/**
 * Kilidi açmayı dener.
 * true  → doğrulandı
 * false → kullanıcı vazgeçti ya da doğrulanamadı (parolaya düşülür)
 */
export async function biyometriDogrula() {
  if (!nativeMi()) return false
  try {
    const { BiometricAuth } = await import('@aparajita/capacitor-biometric-auth')
    await BiometricAuth.authenticate({
      reason: 'Panelini açmak için kimliğini doğrula',
      cancelTitle: 'Vazgeç',
      allowDeviceCredential: true,      // Face ID başarısızsa telefon şifresi
      iosFallbackTitle: 'Telefon şifresini kullan',
    })
    return true
  } catch {
    return false
  }
}
