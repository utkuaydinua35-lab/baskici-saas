"""Ürün kapak görseli — şablonun tasarımını kılıf görseline giydirir.

Hazır forma ürününün vitrindeki fotoğrafı elle hazırlanmasın diye: şablonun
başlangıç görünümü (ya da verilen alan değerleri) BASKIYI ÜRETEN kodla çizilir,
kılıf şablonunun baskı alanına oturtulur, kamera adası üstüne geri konur.
Stüdyodaki önizlemeyle (storefront/components/studio/preview.ts) aynı sıra:
kılıf zemin → tasarım → kesikler.
"""
from __future__ import annotations

import io

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.services import kisitli_sablon
from app.services import storage as storage_svc
from app.services.design_render import _tuval_ciz

KENAR = 1200          # kare çıktı (vitrin ürün kartları kare)
ZEMIN = (244, 244, 245)
DOLGU = 0.07          # kılıfın çevresindeki boşluk (kenar oranı)


def _yuvarlak_maske(w: int, h: int, yaricap_oran: float) -> Image.Image:
    # 3× büyük çizip küçült: kenar tırtıksız
    k = 3
    m = Image.new("L", (w * k, h * k), 0)
    r = int(min(w, h) * k * max(0.0, yaricap_oran))
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=r, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def kilif_giydir(db, overlay, tpl, degerler: dict | None = None, yukseklik: int = 1040) -> Image.Image:
    """Kılıf görseli + tasarım (RGBA, kılıf görselinin oranında)."""
    if not tpl or not tpl.image_path:
        raise ValueError("Kılıf şablonunun görseli yok")
    yol = storage_svc.STORAGE_ROOT / tpl.image_path
    if not yol.is_file():
        raise ValueError("Kılıf şablonunun görseli bulunamadı")
    kilif = Image.open(yol).convert("RGBA")
    H = yukseklik
    W = max(1, round(H * kilif.width / kilif.height))
    kilif = kilif.resize((W, H), Image.LANCZOS)

    ax, ay = float(tpl.area_x) * W, float(tpl.area_y) * H
    aw, ah = max(1, round(float(tpl.area_w) * W)), max(1, round(float(tpl.area_h) * H))
    en, boy = float(tpl.print_width_mm), float(tpl.print_height_mm)
    oran = (float(tpl.area_w) * en) / (float(tpl.area_h) * boy) if tpl.area_h else 1.0
    katmanlar = kisitli_sablon.layers_uret(overlay, degerler or {}, db=db, alan_oran=oran)
    tasarim = _tuval_ciz(db, katmanlar, aw, ah, "kapak")
    maske = ImageChops.multiply(tasarim.getchannel("A"),
                                _yuvarlak_maske(aw, ah, float(tpl.area_radius or 0)))

    sonuc = kilif.copy()
    sonuc.paste(tasarim, (round(ax), round(ay)), maske)
    # Kamera/kesik bölgeleri: kılıf görselinin o parçası tasarımın üstüne döner
    for c in tpl.cutouts or []:
        try:
            cx, cy = round(float(c["x"]) * W), round(float(c["y"]) * H)
            cw, ch = max(1, round(float(c["w"]) * W)), max(1, round(float(c["h"]) * H))
        except (KeyError, TypeError, ValueError):
            continue
        parca = kilif.crop((cx, cy, cx + cw, cy + ch))
        km = ImageChops.multiply(parca.getchannel("A"),
                                 _yuvarlak_maske(cw, ch, float(c.get("radius") or 0)))
        sonuc.paste(parca, (cx, cy), km)
    return sonuc


def kapak_ciz(db, overlay, tpl, degerler: dict | None = None, kenar: int = KENAR) -> bytes:
    """Kare, açık zeminli, hafif gölgeli ürün fotoğrafı (JPEG)."""
    kenar = max(300, min(2000, int(kenar)))
    kilif = kilif_giydir(db, overlay, tpl, degerler, yukseklik=round(kenar * (1 - 2 * DOLGU)))
    if kilif.width > kenar * (1 - 2 * DOLGU):          # yatay/kare kılıf görseli
        o = kenar * (1 - 2 * DOLGU) / kilif.width
        kilif = kilif.resize((max(1, round(kilif.width * o)), max(1, round(kilif.height * o))), Image.LANCZOS)
    zemin = Image.new("RGB", (kenar, kenar), ZEMIN)
    x, y = (kenar - kilif.width) // 2, (kenar - kilif.height) // 2
    # Yumuşak gölge: kılıf zeminden ayrılsın
    golge = Image.new("L", (kenar, kenar), 0)
    golge.paste(kilif.getchannel("A").point(lambda v: v * 70 // 255),
                (x, y + round(kenar * 0.012)))
    golge = golge.filter(ImageFilter.GaussianBlur(kenar * 0.018))
    zemin.paste(Image.new("RGB", (kenar, kenar), (0, 0, 0)), (0, 0), golge)
    zemin.paste(kilif, (x, y), kilif)
    buf = io.BytesIO()
    zemin.save(buf, "JPEG", quality=92)
    return buf.getvalue()
