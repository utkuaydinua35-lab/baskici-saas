#!/usr/bin/env python3
"""PWA ikonlarını üretir (public/pwa-*.png, apple-touch-icon.png).

Neden script: ana ekrandaki ikon favicon.svg ile AYNI çizim olmalı, ama
iOS/Android manifest PNG ister ve bu makinede SVG rasterleyici yok
(cairosvg/rsvg/inkscape kurulu değil). Bu yüzden aynı geometri Pillow ile
yeniden çiziliyor — ölçüler favicon.svg'nin 32'lik viewBox'ından birebir
alındı, tek fark ölçek katsayısı.

Çalıştırma (yalnız ikon değişirse):
    backend/.venv/bin/python panel/scripts/pwa-ikon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

KOK = Path(__file__).resolve().parent.parent / "public"

# Vision UI marka gradyanı (index.css --grad-marka ile aynı)
BAS = (0, 117, 255)      # #0075ff
SON = (33, 212, 253)     # #21d4fd
KOYU = (0, 96, 210)      # çanta üstündeki yüz çizgileri


def _gradyan(boy: int) -> Image.Image:
    """Sol üstten sağ alta çapraz gradyan."""
    g = Image.new("RGB", (boy, boy))
    p = g.load()
    for y in range(boy):
        for x in range(boy):
            t = (x + y) / (2 * (boy - 1))
            p[x, y] = tuple(round(BAS[i] + (SON[i] - BAS[i]) * t) for i in range(3))
    return g


def ikon(boy: int) -> Image.Image:
    """Kenardan kenara DOLU, saydamlığı OLMAYAN kare ikon.

    Köşeleri bilerek yuvarlatmıyoruz: iOS ve Android ikona KENDİ maskesini
    uygular. Saydam köşeli bir PNG verildiğinde iOS köşeleri siyaha boyar,
    Android'in maskable ikonu ise kırpılmış görünür. Doğrusu tam kare vermek;
    glif zaten güvenli alanın içinde (genişliğin ~%34'ü) kalıyor.
    """
    # 4x çiz, sonra küçült — kenarlar yumuşasın (Pillow'da anti-aliasing yok)
    S = boy * 4
    k = S / 32.0                                  # favicon.svg viewBox ölçeği

    im = _gradyan(S).convert("RGBA")
    d = ImageDraw.Draw(im)
    beyaz = (255, 255, 255, 245)

    # Çanta sapı: (16, 10.6) merkezli r=3.2 yarım çember + iki dik parça
    kal = max(1, int(1.8 * k))
    d.arc([(16 - 3.2) * k, (10.6 - 3.2) * k, (16 + 3.2) * k, (10.6 + 3.2) * k],
          start=180, end=360, fill=beyaz, width=kal)
    d.line([12.8 * k, 10.6 * k, 12.8 * k, 12 * k], fill=beyaz, width=kal)
    d.line([19.2 * k, 10.6 * k, 19.2 * k, 12 * k], fill=beyaz, width=kal)

    # Çanta gövdesi: üstü geniş, altı hafif daralan gövde
    d.polygon([(10.5 * k, 12 * k), (21.5 * k, 12 * k),
               (20.4 * k, 24 * k), (11.6 * k, 24 * k)], fill=beyaz)

    # Yüz: iki göz + gülümseme
    r = 1 * k
    for gx in (13.6, 18.4):
        d.ellipse([gx * k - r, 15 * k - r, gx * k + r, 15 * k + r], fill=KOYU)
    d.arc([(16 - 2.4) * k, (15 - 2.4) * k, (16 + 2.4) * k, (15 + 2.4) * k],
          start=0, end=180, fill=KOYU, width=max(1, int(1.2 * k)))

    # Saydamlık kalmasın (iOS siyah köşe basar)
    return im.convert("RGB").resize((boy, boy), Image.LANCZOS)


if __name__ == "__main__":
    for ad, boy in (("pwa-192.png", 192), ("pwa-512.png", 512),
                    ("apple-touch-icon.png", 180)):
        yol = KOK / ad
        ikon(boy).save(yol)
        print(f"{ad}  {boy}x{boy}  {yol.stat().st_size // 1024} KB")
