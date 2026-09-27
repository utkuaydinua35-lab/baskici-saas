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

## Biten: Faz 3 — Kiralama işletimi (2026-09-27)

- [x] Platform → Planlar: aylık ücret, komisyon oranı, modüller, satışta mı;
  yeni plan ekleme. Sahip planının modülleri kilitli, mağaza modülü zorunlu.
- [x] Kiracıya plan atama (oluştur/düzenle formunda plan seçici; eskiden
  serbest metindi ve erişimi belirleyen `plan_id` hiçbir ekrandan atanamıyordu)
- [x] "Ödeme alındı": tutar o anın plan fiyatıyla dondurulur, abonelik uzar;
  1/2/3/6/12 ay peşin. Önizlemedeki tutar değiştiyse kayıt reddedilir (409).
- [x] Yanlış girilen ödemeyi geri alma: yalnız en son ödeme; bitiş eski
  tarihine döner.
- [x] Ödeme geçmişi: platformda kiracı başına, mağaza panelinde Abonelik sayfası
- [x] Tahsilat listesi: her kiracının şimdi ödeyeceği tutar, en acil üstte
- [x] Havale bilgileri (IBAN, alıcı, banka): kiracının Abonelik sayfasında,
  açıklamaya yazılacak mağaza koduyla birlikte

Fatura düzeni (Shopify faturasıyla aynı): sabit ücret peşin, komisyon geçen
dönemin satışından. Komisyon matrahı yalnız **vitrin** satışları, sipariş
toplamı (indirim düşülmüş, KDV + kargo dahil). Bilinçli fark: iptal ve tam
iade düşülür, çünkü panel ciroyu da böyle sayıyor. Vitrini kapanmış kiracının
yeni dönemi bugünden başlar; sınırsız plandan ücretliye geçen kiracının geçmiş
satışından komisyon alınmaz. Kurallar: `backend/app/services/abonelik.py`.

Faz 3 sonrası (2026-09-27 tamamlandı):
- [x] Kiracıya e-posta hatırlatması — bitişe 5 gün kala, ek süre, salt okunur,
  vitrin kapandı; her aşama her dönem bir kez, başarısız gönderim ertesi gün
  yeniden denenir (her sabah 09:30).
- [x] Ödeme kaydında fatura numarası — ödemede ya da sonradan girilir,
  kiracı ödeme geçmişinde görür.

## Biten: Faz 3.5 — Vitrin eksikleri (landscapecase.com incelemesinden, 2026-09-27)

- [x] **Ek seçeneklere fiyat farkı** — seçenek başına ("Parlak +50 TL") ve
  doldurulursa ücretli alan ("İsim +25 TL"). Tutar ödemede sunucuda ürün
  tanımından hesaplanır. Yolda düzeltildi: aynı model farklı seçenekle iki
  satır olunca ödeme tümden reddediliyordu.
  > BERNZ kontrol edildi (Shopify'daki son 40 sipariş): ek alanlar fiyat
  > farksız ve hepsinin bizde karşılığı var; Shopify çıkışını engellemiyordu.
- [x] **"Farkı gör" karşılaştırma penceresi** — seçeneğe görsel; iki görsel
  üst üste, sürüklenen ayırıcı (klavye/dokunma/ekran okuyucu).
- [x] **Galeriye video, bağlantı, etiket** — video yalnız ekrandayken oynar.
- [x] **Medya kütüphanesi** — yüklenen görsel/video her alanda yeniden seçilir.
  Silme bilinçli olarak yok (kullanılan görseli kırmamak için).
- [x] **Tema kütüphanesinde kroki** + editörde **"görünmüyor: görsel bekliyor"**
  uyarısı (kurallar vitrin bileşenleriyle birebir).
- [x] **Sıralama** (en çok satan, en yeni, A-Z/Z-A Türkçe) + **numaralı sayfalama**.
- [x] **Editörde pop-up önizlemesi** ("👁 Önizlemede göster").
- Hız (yolda): tema görsellerine (hero, galeri, koleksiyon, banner) duyarlı
  boyutlar + retina için orijinal; aynı saniyede yüklenen iki görselin
  birbirinin üzerine yazılması düzeltildi.

Bilerek alınmayanlar:
- **Akan galeride bulanık zeminli çerçeve:** hareket eden şeritte bulanıklık
  filtresi telefonda takılma riski taşıyor (bkz. menü akıcılığı dersi);
  kazancı kozmetik, riski "akıcı site" hedefine ters.
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
