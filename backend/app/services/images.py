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


def arka_plani_sil(data: bytes, tolerans: int = 42) -> bytes:
    """Düz zeminde çekilmiş ürün fotoğrafının arka planını saydam yapar.

    Kılıf fotoğrafları genelde tek renk masa/fon üzerinde çekilir. Kenarlardan
    içeri doğru "taşma doldurma" (flood fill) yapılır: köşe rengine yakın ve
    KENARA BAĞLI pikseller silinir. Ürünün içindeki benzer renkler kenara
    bağlı olmadığı için korunur — bu yüzden basit renk eşiğinden iyidir.

    Sonda saydam kenar boşluğu kırpılır, böylece kılıf çerçeveyi doldurur.
    """
    from collections import deque

    img = Image.open(io.BytesIO(data))
    img.load()
    img = ImageOps.exif_transpose(img).convert("RGBA")
    w, h = img.size
    px = img.load()

    # Zemin rengi: dört köşenin ortalaması (kenarda ürün olmadığı varsayımı)
    koseler = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    zemin = tuple(sum(c[i] for c in koseler) // 4 for i in range(3))

    def yakin(p) -> bool:
        return (abs(p[0] - zemin[0]) + abs(p[1] - zemin[1]) + abs(p[2] - zemin[2])) <= tolerans * 3

    gorulen = bytearray(w * h)
    kuyruk: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if yakin(px[x, y]):
                kuyruk.append((x, y)); gorulen[y * w + x] = 1
    for y in range(h):
        for x in (0, w - 1):
            if not gorulen[y * w + x] and yakin(px[x, y]):
                kuyruk.append((x, y)); gorulen[y * w + x] = 1

    while kuyruk:
        x, y = kuyruk.popleft()
        px[x, y] = (0, 0, 0, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not gorulen[ny * w + nx] and yakin(px[nx, ny]):
                gorulen[ny * w + nx] = 1
                kuyruk.append((nx, ny))

    kutu = img.getbbox()          # saydam kenar boşluğunu at
    if kutu:
        img = img.crop(kutu)

    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
