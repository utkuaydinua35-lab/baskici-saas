"""Kargo etiketi ZPL'e çevrilirken ne oluyor — adım adım süre + font dökümü.

İki soruyu cevaplar:
  1) Yazılar neden serif basılıyor? (SVG hangi fontu istiyor, metin mi yol mu)
  2) "Kargoya ver"den sonraki bekleme nereden geliyor? (her adımın süresi)

Kullanım (VPS, baskici kullanıcısı):
    cd ~/baskici-saas/backend && .venv/bin/python scripts/etiket_tani.py [SIPARIS_NO]
"""
from __future__ import annotations

import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Order  # noqa: E402
from app.services import basit_kargo  # noqa: E402
from app.services import zpl_label as Z  # noqa: E402


def main() -> None:
    no = sys.argv[1] if len(sys.argv) > 1 else None
    db = SessionLocal()
    try:
        q = select(Order).where(Order.kargo_info.isnot(None)).order_by(desc(Order.created_at))
        if no:
            q = select(Order).where(Order.order_number == no)
        o = db.scalar(q)
        if not o or not (o.kargo_info or {}).get("id"):
            print("Kargo etiketi olan sipariş bulunamadı.")
            return
        print(f"Sipariş #{o.order_number}\n")

        t = time.time()
        svg = basit_kargo.get_label_svg(o.kargo_info["id"])
        t_svg = time.time() - t
        if not svg:
            print("Etiket SVG alınamadı.")
            return
        print(f"1) Basit Kargo'dan SVG çekme : {t_svg:6.2f} sn  ({len(svg)/1024:.0f} KB)")

        # ── İçerik dökümü ──
        metin = len(re.findall(r"<text\b", svg, re.I))
        yol = len(re.findall(r"<path\b", svg, re.I))
        gorsel = len(re.findall(r"<image\b", svg, re.I))
        fontlar = Counter(
            m.group(2).strip()
            for m in re.finditer(r'font-family\s*=\s*(["\'])(.*?)\1', svg, re.I))
        fontlar.update(
            m.group(1).strip()
            for m in re.finditer(r'font-family\s*:\s*([^;"\'}]+)', svg, re.I))
        print(f"\n   <text> {metin} · <path> {yol} · <image> {gorsel}")
        if fontlar:
            print("   istenen fontlar:")
            for f, n in fontlar.most_common(8):
                print(f"     {n:>3}x  {f}")
        else:
            print("   ⚠ SVG'de font-family YOK.")
            if metin == 0:
                print("     <text> de yok → yazılar YOLA (path) çevrilmiş.")
                print("     Bu durumda font değiştirilemez; görünüm SVG'nin kendisinden gelir.")
            if gorsel:
                print("     <image> var → etiketin bir kısmı hazır GÖRSEL olabilir.")

        # ── Font değişimi GERÇEKTEN çizime yansıyor mu ──
        yeni = Z.fontlari_sadelestir(svg)
        print(f"\n2) Font değişimi metinde: {'UYGULANDI' if yeni != svg else 'DEĞİŞİKLİK YOK'}")

        import fitz as _f

        def _izi(kaynak):
            """Çizilen koyu piksel sayısı — font değişirse bu sayı DEĞİŞİR."""
            d = _f.open(stream=kaynak.encode("utf-8"), filetype="svg")
            pix = d[0].get_pixmap(matrix=_f.Matrix(2, 2), alpha=False)
            n = sum(1 for i in range(0, len(pix.samples), pix.n) if pix.samples[i] < 128)
            d.close()
            return n

        a, b = _izi(svg), _izi(yeni)
        print(f"   çizimdeki koyu piksel: {a} -> {b}"
              f"   {'ÇİZİM DEĞİŞTİ ✓' if a != b else '⚠ ÇİZİM AYNI — font çizime yansımıyor'}")

        # İlk üç <text> ögesi ham haliyle — neyin değiştiği gözle görülsün
        print("\n   ── SVG'deki ilk <text> ögeleri (ham) ──")
        for i, m in enumerate(re.finditer(r"<text\b[^>]*>", svg, re.I)):
            if i >= 3:
                break
            print(f"     once : {m.group(0)[:150]}")
        for i, m in enumerate(re.finditer(r"<text\b[^>]*>", yeni, re.I)):
            if i >= 3:
                break
            print(f"     sonra: {m.group(0)[:150]}")

        # <image> içinde metin olabilir — o zaman font değiştirilemez
        for m in re.finditer(r"<image\b[^>]*>", svg, re.I):
            b64 = re.search(r'(?:xlink:)?href\s*=\s*"data:image/([a-z+]+);base64,', m.group(0), re.I)
            wh = re.findall(r'\b(width|height)\s*=\s*"([^"]+)"', m.group(0))
            print(f"\n   <image> tur={b64.group(1) if b64 else 'harici'} {dict(wh)}")

        # ── ZPL üretimi ──
        t = time.time()
        zpl = Z.svg_to_zpl(svg, w_mm=80, h_mm=100)
        t_zpl = time.time() - t
        print(f"3) ZPL üretimi (80x100 mm)   : {t_zpl:6.2f} sn  ({len(zpl)/1024:.0f} KB)")

        print(f"\n   toplam sunucu tarafı: {t_svg + t_zpl:.2f} sn")
        print("   (Panelin beklediği süre buna + Basit Kargo gönderi oluşturma +")
        print("    Shopify fulfillment + ZPL'in yazıcıya gitmesi ekleniyor.)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
