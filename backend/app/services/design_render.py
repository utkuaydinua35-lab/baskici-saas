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
    "anton": "Anton-Regular.ttf",
    "staatliches": "Staatliches-Regular.ttf",
    "russo": "RussoOne-Regular.ttf",
    "gotik": "UnifrakturCook-Bold.ttf",
    "pirata": "PirataOne-Regular.ttf",
    "bangers": "Bangers-Regular.ttf",
    "marker": "PermanentMarker-Regular.ttf",
    "sprey": "RockSalt-Regular.ttf",
    "bungee": "Bungee-Regular.ttf",
    "alfaslab": "AlfaSlabOne-Regular.ttf",
    "creepster": "Creepster-Regular.ttf",
    "caveat": "Caveat-Regular.ttf",
    "greatvibes": "GreatVibes-Regular.ttf",
    "pacifico": "Pacifico-Regular.ttf",
    "monoton": "Monoton-Regular.ttf",
    "righteous": "Righteous-Regular.ttf",
    "elite": "SpecialElite-Regular.ttf",
}
MAX_PRINT_PX = 8000     # güvenlik tavanı (10.000×10.000 PNG belleği yer)

# BASKI RENK KURALI (storefront/components/studio/renk.ts ile aynı):
# CMYK bileşenlerinin tamamı ~0 olan renk (saf beyaz) baskı makinesinde
# "mürekkep yok" demektir — o alana hiç baskı yapılmaz. Beyaz her zaman
# CMYK 0,0,0,5 ile basılır. İstemci düzeltmeyi atlarsa burada yakalanır.
BASKI_BEYAZ = "#f2f2f2"


def _basilabilir_renk(ham: str | None) -> str:
    s = (ham or "").strip().lstrip("#").lower()
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6 or any(ch not in "0123456789abcdef" for ch in s):
        return "#000000"
    r, g, b = (int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))
    k = 1 - max(r, g, b)
    if k >= 1:
        return f"#{s}"          # saf siyah — sorun yok
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    if max(c, m, y, k) < 0.02:
        return BASKI_BEYAZ
    return f"#{s}"


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
            elif tip == "overlay":
                _ciz_overlay(db, tuval, katman, W, H)
            elif tip == "text":
                _ciz_metin(tuval, ciz, katman, W, H)
            elif tip == "sekil":
                _ciz_sekil(ciz, katman, W, H)
        except Exception:  # noqa: BLE001 — tek katman baskıyı tümden bozmasın
            log.exception("katman çizilemedi (design=%s, tip=%s)", design.id, tip)

    import io

    buf = io.BytesIO()
    tuval.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# KATMAN SIRASI: dizideki sıra çizim sırasıdır (ilk eleman en altta). Tipe göre
# otomatik sıralama YOK — müşteri hazır şablonu (çerçeveyi) editörde istediği
# katmana taşıyabilir. Storefront karşılığı: components/studio/katmanlar.ts


def _ciz_sekil(ciz: ImageDraw.ImageDraw, k: dict, W: int, H: int) -> None:
    """Kısıtlı şablonun çizilen öğeleri — şimdilik "ilerleme" (Spotify çubuğu).

    Çubuğun dolu kısmı ve noktanın konumu, müşterinin yazdığı geçen/toplam
    süreden hesaplanan orandan gelir (kisitli_sablon.layers_uret).
    """
    if k.get("bicim") != "ilerleme":
        return
    x = float(k.get("x", 0.1)) * W
    y = float(k.get("y", 0.5)) * H
    w = float(k.get("w", 0.8)) * W
    kalinlik = max(1, round(float(k.get("kalinlik", 0.004)) * H))
    yaricap = max(1, round(float(k.get("boyut", 0.012)) * H))
    oran = max(0.0, min(1.0, float(k.get("oran", 0))))
    renk = _basilabilir_renk(k.get("renk"))
    pasif = _basilabilir_renk(k.get("renk_pasif"))

    ciz.rectangle([x, y - kalinlik / 2, x + w, y + kalinlik / 2], fill=pasif)
    if oran > 0:
        ciz.rectangle([x, y - kalinlik / 2, x + w * oran, y + kalinlik / 2], fill=renk)
    nx = x + w * oran
    ciz.ellipse([nx - yaricap, y - yaricap, nx + yaricap, y + yaricap], fill=renk)


