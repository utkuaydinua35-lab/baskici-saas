# Yol haritası

Kiralama (SaaS) ve vitrin işlerinin sıradaki fazları. Her fazın sonunda
deploy; biten madde işaretlenir, tarih ve commit yazılır.

## Biten: Faz 1–2 — Kiralama altyapısı

- Planlar (sabit ücret + ciro komisyonu), modül yetkileri, kademeli gecikme
  (7 gün ek süre → salt okunur → 15. gün vitrin bakımda)
- BERNZ'e özel varsayılanların her yeni mağazadan temizlenmesi
- Dış + iç güvenlik testleri (6 saldırı sınıfı dayandı)

## Biten: Tema — "Manzara" (2026-09-27)

landscapecase.com düzeninden uyarlanmış, marka-nötr ön ayar. Tüm mağazaların
tema kütüphanesinde. Bu çalışmada eklenen ve **her temada** kullanılabilen
altyapı:

- Açılış kampanya pop-up'ı: üst etiket, çok satırlı başlık, kupon, görsel
  yükleme; masaüstünde iki sütun
- Tema geneli görünüm (Tema → Görünüm): ortalı logo + altta menü (etkin sayfa
  hap), tam yuvarlak butonlar, çerçevesiz ürün kartı, büyük ortalı bölüm
  başlıkları, "yukarı çık" düğmesi
- Bölüm başlığı üçlüsü (üst etiket / başlık / alt başlık)
- Hero: slayt üst etiketi, sola hizalı yazı + geçişli karartma, yüksek vitrin
- Galeri: 9:16 hikâye kartı, oklu + otomatik şerit, sürekli akan şerit, 12 görsel
- Koleksiyon kartları: 2'li büyük, numaralı, açıklamalı düzen; gösterilecek sayı
- Ürün bölümleri: oklu şerit düzeni + altta "Tümünü görüntüle"
- Duyuru şeridi rengi
- Koleksiyon sayfasında sayfalama (eskiden yalnız ilk 24 ürün görünüyordu)

## Sıradaki: Faz 3 — Kiralama işletimi

- [ ] Panelde plan fiyatlarını düzenleme ekranı
- [ ] Mağazaya plan atama / değiştirme
- [ ] "Havale alındı" → `active_until` uzatma
- [ ] Ödeme geçmişi (kiracı ve platform tarafı)
- [ ] Aylık ciro komisyonu hesabı ve faturalanacak tutar

## Faz 3.5 — Vitrin eksikleri (landscapecase.com incelemesinden)

Tema kopyalanırken landscape'te olup bizde olmayan, tema ayarıyla
çözülemeyen işler:

- [ ] **Ürün ek seçenekleri (fiyat farklı).** Landscape'te model seçiminden
  sonra "Vernik: Evet / Hayır" gibi ek seçenek var. Bizde yalnız marka → model
  varyantı var. Katalog, sepet, ödeme anındaki fiyat kaydı, sipariş, üretim
  ve etiket zincirinin hepsine dokunur; en büyük madde.
  > **Shopify kapanmadan önce kontrol:** BERNZ'de fiyat farklı ek seçenek
  > kullanılıyorsa bu madde Faz 3'ün önüne alınmalı.
- [ ] **Seçenek karşılaştırma penceresi.** Ürün sayfasında "farkı gör"
  düğmesi → iki görsel arasında kaydırmalı önce/sonra karşılaştırması (mat ve
  parlak). Ek seçeneklere bağlı; onunla birlikte yapılmalı.
- [ ] **Galeriye video, bağlantı ve etiket.** Landscape "fotoğraf ve video
  paylaşımları" gösteriyor. Galeri öğesi şu an yalnız görsel adresi; öğeye
  tür (görsel/video), tıklanınca gidilecek adres ve kullanıcı adı etiketi
  eklenmeli.
- [ ] **Medya kütüphanesi.** Hero, galeri, pop-up ve banner'a yüklenen her
  görsel ayrı yükleniyor; bir kez yüklenenin başka yerde tekrar seçilebilmesi.
- [ ] **Tema kütüphanesinde ekran görüntüsü.** Şablonlar şu an 3 renk
  noktasıyla tanıtılıyor; kiracı seçerken gerçek görünümü görmeli. Ayrıca
  panelde "görsel bekleyen boş bölüm" uyarısı: Manzara'nın görsel alanları
  boş gelir ve boş bölüm vitrinde hiç görünmez.
- [ ] **Sıralama seçenekleri + numaralı sayfalama.** Bizde 3 sıralama var
  (önerilen, fiyat artan/azalan); landscape'te en çok satan, en yeni,
  alfabetik de var. Sayfalama "Önceki / Sonraki", numaralı değil.
- [ ] **Tema editöründe pop-up önizlemesi.** Canlı önizlemede pop-up
  bilerek gizli; "pop-up'ı önizle" düğmesi.
- [ ] Kozmetik: akan galerideki kartlarda bulanık zeminli çerçeve.

Bilerek alınmayanlar:
- **Müzik çalar:** landscape'te de kapalı; kendiliğinden çalan ses dönüşümü
  düşürür.
- **Shopify uygulama bloğu model seçici:** bizde yerleşik marka → model
  seçici zaten var.

## Faz 4 — Kartla abonelik

- [ ] iyzico abonelik (yinelenen ödeme) ile otomatik tahsilat

## Açık altyapı / güvenlik işleri

- [ ] `/storage` doğrudan URL'lerinde kiracı izolasyonu
- [ ] Gerçek ödeme akışı uçtan uca testi (sağlayıcı anahtarlarıyla)
- [ ] nginx `protocol options redefined` uyarısı (http2 tutarsızlığı)
- [ ] `storefront/middleware.ts` → `proxy.ts` (Next 16 kullanımdan kaldırdı)
