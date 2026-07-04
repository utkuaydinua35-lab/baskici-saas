"""
Görsel optimize servisi — "her zaman kabul et, arka planda küçült" (Shopify davranışı).

Telefon fotoğrafları 12-20MB olabiliyor; müşteriye 'çok büyük' hatası göstermek
yerine sunucuda optimize edip küçük dosya yazarız: EXIF yönü düzeltilir, uzun
kenar max_px'e indirilir, JPEG (progressive, q85) olarak yeniden kodlanır.
Şeffaflık içeren PNG'ler PNG olarak optimize edilir (şeffaflık kaybolmaz).
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps

# Bu boyutun altındaki ve max_px'i aşmayan görsellere dokunma (zaten optimal)
SKIP_THRESHOLD_BYTES = 300 * 1024


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
