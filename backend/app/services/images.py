"""
Görsel optimize servisi — "her zaman kabul et, arka planda küçült" (Shopify davranışı).

Telefon fotoğrafları 12-20MB olabiliyor; müşteriye 'çok büyük' hatası göstermek
yerine sunucuda optimize edip küçük dosya yazarız: EXIF yönü düzeltilir, uzun
kenar max_px'e indirilir, JPEG (progressive, q85) olarak yeniden kodlanır.
Şeffaflık içeren PNG'ler PNG olarak optimize edilir (şeffaflık kaybolmaz).
"""
from __future__ import annotations

import io

import os
import threading
from pathlib import Path
from PIL import Image, ImageOps

# Bu boyutun altındaki ve max_px'i aşmayan görsellere dokunma (zaten optimal)
SKIP_THRESHOLD_BYTES = 300 * 1024


# Vitrin ürün görselleri için duyarlı (responsive) genişlikler.
# Telefon ~400, tablet ~800, masaüstü ~1280 piksellik kutuya oturur; ana
# dosya (≤2048) büyütme/lightbox için kalır. Küçük varyantlar YÜKLEME ANINDA
# üretilir ve statik sunulur — Next.js'in istek-anında optimize edicisi
# belleği kısıtlı VPS'te ilk ziyarette 2+ sn sürüyor ve eşzamanlı isteklerde
# zaman aşımına düşüyordu (görseller "ilk girişte gelmiyor" şikâyeti buydu).
RESPONSIVE_WIDTHS = (400, 800, 1280)


def responsive_variants(data: bytes) -> list[tuple[int, bytes, str]]:
    """Ana görselden küçük genişlik varyantları üret.

    Dönüş: [(genişlik, bytes, uzantı)]. Yalnız KÜÇÜLTÜR — ana görsel bir
    genişlikten darsa o varyant atlanır (büyütmek kaliteyi düşürür, boşa
    bayt yazar). Bozuk veri sessizce boş liste döner: ana görsel zaten
    kaydedildiği için varyant üretimi siparişi/yüklemeyi bozmamalı.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # noqa: BLE001
        return []
    img = ImageOps.exif_transpose(img)
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    kaynak_en = img.size[0]
    cikti: list[tuple[int, bytes, str]] = []
    for w in RESPONSIVE_WIDTHS:
        # HER bucket için bir dosya üret — kaynak dardan büyükse o genişlikte
        # KLAMPLA (asla büyütme). Böylece vitrin srcset'i -400/-800/-1280'i
        # her zaman bulur; üretilmemiş varyant 404 vermez. Küçük kaynakta
        # dosyalar neredeyse aynı olur, bayt maliyeti önemsiz.
        hedef_en = min(w, kaynak_en)
        oran = hedef_en / float(img.size[0])
        yeni_boy = (hedef_en, max(1, round(img.size[1] * oran)))
        kucuk = img.resize(yeni_boy, Image.LANCZOS) if hedef_en < kaynak_en else img.copy()
        buf = io.BytesIO()
        if has_alpha:
            kucuk.convert("RGBA").save(buf, format="PNG", optimize=True)
            cikti.append((w, buf.getvalue(), "png"))
        else:
            (kucuk if kucuk.mode == "RGB" else kucuk.convert("RGB")).save(
                buf, format="JPEG", quality=82, optimize=True, progressive=True)
            cikti.append((w, buf.getvalue(), "jpg"))
        # WebP eşi — vitrin srcset'i bunu ister (JPEG'den ~%30 küçük; tüm
        # güncel tarayıcılar destekler). Saydamlık korunur.
        cikti.append((w, webp_kodla(kucuk), "webp"))
    return cikti


def webp_kodla(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    alfa = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    (img.convert("RGBA") if alfa else img.convert("RGB")).save(buf, format="WEBP", quality=80, method=4)
    return buf.getvalue()


def webp_varyant_uret(kaynak: Path, hedef: Path, en: int) -> bool:
    """Eski görsellerin WebP varyantını İLK İSTEKTE üret (bkz. main.SafeStaticFiles).

    kaynak: aynı genişlikteki JPEG/PNG varyantı ya da ana görsel (gerekirse
    küçültülür, asla büyütülmez). Yarım dosya görünmesin diye geçici dosyaya
    yazılıp yerine taşınır (aynı anda iki istek gelirse ikisi de güvenli).
    """
    try:
        img = Image.open(kaynak)
        img.load()
    except Exception:  # noqa: BLE001
        return False
    img = ImageOps.exif_transpose(img)
    if img.size[0] > en:
        img = img.resize((en, max(1, round(img.size[1] * en / img.size[0]))), Image.LANCZOS)
    gecici = hedef.with_name(f".{hedef.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    gecici.write_bytes(webp_kodla(img))
    os.replace(gecici, hedef)
    return True


def optimize_image(
    data: bytes,
    *,
    max_px: int = 2048,
    quality: int = 85,
) -> tuple[bytes, str]:
    """Görseli optimize et. Dönüş: (bytes, uzantı: 'jpg'|'png').

    Bozuk/açılamayan görselde ValueError (çağıran 422'ye çevirir).
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:  # noqa: BLE001 — Pillow çok çeşitli hata atar
        raise ValueError(f"Görsel dosyası okunamadı: {e}") from e

    # EXIF yönünü uygula (dikey telefon fotoğrafları yan yatmasın)
    img = ImageOps.exif_transpose(img)

    needs_resize = max(img.size) > max_px
    if len(data) <= SKIP_THRESHOLD_BYTES and not needs_resize:
        ext = (img.format or "jpeg").lower()
        return data, ("jpg" if ext in ("jpeg", "jpg") else ext)

    if needs_resize:
        img.thumbnail((max_px, max_px), Image.LANCZOS)

    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    buf = io.BytesIO()
    if has_alpha:
        # Şeffaflık korunmalı → optimize PNG
        img.convert("RGBA").save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "png"

    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue(), "jpg"
