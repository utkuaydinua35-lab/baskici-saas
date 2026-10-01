# Toplu mockup (Photoshop)

`toplu-mockup.jsx` — bir klasördeki tasarımları mockup PSD'lerine oturtur ve
katalog görseli olarak kaydeder. Amaç: **ürün büyük, zemin sakin, filigran yok**
(vitrin ızgarası ve pazar yeri kapak görseli için).

## Çalıştırma

1. Photoshop → **Dosya → Komut Dosyaları → Gözat…** → `toplu-mockup.jsx`
2. Sırayla üç klasör sorulur: **tasarımlar**, **şablonlar (.psd)**, **çıktı**.
   (Her seferinde sormasın istersen dosyanın başındaki `AYAR` bloğundaki
   `TASARIM_KLASORU / SABLON_KLASORU / CIKTI_KLASORU` alanlarına yolu yaz.)
3. Biter bitmez özet kutusu çıkar; ayrıntı çıktı klasöründeki
   `toplu-mockup-gunluk.txt` dosyasında.

> **Yeniden çalıştırırken:** klasörde aynı adlı çıktılar varsa script
> *"Bu klasörde N görsel ZATEN VAR — üzerine yazılsın mı?"* diye sorar.
> Ayar değiştirip görselleri yenilemek istiyorsan **Evet** de. Hayır dersen
> yalnız eksikler üretilir (yarıda kalan işi sürdürmek için).

Her **tasarım × şablon** için bir görsel üretir. Tek şablon varsa çıktı adı
tasarım adıdır; birden fazla şablon varsa sonuna şablon adı eklenir.

## Ne yapıyor

1. Şablondaki smart object'i (`Design Here`, `Your Work Here`, `design`, `w1`, `bc`)
   tasarımla değiştirir — kılıfın maskesi, kamera oyuğu, ışık/gölge şablondan gelir.
2. Adı filigran/logo/`Remove This` içeren katmanları **gizler**.
3. Kadraj: varsayılan `KADRAJ: "sablon"` — **şablonun kendi kadrajı ve ölçüsü**
   korunur (ör. 4000×3000), kırpma/ölçekleme yapılmaz. `"urun"` seçersen ürüne
   kırpar ve kılıf kadrajın `ORAN` kadarını (%85) kaplar.
4. Zemini **#F6F7F9** düz renge çevirir (beyaz ve şeffaf kılıflar saf beyazda
   kayboluyor, bu tonda kenarları belli oluyor).
5. **PNG** olarak kaydeder; `CIKTI_PX: 0` olduğu için ham çözünürlük korunur
   (küçültmek kılıfı piksel olarak da küçültüyordu).
6. Şablonu **kaydetmeden** kapatır — şablon dosyası hiç değişmez.

## Sık ayarlanan şeyler (`AYAR` bloğu)

| Ayar | Ne işe yarar |
|---|---|
| `KADRAJ` | `"sablon"` = şablonun kendi kadrajı/ölçüsü (4000×3000). `"urun"` = kılıfa kırp, kadrajı `ORAN`'a göre kur |
| `ORAN` | (`KADRAJ:"urun"`) Ürünün kadrajı doldurma oranı. 0.85 → rahat boşluk; 0.92 → daha "dolu" kart |
| `KARE` | (`KADRAJ:"urun"`) `false` yaparsan kırpılan alanın oranı korunur |
| `ZEMIN_RENK` | `""` verirsen zemin rengi hiç eklenmez (atmosferli çekimler için) |
| `ZEMINI_GIZLE` | Şablonun kendi zemin katmanı gizlensin mi. **Varsayılan kapalı** — aşağıdaki tuzağa bak |
| `PSB_DIGER_KATMANLARI_GIZLE` | Smart object'in İÇİNDEKİ eski katmanlar gizlensin mi. Varsayılan kapalı |
| `CIKTI_PX` | Uzun kenar. **0 = hiç küçültme** (ham çözünürlük). 3000 gibi bir değer verirsen oraya ölçeklenir |
| `FORMAT` / `JPG_KALITE` | Varsayılan `png` (kayıpsız). `jpg` seçersen `JPG_KALITE` (80) geçerli olur |
| `YERLESIM` | `cover` = baskı kılıfı doldurur (taşan kırpılır), `contain` = tamamı sığar |
| `VARSA_ATLA` | `true` iken aynı adlı çıktı varsa atlanır — yarıda kalan işi kaldığı yerden sürdürür |
| `GIZLE` | Gizlenecek katman adları (parça eşleşme, küçük/büyük harf farketmez) |

### Kılıf küçük kalıyorsa

İki ayrı sebebi var, karıştırma:
- **Piksel olarak küçük** → `CIKTI_PX` küçültüyordur. 0 yap (ham çözünürlük).
- **Kadrajda küçük (etrafı çok boşluk)** → şablonun kendi kadrajı geniştir.
  `KADRAJ: "urun"` + `ORAN: 0.9` ile kılıf kadrajı doldurur; `CIKTI_PX: 0`
  olduğu için çözünürlük yine düşmez.

## Tuzaklar

- **Kodu düzenlerken noktalı virgülleri silme.** ExtendScript'in otomatik
  noktalı virgül eklemesi güvenilmez: `continue` / `return` gibi satırlarda
  "Error 25: Expected: ;" verip duruyor. Her deyimin sonunda `;` olmalı.
- **Dosya UTF-8 BOM ile kaydedilmeli** (öyle duruyor). BOM silinirse Türkçe
  karakterler uyarı kutularında ve günlükte bozuk çıkar.

- **"Background" adlı katman çoğu zaman ARKA PLAN DEĞİL, KILIFIN KENDİSİDİR.**
  `arkası boş mockup.psd` dosyasında kılıfın fotoğrafı (kamera modülü, parlama,
  gölge) `Background` katmanında duruyor ve `Design Here` smart object'i
  **Multiply** modunda onun üstüne biniyor; gerçekçilik oradan geliyor. Bu katman
  gizlenirse çıktı düz bir silüete dönüşür, kamera deliği bembeyaz kalır.
  Bu yüzden `ZEMINI_GIZLE` varsayılan olarak **kapalı**. Zemin rengi zaten en
  alta eklenen katmandan geliyor; şablonun arkası şeffafsa başka bir şey gerekmez.
  Yalnız gerçekten fotoğraf zeminli şablonlarda `true` yap.
- **Baskı dosyasındaki kamera boşluğu beyaz kalıyorsa** sebep yine budur: beyaz
  alan Multiply ile altındaki kamera fotoğrafını göstermeli; kılıf katmanı
  gizliyse gösterecek bir şey kalmıyor.
- **PDF tasarım desteklenmez** — Photoshop PDF açarken diyalog istiyor, toplu iş
  durur. Önce PNG'ye çevir (`sips`/Önizleme ya da panelin tasarım çıktısı).
- **Şablondaki smart object adı farklıysa** script "Tasarım katmanı bulunamadı"
  der; adı `TASARIM_KATMANI` listesine ekle.
- **Şeffaf kılıf**: smart object içindeki eski içerik gizlenir, yani tasarımın
  şeffaf yerlerinden kılıfın altı görünür — istenen davranış budur.
- Çalışırken Photoshop'ta başka belge açık kalmasın; script etkin belgeyle çalışır.

## Elimizdeki şablon

`etrafı boş mockup.psd` (4000×3000) bu script'in varsayılanlarıyla uyumlu:
smart object `Design Here`, ürün grubu `Mockup Here`, gizlenecek `Remove This`.
