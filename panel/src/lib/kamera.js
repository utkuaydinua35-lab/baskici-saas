/**
 * Native kamera / galeri — yalnız uygulama kabuğunda.
 *
 * NEDEN VAR: Apple'ın 4.2 ("minimum functionality") kuralı, siteyi olduğu
 * gibi gösteren kabukları reddediyor. Ürün fotoğrafını doğrudan telefonun
 * kamerasıyla çekmek, uygulamanın web'de yapılamayanı yaptığı somut bir
 * yetenek — hem incelemede savunulabilir hem de satıcının gerçekten işine
 * yarıyor (ürünü çek, anında yayına al).
 *
 * TASARIM: bu modül File nesnesi döndürür, yani mevcut yükleme kodu HİÇ
 * değişmez — <input type="file"> ile aynı şeyi verir. Web'de `nativeMi()`
 * false döner ve hiçbir şey görünmez; tarayıcıda eklenti yüklenmeye bile
 * çalışılmaz (dinamik import).
 */
let _native = null

/** Uygulama kabuğunda mıyız? (tarayıcıda her zaman false) */
export function nativeMi() {
  if (_native !== null) return _native
  try {
    _native = !!(window.Capacitor && window.Capacitor.isNativePlatform
                 && window.Capacitor.isNativePlatform())
  } catch {
    _native = false
  }
  return _native
}

/**
 * Kamerayı ya da galeriyi aç, seçilen görselleri File olarak döndür.
 *
 * kaynak: 'kamera' | 'galeri'
 * Kullanıcı vazgeçerse BOŞ dizi döner (hata değil — iptal normal bir sonuç).
 */
export async function gorselSec(kaynak = 'kamera') {
  if (!nativeMi()) return []
  // Dinamik import: web derlemesinde eklenti paketi ana pakete girmesin.
  const { Camera, CameraResultType, CameraSource } = await import('@capacitor/camera')

  try {
    if (kaynak === 'galeri') {
      // Galeriden ÇOKLU seçim — satıcı bir üründe birden çok açı yüklüyor.
      const { photos } = await Camera.pickImages({ quality: 90 })
      return (await Promise.all((photos || []).map(_dosyaya))).filter(Boolean)
    }
    const foto = await Camera.getPhoto({
      quality: 90,
      allowEditing: false,
      resultType: CameraResultType.Uri,
      source: CameraSource.Camera,
    })
    const f = await _dosyaya(foto)
    return f ? [f] : []
  } catch (e) {
    // Eklenti iptalde de HATA fırlatıyor; iptali sessizce boş dizi say.
    const m = String(e?.message || e).toLowerCase()
    if (m.includes('cancel') || m.includes('iptal')) return []
    throw e
  }
}

/** Capacitor foto sonucunu (webPath) File'a çevirir. */
async function _dosyaya(foto) {
  const yol = foto?.webPath || foto?.path
  if (!yol) return null
  const blob = await (await fetch(yol)).blob()
  const uzanti = (foto.format || 'jpeg').replace('jpg', 'jpeg')
  return new File([blob], `foto-${Date.now()}.${uzanti === 'jpeg' ? 'jpg' : uzanti}`,
                  { type: blob.type || `image/${uzanti}` })
}
