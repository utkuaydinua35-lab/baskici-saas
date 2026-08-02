"""Baskıya hazır dosya üretimi — müşterinin tasarımından gerçek baskı çıktısı.

İLKE: ekran görüntüsü ASLA baskıya gitmez. Bu modül müşterinin yüklediği
ORİJİNAL dosyaları ve editördekiyle aynı font dosyalarını kullanarak,
şablonda tanımlı fiziksel ölçüde (mm) ve çözünürlükte (DPI) yeniden çizer.

Katman konumları baskı alanına oransal (0-1) olduğundan, müşterinin 380 px
genişlikte gördüğü yerleşim 827×1713 px dosyada bire bir aynı yere düşer.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.storage import STORAGE_ROOT

log = logging.getLogger("design_render")

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
# Editördeki font anahtarı → dosya (storefront/components/studio/fonts.ts ile aynı)
FONT_FILES = {
    "poppins": "Poppins-SemiBold.ttf",
    "montserrat": "Montserrat-Bold.ttf",
    "playfair": "PlayfairDisplay-Bold.ttf",
    "bebas": "BebasNeue-Regular.ttf",
    "oswald": "Oswald-SemiBold.ttf",
    "dancing": "DancingScript-Bold.ttf",
    "lobster": "Lobster-Regular.ttf",
    "mono": "RobotoMono-Medium.ttf",
}
MAX_PRINT_PX = 8000     # güvenlik tavanı (10.000×10.000 PNG belleği yer)


def _font(key: str, size_px: int) -> ImageFont.FreeTypeFont:
    dosya = FONT_FILES.get(key) or FONT_FILES["poppins"]
    yol = FONT_DIR / dosya
    try:
        return ImageFont.truetype(str(yol), max(4, size_px))
    except OSError:
        log.warning("font bulunamadı: %s — varsayılan kullanılıyor", yol)
        return ImageFont.load_default()


def _asset_path(db, asset_id: str) -> Path | None:
    """Katmandaki asset_id → diskteki ORİJİNAL dosya."""
    from sqlalchemy import select

    from app.models import DesignAsset

    try:
        a = db.scalar(select(DesignAsset).where(DesignAsset.id == asset_id))
    except Exception:  # noqa: BLE001 — geçersiz uuid vb.
        return None
    if not a:
        return None
    p = STORAGE_ROOT / a.original_path
    return p if p.exists() else None


def _sar(ciz: ImageDraw.ImageDraw, metin: str, font, max_gen: int) -> list[str]:
    """Satır sarma — editördeki word-break davranışının aynısı."""
    satirlar: list[str] = []
    satir = ""
    for kelime in (metin or "").split():
        deneme = f"{satir} {kelime}".strip()
        if ciz.textlength(deneme, font=font) > max_gen and satir:
            satirlar.append(satir)
            satir = kelime
        else:
            satir = deneme
    if satir:
        satirlar.append(satir)
    return satirlar


def render_print_file(db, design, template) -> bytes:
    """Tasarımdan baskıya hazır PNG üret (saydam zeminli, RGBA).

    Dönüş: PNG bayt dizisi. Çağıran diske yazar (storage.save_design_render).
    """
    W = round(template.print_width_mm / 25.4 * template.print_dpi)
    H = round(template.print_height_mm / 25.4 * template.print_dpi)
    if W > MAX_PRINT_PX or H > MAX_PRINT_PX:
        raise ValueError(f"Baskı ölçüsü çok büyük: {W}×{H} px")

    tuval = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(tuval)

    for katman in (design.layers or []):
        tip = katman.get("type")
        try:
            if tip == "image":
                _ciz_gorsel(db, tuval, katman, W, H)
            elif tip == "text":
                _ciz_metin(tuval, ciz, katman, W, H)
        except Exception:  # noqa: BLE001 — tek katman baskıyı tümden bozmasın
            log.exception("katman çizilemedi (design=%s, tip=%s)", design.id, tip)

    import io

    buf = io.BytesIO()
    tuval.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _ciz_gorsel(db, tuval: Image.Image, k: dict, W: int, H: int) -> None:
    yol = _asset_path(db, str(k.get("asset_id") or ""))
    if not yol:
        return
    g = Image.open(yol)
    g.load()
    if g.mode != "RGBA":
        g = g.convert("RGBA")

    # Kırpma: editörde seçilen bölge, ORİJİNAL piksellere uygulanır
    c = k.get("crop")
    if c:
        gw, gh = g.size
        kutu = (
            max(0, int(float(c.get("x", 0)) * gw)),
            max(0, int(float(c.get("y", 0)) * gh)),
            min(gw, int((float(c.get("x", 0)) + float(c.get("w", 1))) * gw)),
            min(gh, int((float(c.get("y", 0)) + float(c.get("h", 1))) * gh)),
        )
        if kutu[2] > kutu[0] and kutu[3] > kutu[1]:
            g = g.crop(kutu)

    hedef_w = max(1, round(float(k.get("w", 1)) * W))
    hedef_h = max(1, round(float(k.get("h", 1)) * H))
    # LANCZOS: büyütmede de küçültmede de en temiz sonuç (baskı için önemli)
    g = g.resize((hedef_w, hedef_h), Image.LANCZOS)

    aci = float(k.get("rot") or 0)
    if aci:
        g = g.rotate(-aci, expand=True, resample=Image.BICUBIC)

    # Konum: döndürme kutuyu büyüttüğü için MERKEZ referans alınır
    mx = round((float(k.get("x", 0)) + float(k.get("w", 1)) / 2) * W)
    my = round((float(k.get("y", 0)) + float(k.get("h", 1)) / 2) * H)
    tuval.alpha_composite(g, (mx - g.width // 2, my - g.height // 2))


def _ciz_metin(tuval: Image.Image, ciz: ImageDraw.ImageDraw, k: dict, W: int, H: int) -> None:
    metin = (k.get("text") or "").strip()
    if not metin:
        return
    boy = max(4, round(float(k.get("size", 0.1)) * H))
    font = _font(str(k.get("font") or "poppins"), boy)
    kutu_gen = max(1, round(float(k.get("w", 0.8)) * W))
    satirlar = _sar(ciz, metin, font, kutu_gen)
    satir_yuk = round(boy * 1.15)

    # Metni kendi katmanına çiz — döndürme ancak böyle temiz olur
    kat = Image.new("RGBA", (kutu_gen, max(1, satir_yuk * len(satirlar))), (0, 0, 0, 0))
    kciz = ImageDraw.Draw(kat)
    hiza = k.get("align") or "left"
    for i, s in enumerate(satirlar):
        gen = kciz.textlength(s, font=font)
        x = 0 if hiza == "left" else (kutu_gen - gen) / 2 if hiza == "center" else kutu_gen - gen
        kciz.text((x, i * satir_yuk), s, font=font, fill=k.get("color") or "#000000")

    aci = float(k.get("rot") or 0)
    if aci:
        kat = kat.rotate(-aci, expand=True, resample=Image.BICUBIC)

    # Editörde metin kutusunun SOL-ÜSTÜ konumlandırılır; döndürmede merkez korunur
    sol = float(k.get("x", 0)) * W
    ust = float(k.get("y", 0)) * H
    mx = round(sol + kutu_gen / 2)
    my = round(ust + (satir_yuk * len(satirlar)) / 2)
    tuval.alpha_composite(kat, (mx - kat.width // 2, my - kat.height // 2))
