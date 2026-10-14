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


def _kilif_ac(tpl, yukseklik: int) -> Image.Image:
    if not tpl or not tpl.image_path:
        raise ValueError("Kılıf şablonunun görseli yok")
    yol = storage_svc.STORAGE_ROOT / tpl.image_path
    if not yol.is_file():
        raise ValueError("Kılıf şablonunun görseli bulunamadı")
    kilif = Image.open(yol).convert("RGBA")
    W = max(1, round(yukseklik * kilif.width / kilif.height))
    return kilif.resize((W, yukseklik), Image.LANCZOS)


def _alan(tpl, W: int, H: int) -> tuple[int, int, int, int]:
    return (round(float(tpl.area_x) * W), round(float(tpl.area_y) * H),
            max(1, round(float(tpl.area_w) * W)), max(1, round(float(tpl.area_h) * H)))


def _giydir(kilif: Image.Image, tpl, tasarim: Image.Image) -> Image.Image:
    """Baskı alanı ölçüsündeki tasarımı (RGBA) kılıfa oturt, kesikleri üste al."""
    W, H = kilif.size
    ax, ay, aw, ah = _alan(tpl, W, H)
    if tasarim.size != (aw, ah):
        tasarim = tasarim.resize((aw, ah), Image.LANCZOS)
    maske = ImageChops.multiply(tasarim.getchannel("A"),
                                _yuvarlak_maske(aw, ah, float(tpl.area_radius or 0)))
    sonuc = kilif.copy()
    sonuc.paste(tasarim, (ax, ay), maske)
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


def kilif_giydir(db, overlay, tpl, degerler: dict | None = None, yukseklik: int = 1040) -> Image.Image:
    """Kılıf görseli + şablonun tasarımı (RGBA, kılıf görselinin oranında)."""
    kilif = _kilif_ac(tpl, yukseklik)
    _, _, aw, ah = _alan(tpl, *kilif.size)
    en, boy = float(tpl.print_width_mm), float(tpl.print_height_mm)
    oran = (float(tpl.area_w) * en) / (float(tpl.area_h) * boy) if tpl.area_h else 1.0
    katmanlar = kisitli_sablon.layers_uret(overlay, degerler or {}, db=db, alan_oran=oran)
    return _giydir(kilif, tpl, _tuval_ciz(db, katmanlar, aw, ah, "kapak"))


def gorsel_giydir(tpl, tasarim: Image.Image, yukseklik: int = 1040) -> Image.Image:
    """Hazır bir baskı görselini (müşteriye özel tasarım) kılıfa giydir.
    Görsel baskı alanını KAPLAR (oran farkı ortadan kırpılır)."""
    kilif = _kilif_ac(tpl, yukseklik)
    _, _, aw, ah = _alan(tpl, *kilif.size)
    t = tasarim.convert("RGBA")
    olcek = max(aw / t.width, ah / t.height)
    t = t.resize((max(aw, round(t.width * olcek)), max(ah, round(t.height * olcek))), Image.LANCZOS)
    sol, ust = (t.width - aw) // 2, (t.height - ah) // 2
    return _giydir(kilif, tpl, t.crop((sol, ust, sol + aw, ust + ah)))


def kare_kapak(kilif: Image.Image, kenar: int = KENAR) -> bytes:
    """Kılıfı kare, açık zeminli, hafif gölgeli ürün fotoğrafına koy (JPEG)."""
    kenar = max(300, min(2000, int(kenar)))
    sinir = kenar * (1 - 2 * DOLGU)
    o = min(sinir / kilif.width, sinir / kilif.height)
    if abs(o - 1) > 0.001:
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


def kapak_ciz(db, overlay, tpl, degerler: dict | None = None, kenar: int = KENAR) -> bytes:
    """Şablonun kare ürün fotoğrafı (JPEG)."""
    kenar = max(300, min(2000, int(kenar)))
    return kare_kapak(kilif_giydir(db, overlay, tpl, degerler,
                                   yukseklik=round(kenar * (1 - 2 * DOLGU))), kenar)
