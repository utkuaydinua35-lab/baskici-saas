"""Vitrin ürün araması (services/arama.py) — Türkçe harf, yazım hatası, sıralama.

Canlıda bulunan sorunlar: "kilif" 18 / "kılıf" 595 sonuç, "cicek" 0, "ihpone"
0, her arama 1-3 sn. İlk yeni sürümde de kelime İÇİ eşleşme "sari"yi
"taSARIm" yüzünden 610 ürüne yaydı — burada kilitlenir.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import arama  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


M = "iPhone 15 | iPhone 15 Pro Max | Galaxy S24"
URUNLER = [
    ("u1", '"Sarı Kırmızı Temalı" Tasarım Telefon Kılıfı', "renkli", M),
    ("u2", '"Güneş Çiçek Büyüsü" Tasarım Telefon Kılıfı', "çiçek doğa", M),
    ("u3", '"Ferrari Ascend" Tasarım Telefon Kılıfı', "f1 araba", M),
    ("u4", '"Project Rock" Tasarım Telefon Kılıfı', "", M),
    ("u5", '"Mistik Kalp Göz" Tasarım Telefon Kılıfı', "anatomik kalp", "iPhone 16"),
    ("u6", "Lens Koruyucu (iPhone)", "aksesuar", ""),
]
dizin = [arama._Urun(i, arama.normalize(a), arama.normalize(e), arama.normalize(m)) for i, a, e, m in URUNLER]
arama._dizin = lambda db, store: dizin
ara = lambda q: arama.ara(None, None, q)  # noqa: E731

print("\n── Normalleştirme ──")
es("Türkçe harfler + büyük İ/I", "iphone 15 kilif cicek sari", arama.normalize("İPHONE 15 Kılıf ÇİÇEK SARI"))

print("\n── Türkçe harfsiz yazım ──")
es("kilif = kılıf", ara("kılıf"), ara("kilif"))
es("cicek = çiçek", ["u2"], ara("cicek"))
es("kirmizi = KIRMIZI", ["u1"], ara("kirmizi"))

print("\n── Kelime başından eşleşme ──")
es("sari 'Tasarım'a takılmaz", ["u1"], ara("sari"))
es("yazarken yarım kelime (son kelime)", ["u5"], ara("kal"))
es("kısa ara kelime tam eşleşmeli: 'pro' Project'i öne çıkarmaz", "u1", ara("15 pro max")[0])

print("\n── Yazım hatası ──")
es("ferari → Ferrari ilk sırada", "u3", ara("ferari")[0])
es("ihpone → iPhone adı geçen öne", "u6", ara("ihpone")[0])
es("anlamsız kelime → sonuç yok", [], ara("xyzqw"))

print("\n── Sıralama ve birleşik arama ──")
es("ad > etiket > model", ["u5"], ara("kalp")[:1])
es("iphone 15 kalp → hepsi tutmalı", ["u5"], ara("iphone 16 kalp"))
es("f1 etiketiyle bulunur", ["u3"], ara("f1"))
es("hiçbiri hepsini tutmazsa en az biri tutanlar (boş sayfa yok)", ["u3"], ara("ferrari zzzzq"))

print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