def _ciz_overlay(db, tuval: Image.Image, k: dict, W: int, H: int) -> None:
    """Hazır şablon. Katmanda 'field' yoksa şablonun kendi görseli baskı
    alanını tam kaplar; 'field' varsa o ALANIN görseli (kısıtlı şablondaki
    bayrak/logo gibi açılabilir öğe) kendi konumuna çizilir.

    Dosya yolu İSTEMCİDEN DEĞİL veritabanından okunur: müşteri katmana
    istediği url'i yazsa bile sunucu yalnızca kendi kayıtlı dosyasını basar.
    """
    from sqlalchemy import select

    from app.models import DesignOverlay

    try:
        o = db.scalar(select(DesignOverlay).where(
            DesignOverlay.id == str(k.get("overlay_id") or "")))
    except Exception:  # noqa: BLE001 — geçersiz uuid
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
        kutu = (
            round(float(alan.get("x", 0)) * W), round(float(alan.get("y", 0)) * H),
            max(1, round(float(alan.get("w", 0.1)) * W)),
            max(1, round(float(alan.get("h", 0.1)) * H)),
        )
    else:
        yol = STORAGE_ROOT / o.image_path
        kutu = (0, 0, W, H)

    if not yol.exists():
        log.warning("hazır şablon dosyası yok: %s", yol)
        return
    g = Image.open(yol)
    g.load()
    if g.mode != "RGBA":
        g = g.convert("RGBA")
    g = g.resize((kutu[2], kutu[3]), Image.LANCZOS)
    tuval.alpha_composite(g, (kutu[0], kutu[1]))


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
    kutu_gen = max(1, round(float(k.get("w", 0.8)) * W))
    font = _font(str(k.get("font") or "poppins"), boy)

    # ÇERÇEVEYE SIĞDIR: metin kutuya sığmıyorsa punto orantılı küçültülür.
    # "10" tanımlı puntoda çıkar, "100" aynı genişliğe sığacak kadar küçülür.
    # Yalnız KISITLI ŞABLON alanlarında açıktır (katman üreticisi sigdir=True
    # yazar); serbest editörde punto müşterinin kendi ayarıdır, dokunulmaz.
    if k.get("sigdir") is True:
        gen = ciz.textlength(metin, font=font)
        if gen > kutu_gen and gen > 0:
            boy = max(4, int(boy * kutu_gen / gen))
            font = _font(str(k.get("font") or "poppins"), boy)

    satirlar = _sar(ciz, metin, font, kutu_gen)
    satir_yuk = round(boy * 1.15)

    # Metni kendi katmanına çiz — döndürme ancak böyle temiz olur
    kat = Image.new("RGBA", (kutu_gen, max(1, satir_yuk * len(satirlar))), (0, 0, 0, 0))
    kciz = ImageDraw.Draw(kat)
    hiza = k.get("align") or "left"
    for i, s in enumerate(satirlar):
        gen = kciz.textlength(s, font=font)
        x = 0 if hiza == "left" else (kutu_gen - gen) / 2 if hiza == "center" else kutu_gen - gen
        kciz.text((x, i * satir_yuk), s, font=font,
                  fill=_basilabilir_renk(k.get("color")))

    aci = float(k.get("rot") or 0)
    if aci:
        kat = kat.rotate(-aci, expand=True, resample=Image.BICUBIC)

    # Editörde metin kutusunun SOL-ÜSTÜ konumlandırılır; döndürmede merkez korunur
    sol = float(k.get("x", 0)) * W
    ust = float(k.get("y", 0)) * H
    mx = round(sol + kutu_gen / 2)
    my = round(ust + (satir_yuk * len(satirlar)) / 2)
    tuval.alpha_composite(kat, (mx - kat.width // 2, my - kat.height // 2))
