# Tasarım Stüdyosu yazı tipleri — lisans bilgisi

Bu klasördeki tüm `.ttf` dosyaları ticari kullanıma açık lisanslarla dağıtılır
ve Google Fonts arşivinden (github.com/google/fonts) alınmıştır. Aynı dosyalar
`backend/app/fonts/` altında da bulunur; baskıya giden dosya ekrandakiyle
birebir aynı yazı tipiyle üretilsin diye.

## SIL Open Font License 1.1 (OFL)
Poppins, Montserrat, Playfair Display, Bebas Neue, Oswald, Anton, Staatliches, Russo One, Alumni Sans Collegiate One,
UnifrakturCook, Pirata One, Bangers, Bungee, Alfa Slab One, Creepster,
Dancing Script, Caveat, Great Vibes, Pacifico, Lobster, Monoton, Righteous.

Lisans metni: https://openfontlicense.org — yazı tipleri gömülü olarak
kullanılabilir, ürün üzerinde basılabilir; tek koşul yazı tipi dosyalarının
kendisinin satılmaması ve isim değiştirilerek dağıtılmamasıdır.

## Apache License 2.0
Roboto Mono, Permanent Marker, Rock Salt, Special Elite.

Lisans metni: https://www.apache.org/licenses/LICENSE-2.0

## Türkçe karakter notu
Permanent Marker, Rock Salt, Creepster ve UnifrakturCook fontlarında
ğ Ğ ş Ş İ (ve UnifrakturCook'ta ı) harflerinin glyph'i yoktur. Editör bu
harfler yazıldığında müşteriyi uyarır (`components/studio/fonts.ts` →
`trUyarisi`), çünkü baskıda boş/yanlış karakter çıkar.
