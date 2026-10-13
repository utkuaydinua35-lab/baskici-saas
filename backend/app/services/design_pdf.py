"""Baskıya hazır PDF — vektörel yazı + CMYK renk.

PNG çıktısı (design_render.py) ekranla birebir aynı görüntüyü verir ama her şey
rasterdir ve renkler RGB'dir. Matbaa/RIP tarafında istenen dosya ise:
  • yazılar ve şekiller VEKTÖR (punto ne olursa olsun kenarlar keskin),
  • renk uzayı DOĞRU: mağazanın ICC profili yüklüyse gerçek CMYK, yüklü
    değilse sRGB (profil gömülü) — profilsiz "sözde CMYK" ÜRETİLMEZ,
  • sayfa GERÇEK fiziksel ölçüde (70×145 mm gibi).

Bu modül aynı katman listesinden PDF üretir. Fotoğraflar vektöre çevrilemez
(fizik) — onlar CMYK rastere dönüştürülüp gömülür; müşteri PDF/SVG yüklediyse
o dosya OLDUĞU GİBİ (vektörel) gömülür, yeniden çizilmez.

PyMuPDF tek başına üçünü de yapar: font gömme, CMYK renk (4 elemanlı renk
demeti) ve PDF-içine-PDF yerleştirme.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image

from app.services.design_render import (
    FONT_DIR, FONT_FILES, TAVAN_PUNTO, _basilabilir_renk, _kontur, _sayi_yoksa,
)
from app.services.storage import STORAGE_ROOT

log = logging.getLogger("design_pdf")

MM = 72 / 25.4          # 1 mm kaç punto
VEKTOR_UZANTILARI = {".pdf", ".svg", ".eps", ".ai"}


def hex_to_cmyk(hex_renk: str | None) -> tuple[float, float, float, float]:
    """#rrggbb → (c, m, y, k) 0-1 — PROFİLSİZ, kaba dönüşüm.

    DİKKAT: bu formülün ürettiği CMYK hiçbir baskı makinesine ait değildir;
    gerçek bir CMYK uzayında yorumlandığında renk solar. Yalnız ICC profili
    yokken ve CMYK zorunluysa son çare olarak kullanılır — normal yol
    _renk_cevirici()'dir.
    """
    s = _basilabilir_renk(hex_renk).lstrip("#")
    r, g, b = (int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))
    k = 1 - max(r, g, b)
    if k >= 1:
        return (0.0, 0.0, 0.0, 1.0)
    return ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k)


def _rgb01(hex_renk: str | None) -> tuple[float, float, float]:
    s = _basilabilir_renk(hex_renk).lstrip("#")
    return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _renk_cevirici(icc: bytes | None):
    """hex → PDF rengi. ICC varsa profille CMYK, yoksa sRGB.

    Yazı ve şekiller de görsellerle AYNI uzayda olmalı: biri CMYK biri RGB
    olursa aynı bordo iki farklı tonda basılır.
    """
    if not icc:
        return _rgb01
    try:
        from PIL import ImageCms
        kaynak = ImageCms.createProfile("sRGB")
        hedef = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        donusum = ImageCms.buildTransform(
            kaynak, hedef, "RGB", "CMYK",
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
    except Exception:  # noqa: BLE001 — bozuk profil baskıyı durdurmasın
        log.warning("ICC ile renk dönüşümü kurulamadı — sRGB kullanılıyor",
                    exc_info=True)
        return _rgb01

    bellek: dict[str, tuple] = {}

    def cevir(hex_renk: str | None) -> tuple:
        anahtar = _basilabilir_renk(hex_renk)
        if anahtar not in bellek:
            tek = Image.new("RGB", (1, 1), tuple(
                round(x * 255) for x in _rgb01(anahtar)))
            c, m, y, k = ImageCms.applyTransform(tek, donusum).getpixel((0, 0))
            bellek[anahtar] = (c / 255, m / 255, y / 255, k / 255)
        return bellek[anahtar]

    return cevir


def _srgb_profil() -> bytes | None:
    """Gömülecek sRGB profili — kaynak rengin hangi uzayda olduğunu söyler."""
    try:
        from PIL import ImageCms
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    except Exception:  # noqa: BLE001
        return None


def _baski_jpeg(img: Image.Image, icc: bytes | None) -> bytes:
    """Raster görseli baskı PDF'ine gömülecek JPEG'e çevir.

    ICC PROFİLİ VARSA → gerçek CMYK'ya dönüştürülür (matbaanın makinesine
    göre doğru renk).

    PROFİL YOKSA → sRGB olarak, profili GÖMÜLÜ hâlde bırakılır.
    Eskiden burada Pillow'un basit dönüşümü (C=1−R…) yapılıyordu. O dönüşüm
    matematiksel olarak kayıpsızdır ama ürettiği CMYK değerlerinin hiçbir
    baskı makinesiyle ilgisi yoktur: gerçek bir CMYK uzayında yorumlandığında
    renkler SOLUK ve MAT çıkar (koyu bordo kirli kırmızıya, altın sarısı
    soluk hardala döner) — kullanıcının bildirdiği tam olarak buydu.
    sRGB bırakmak matbaanın RIP'inin kendi (doğru) profiliyle çevirmesini
    sağlar; profilsiz naif CMYK'dan HER ZAMAN daha iyi sonuç verir.
    """
    if img.mode in ("RGBA", "LA", "P"):
        zemin = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        zemin.paste(img, mask=img.split()[-1])
        img = zemin
    elif img.mode != "RGB":
        img = img.convert("RGB")

    profil = _srgb_profil()
    if icc:
        try:
            from PIL import ImageCms
            kaynak = ImageCms.createProfile("sRGB")
            hedef = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            img = ImageCms.profileToProfile(
                img, kaynak, hedef, outputMode="CMYK",
                # Algısal niyet: gamut dışı renkleri kırpmak yerine yumuşakça
                # sıkıştırır — fotoğraf ve dolgu renklerde doğru tercih
                renderingIntent=ImageCms.Intent.PERCEPTUAL)
            profil = icc
        except Exception:  # noqa: BLE001 — bozuk profil baskıyı durdurmasın
            log.warning("ICC profili uygulanamadı — sRGB olarak gömülüyor",
                        exc_info=True)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, subsampling=0,
             **({"icc_profile": profil} if profil else {}))
    return buf.getvalue()


def _asset_yolu(db, asset_id: str) -> Path | None:
    from sqlalchemy import select

    from app.models import DesignAsset

    try:
        a = db.scalar(select(DesignAsset).where(DesignAsset.id == asset_id))
    except Exception:  # noqa: BLE001
        return None
    if not a:
        return None
    p = STORAGE_ROOT / a.original_path
    return p if p.exists() else None


def render_print_pdf(db, design, template, icc: bytes | None = None) -> bytes:
    """Tasarımdan baskıya hazır PDF üret (gerçek mm ölçüsünde, CMYK)."""
    import pymupdf

    W = template.print_width_mm * MM
    H = template.print_height_mm * MM

    belge = pymupdf.open()
    sayfa = belge.new_page(width=W, height=H)
    renk_fn = _renk_cevirici(icc)

    for katman in (design.layers or []):
        tip = katman.get("type")
        try:
            if tip == "text":
                _yazi(sayfa, katman, W, H, renk_fn)
            elif tip == "sekil":
                if katman.get("bicim") == "desen":
                    _desen(sayfa, katman, W, H, renk_fn)
                elif katman.get("bicim") == "amblem":
                    _amblem(db, sayfa, katman, W, H, icc)
                else:
                    _sekil(sayfa, katman, W, H, renk_fn)
            elif tip == "image":
                _gorsel(db, sayfa, katman, W, H, icc)
            elif tip == "overlay":
                _overlay(db, sayfa, katman, W, H, icc)
        except Exception:  # noqa: BLE001 — tek katman tüm dosyayı bozmasın
            log.exception("PDF katmanı çizilemedi (design=%s, tip=%s)", design.id, tip)

    çıktı = belge.tobytes(garbage=3, deflate=True)
    belge.close()
    return çıktı


def _yazi(sayfa, k: dict, W: float, H: float, renk_fn=_rgb01) -> None:
    """VEKTÖREL metin — font PDF'e gömülür, punto ne olursa olsun keskin."""
    import pymupdf

    metin = (k.get("text") or "").strip()
    if not metin:
        return
    dosya = FONT_FILES.get(str(k.get("font") or "poppins")) or FONT_FILES["poppins"]
    yol = FONT_DIR / dosya
    boy = float(k.get("size", 0.1)) * H
    renk = renk_fn(k.get("color"))
    kutu_gen = float(k.get("w", 0.8)) * W

    sol = float(k.get("x", 0)) * W
    ust = float(k.get("y", 0)) * H
    yaslama = str(k.get("align") or "left")
    hiza = {"left": 0, "center": 1, "right": 2}.get(yaslama, 0)

    # ÇERÇEVEYİ DOLDUR — PNG çıktısındaki kuralın aynısı (bkz. design_render):
    # kısa metin büyür, uzun metin küçülür; hem genişlik hem YÜKSEKLİK sınırlar.
    if k.get("sigdir") is True:
        try:
            font = pymupdf.Font(fontfile=str(yol))
            # Satır yüksekliği fontun kendi ölçüsünden (ascent - descent)
            oran = max(0.5, font.ascender - font.descender)
            # Yükseklik verilmemişse tanımlı puntonun doğal satırı → büyüme yok
            kutu_yuk = _sayi_yoksa(k.get("h"), 0) * H or boy * oran
            gen = _aralikli(font, metin, boy, _kontur(k, boy)[1])
            if gen > 0:
                boy = max(2.0, min(boy * kutu_gen / gen, kutu_yuk / oran,
                                   H * TAVAN_PUNTO))
                # TEK SATIR olarak çizilir: insert_textbox metni kutuya
                # sığdıramazsa HİÇ çizmez — punto büyüyünce kısa metinler
                # (tek harf, "10") baskı dosyasından tamamen düşüyordu.
                # Ekrandaki karşılığı da tek satırdır (white-space: nowrap).
                kalinlik, aralik = _kontur(k, boy)
                genislik = _aralikli(font, metin, boy, aralik)
                x = sol
                if yaslama == "center":
                    x = sol + (kutu_gen - genislik) / 2
                elif yaslama == "right":
                    x = sol + kutu_gen - genislik
                # insert_text TABAN ÇİZGİSİNİ ister. Metin çerçeveye dikey
                # ortalanır (PNG çıktısındaki kuralın aynısı).
                satir_ust = ust + (kutu_yuk - boy * oran) / 2
                taban = satir_ust + boy * font.ascender
                if not kalinlik:
                    sayfa.insert_text(
                        (x, taban), metin, fontsize=boy,
                        fontfile=str(yol), fontname=yol.stem, color=renk,
                    )
                    return
                # KONTURLU (forma tasarlayıcı): harfler tek tek, aralıklı.
                # ÖNCE tüm konturlar, SONRA tüm dolgular (PNG ile aynı sıra).
                kontur_renk = renk_fn(k.get("kontur"))
                konumlar, cx = [], x
                for h in metin:
                    konumlar.append((cx, h))
                    cx += font.text_length(h, fontsize=boy) + aralik
                onceki = len(sayfa.get_contents())
                for hx, h in konumlar:
                    # render_mode 2 = dolgu + çizgi; çizgi kenara ORTALANIR,
                    # yani dışarıda `kalinlik` görünmesi için genişlik 2 katı
                    sayfa.insert_text(
                        (hx, taban), h, fontsize=boy, fontfile=str(yol), fontname=yol.stem,
                        color=kontur_renk, fill=kontur_renk, render_mode=2,
                        border_width=2 * kalinlik / boy)
                _yuvarlak_kose(sayfa, onceki)
                for hx, h in konumlar:
                    sayfa.insert_text(
                        (hx, taban), h, fontsize=boy,
                        fontfile=str(yol), fontname=yol.stem, color=renk)
                return
        except Exception:  # noqa: BLE001 — ölçüm/çizim başarısızsa kutuya düşülür
            log.debug("PDF metin ölçülemedi — kutuya düşülüyor", exc_info=True)

    # Metin kutusu: PNG çıktısındaki satır sarma davranışının karşılığı
    kutu = pymupdf.Rect(sol, ust, sol + kutu_gen, H)
    sayfa.insert_textbox(
        kutu, metin, fontsize=boy, fontfile=str(yol), fontname=yol.stem,
        color=renk, align=hiza, lineheight=1.15,
    )


