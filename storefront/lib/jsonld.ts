/**
 * JSON-LD'yi <script> içine GÜVENLE yazmak için.
 *
 * NEDEN VAR: `JSON.stringify` `<` ve `/` karakterlerini kaçırmaz. Veride
 * `</script>` geçerse tarayıcı script etiketini ORADA kapatır ve sonrasındaki
 * her şeyi HTML olarak işler:
 *
 *   <script type="application/ld+json">{"name":"Kılıf </script><script>…
 *
 * Ürün başlığı, blog başlığı, marka adı ve SSS metinleri mağaza sahibinden
 * geliyor ve (açıklamanın aksine) sanitize EDİLMİYOR — yalnız uzunluk sınırı
 * var. Yani mağaza sahibi kendi vitrininin ziyaretçilerinde rastgele JS
 * çalıştırabiliyordu; vitrin `*.bernzcompany.com` alt alanında da yayında
 * olduğu için bu platformun alan adı altında barındırılan bir XSS demekti.
 *
 * Çözüm standart: `<` karakterini `<` olarak kaçır. JSON içinde bu geçerli
 * bir kaçış — okuyucu (Google) aynı metni görür, tarayıcı ise etiket görmez.
 * U+2028/U+2029 de kaçırılır: JSON'da yasal ama JavaScript'te satır sonu
 * sayıldıkları için ayrıştırmayı bozabilirler.
 */
export function jsonLdScript(veri: unknown): string {
  return JSON.stringify(veri)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    // U+2028/U+2029: kaynak dosyada HAM yazılamaz — JavaScript onları satır
    // sonu sayar ve bu dosyanın kendisini böler (ilk denemede öyle oldu).
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}
