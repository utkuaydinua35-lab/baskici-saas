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

Her **tasarım × şablon** için bir görsel üretir. Tek şablon varsa çıktı adı
tasarım adıdır; birden fazla şablon varsa sonuna şablon adı eklenir.

## Ne yapıyor

1. Şablondaki smart object'i (`Design Here`, `Your Work Here`, `design`, `w1`, `bc`)
   tasarımla değiştirir — kılıfın maskesi, kamera oyuğu, ışık/gölge şablondan gelir.
2. Adı filigran/logo/`Remove This` içeren katmanları **gizler**.
3. Ürünü kadraja oturtur: ürün sınırına kırpar, sonra kadrajı **kare** yapar ve
   ürün kadrajın **%85'ini** kaplar (`ORAN`).
4. Zemini **#F6F7F9** düz renge çevirir (beyaz ve şeffaf kılıflar saf beyazda
   kayboluyor, bu tonda kenarları belli oluyor).
5. Uzun kenar **2000 px**, Web için kaydet **JPG kalite 80** olarak yazar.
6. Şablonu **kaydetmeden** kapatır — şablon dosyası hiç değişmez.

## Sık ayarlanan şeyler (`AYAR` bloğu)

| Ayar | Ne işe yarar |
|---|---|
| `ORAN` | Ürünün kadrajı doldurma oranı. 0.85 → kenarlarda rahat boşluk; 0.92 → daha "dolu" kart |
| `KARE` | `false` yaparsan şablonun en-boy oranı korunur (kare pazar yeri için önerilir) |
| `ZEMIN_RENK` | `""` verirsen şablonun kendi zeminine dokunulmaz (atmosferli çekimler için) |
| `CIKTI_PX` | Uzun kenar. Vitrin için 2000 yeter; Trendyol/HB için de uygundur |
| `FORMAT` / `JPG_KALITE` | `"png"` şeffaflık korur ama dosya büyür. Katalog için `jpg`/80 |
| `YERLESIM` | `cover` = baskı kılıfı doldurur (taşan kırpılır), `contain` = tamamı sığar |
| `VARSA_ATLA` | `true` iken aynı adlı çıktı varsa atlanır — yarıda kalan işi kaldığı yerden sürdürür |
| `GIZLE` | Gizlenecek katman adları (parça eşleşme, küçük/büyük harf farketmez) |

## Tuzaklar

- **Kodu düzenlerken noktalı virgülleri silme.** ExtendScript'in otomatik
  noktalı virgül eklemesi güvenilmez: `continue` / `return` gibi satırlarda
  "Error 25: Expected: ;" verip duruyor. Her deyimin sonunda `;` olmalı.
- **Dosya UTF-8 BOM ile kaydedilmeli** (öyle duruyor). BOM silinirse Türkçe
  karakterler uyarı kutularında ve günlükte bozuk çıkar.

- **Gölge zemin katmanının içindeyse**: `ZEMIN_RENK` verince şablonun kendi zemini
  gizlenir, gölge de gider. O şablonlarda `ZEMIN_RENK: ""` bırak ya da
  `ZEMINI_GIZLE: false` yap (o zaman renk değişmez).
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