def _aralikli(font, metin: str, boy: float, aralik: float) -> float:
    """Metnin genişliği — konturluysa harfler tek tek, aralıklı ölçülür."""
    if not aralik:
        return font.text_length(metin, fontsize=boy)
    return sum(font.text_length(h, fontsize=boy) for h in metin) + aralik * max(0, len(metin) - 1)


def _yuvarlak_kose(sayfa, onceki: int) -> None:
    """Kontur çizgisinin köşelerini YUVARLAT (PDF varsayılanı sivri köşe:
    "1", "7", "M" gibi harflerde kontur diken gibi uzar; tuval ve PNG yuvarlak
    çizer). PyMuPDF'te bunun seçeneği yok — az önce eklenen içerik akışlarına
    çizgi birleşim/uç operatörü (1 j, 1 J) yazılır."""
    belge = sayfa.parent
    for xref in sayfa.get_contents()[onceki:]:
        try:
            akis = belge.xref_stream(xref)
            if akis and b"BT" in akis:
                belge.update_stream(xref, akis.replace(b"BT", b"1 j 1 J\nBT", 1))
        except Exception:  # noqa: BLE001 — yalnız görünüm; çizim yine geçerli
            log.debug("kontur köşesi yuvarlatılamadı", exc_info=True)


def _desen(sayfa, k: dict, W: float, H: float, renk_fn=_rgb01) -> None:
    """Forma zemini — VEKTÖR çokgenler (services/forma.desen_sekilleri)."""
    import pymupdf

    from app.services import forma

    renkler = [renk_fn(r) for r in (k.get("renkler") or [])][:3]
    while len(renkler) < 3:
        renkler.append(renk_fn("#ffffff"))
    sayfa.draw_rect(pymupdf.Rect(0, 0, W, H), color=renkler[0], fill=renkler[0], width=0)
    for sira, cokgen in forma.desen_sekilleri(str(k.get("desen") or "duz"),
                                              str(k.get("yogunluk") or "orta")):
        kirpik = forma.kirp_birim_kare(cokgen)      # sayfa dışına taşan şeritleri kes
        if len(kirpik) < 3:
            continue
        renk = renkler[min(sira, 2)]
        sayfa.draw_polyline([pymupdf.Point(x * W, y * H) for x, y in kirpik] +
                            [pymupdf.Point(kirpik[0][0] * W, kirpik[0][1] * H)],
                            color=renk, fill=renk, width=0, closePath=True)


