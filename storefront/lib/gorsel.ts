// Ürün görselleri için srcset üreteci.
//
// NEDEN: vitrin eskiden next/image kullanıyordu; o, görseli İLK İSTEKTE
// optimize ediyor. Belleği kısıtlı VPS'te bu 2+ saniye sürüyor ve eşzamanlı
// ilk ziyaretlerde zaman aşımına düşüyordu — "görseller ilk girişte gelmiyor"
// sorunu buydu. Artık görsel varyantları YÜKLEME ANINDA üretiliyor
// (backend/services/images.py) ve statik sunuluyor; burada yalnız doğru
// dosya adlarını birleştiriyoruz. İstek başına CPU sıfır.
//
// Dosya düzeni: .../{id}.jpg (ana, ≤2048) + .../{id}-400.jpg, -800, -1280.

const GENISLIKLER = [400, 800, 1280];

/** "/storage/.../abc.jpg" → { srcSet, src }. Uzantı korunur (png alpha). */
export function urunGorsel(url: string | null | undefined): { src: string; srcSet: string } {
  if (!url) return { src: "", srcSet: "" };
  const nokta = url.lastIndexOf(".");
  if (nokta < 0) return { src: url, srcSet: "" };
  const govde = url.slice(0, nokta);
  const ext = url.slice(nokta); // ".jpg" | ".png"
  const srcSet = GENISLIKLER.map((w) => `${govde}-${w}${ext} ${w}w`).join(", ");
  return { src: url, srcSet };
}