def _amblem(db, sayfa, k: dict, W: float, H: float, icc: bytes | None) -> None:
    """Amblem — maske görseli seçilen renge boyanıp kutusuna ortalanır.
    Dosya şablon kaydından çözülür (katmandaki url kullanılmaz)."""
    import pymupdf
    from sqlalchemy import select

    from app.models import DesignOverlay
    from app.services import forma

    try:
        o = db.scalar(select(DesignOverlay).where(
            DesignOverlay.id == str(k.get("overlay_id") or "")))
    except Exception:  # noqa: BLE001
        return
    if not o:
        return
    yol = forma.amblem_dosyasi(getattr(o, "forma", None), str(k.get("amblem") or ""))
    if not yol:
        return
    maske = Image.open(yol)
    maske.load()
    alfa = maske.convert("RGBA").getchannel("A")
    kx, ky = float(k.get("x", 0)) * W, float(k.get("y", 0)) * H
    kw, kh = float(k.get("w", 0.2)) * W, float(k.get("h", 0.1)) * H
    olcek = min(kw / alfa.width, kh / alfa.height)
    gw, gh = alfa.width * olcek, alfa.height * olcek
    kutu = pymupdf.Rect(kx + (kw - gw) / 2, ky + (kh - gh) / 2,
                        kx + (kw + gw) / 2, ky + (kh + gh) / 2)
    renk = tuple(round(x * 255) for x in _rgb01(k.get("renk")))
    duz = Image.new("RGB", alfa.size, renk)
    buf = io.BytesIO()
    alfa.save(buf, "PNG")
    # Renk, yazı ve desenle AYNI uzaya çevrilir (_baski_jpeg: ICC varsa CMYK)
    sayfa.insert_image(kutu, stream=_baski_jpeg(duz, icc), mask=buf.getvalue())


def _sekil(sayfa, k: dict, W: float, H: float, renk_fn=_rgb01) -> None:
    """Vektör şekil — ilerleme çubuğu (Spotify)."""
    import pymupdf

    if k.get("bicim") != "ilerleme":
        return
    x = float(k.get("x", 0.1)) * W
    y = float(k.get("y", 0.5)) * H
    w = float(k.get("w", 0.8)) * W
    kal = float(k.get("kalinlik", 0.004)) * H
    yari = float(k.get("boyut", 0.012)) * H
    oran = max(0.0, min(1.0, float(k.get("oran", 0))))
    renk = renk_fn(k.get("renk"))
    pasif = renk_fn(k.get("renk_pasif"))

    sayfa.draw_rect(pymupdf.Rect(x, y - kal / 2, x + w, y + kal / 2),
                    color=pasif, fill=pasif, width=0)
    if oran > 0:
        sayfa.draw_rect(pymupdf.Rect(x, y - kal / 2, x + w * oran, y + kal / 2),
                        color=renk, fill=renk, width=0)
    sayfa.draw_circle(pymupdf.Point(x + w * oran, y), yari,
                      color=renk, fill=renk, width=0)


def _yerlestir(sayfa, yol: Path, kutu, icc: bytes | None, crop: dict | None = None) -> None:
    """Dosyayı sayfaya koy. PDF/SVG ise VEKTÖREL gömülür (rasterleşmez),
    raster ise CMYK'ya çevrilip gömülür."""
    import pymupdf

    if yol.suffix.lower() in VEKTOR_UZANTILARI:
        kaynak = pymupdf.open(str(yol))
        try:
            if kaynak.page_count:
                # SVG/EPS gibi dosyalar önce PDF'e çevrilir (vektör korunur)
                if not kaynak.is_pdf:
                    kaynak = pymupdf.open("pdf", kaynak.convert_to_pdf())
                sayfa.show_pdf_page(kutu, kaynak, 0)
        finally:
            kaynak.close()
        return

    img = Image.open(yol)
    img.load()
    if crop:
        gw, gh = img.size
        kutu_px = (
            max(0, int(float(crop.get("x", 0)) * gw)),
            max(0, int(float(crop.get("y", 0)) * gh)),
            min(gw, int((float(crop.get("x", 0)) + float(crop.get("w", 1))) * gw)),
            min(gh, int((float(crop.get("y", 0)) + float(crop.get("h", 1))) * gh)),
        )
        if kutu_px[2] > kutu_px[0] and kutu_px[3] > kutu_px[1]:
            img = img.crop(kutu_px)
    # SAYDAM görsel (logo, bayrak, delikli çerçeve): saydamlık MASKE olarak
    # gömülür. Eskiden beyaza düzleştiriliyordu — desenin/fotoğrafın üstüne
    # binen logo PDF'te beyaz bir kutu içinde çıkıyordu.
    maske = None
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        alfa = img.convert("RGBA").getchannel("A")
        if alfa.getextrema()[0] < 255:
            buf = io.BytesIO()
            alfa.save(buf, "PNG")
            maske = buf.getvalue()
            # Renk kanalı beyazla KARIŞTIRILMAZ (kenarlarda açık renk hale olurdu)
            img = img.convert("RGBA").convert("RGB")
    sayfa.insert_image(kutu, stream=_baski_jpeg(img, icc), **({"mask": maske} if maske else {}))


def _gorsel(db, sayfa, k: dict, W: float, H: float, icc: bytes | None) -> None:
    import pymupdf

    yol = _asset_yolu(db, str(k.get("asset_id") or ""))
    if not yol:
        return
    x = float(k.get("x", 0)) * W
    y = float(k.get("y", 0)) * H
    kutu = pymupdf.Rect(x, y, x + float(k.get("w", 1)) * W, y + float(k.get("h", 1)) * H)
    _yerlestir(sayfa, yol, kutu, icc, k.get("crop"))


def _overlay(db, sayfa, k: dict, W: float, H: float, icc: bytes | None) -> None:
    """Hazır şablon: tabanda tüm sayfayı kaplar, alan öğesiyse kendi kutusuna."""
    import pymupdf
    from sqlalchemy import select

    from app.models import DesignOverlay

    try:
        o = db.scalar(select(DesignOverlay).where(
            DesignOverlay.id == str(k.get("overlay_id") or "")))
    except Exception:  # noqa: BLE001
        return
    if not o:
        return

    alan_key = k.get("field")
    if alan_key:
        alan = next((a for a in (o.alanlar or [])
                     if str(a.get("key")) == str(alan_key) and a.get("tip") == "gorsel"), None)
        if not alan or not alan.get("image_path"):
            return
        yol = STORAGE_ROOT / alan["image_path"]
        x = float(alan.get("x", 0)) * W
        y = float(alan.get("y", 0)) * H
        kutu = pymupdf.Rect(x, y, x + float(alan.get("w", 0.1)) * W,
                            y + float(alan.get("h", 0.1)) * H)
    else:
        yol = STORAGE_ROOT / o.image_path
        kutu = pymupdf.Rect(0, 0, W, H)

    if not yol.exists():
        log.warning("PDF: şablon dosyası yok: %s", yol)
        return
    _yerlestir(sayfa, yol, kutu, icc)
