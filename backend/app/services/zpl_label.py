"""Etiketi ZPL'e çevir — Zebra yazıcıya DOĞRUDAN gönderilmek üzere.

Neden: tarayıcıdan yazdırınca hem onay penceresi çıkıyor hem de ölçekleme
ayarları çıktıyı bozabiliyor (barkod küçülüyor). Zebra GX420t ZPL konuşuyor;
etiketi 203 dpi'da 1-bit bitmap'e çevirip ^GFA ile gömdüğümüzde çıktı piksel
piksel bizim kontrolümüzde olur — yazıcı ayarlarından bağımsız.

Akış: SVG/PDF -> PyMuPDF ile raster -> eşikle 1-bit -> ^GFA hex -> ZPL
"""
from __future__ import annotations

import re

import fitz

# GX420t ve GX430t: 203 / 300 dpi. Yanlış dpi = yanlış fiziksel boyut.
VARSAYILAN_DPI = 203
# GX420t azami baskı genişliği 4 inç = 832 nokta (203 dpi)
AZAMI_NOKTA = 832


class ZplError(Exception):
    pass


def _pixmap_to_zpl_gfa(pix: fitz.Pixmap, esik: int = 128) -> tuple[str, int, int]:
    """Pixmap -> (^GFA hex verisi, satır_bayt, toplam_bayt).

    ZPL bitmap: satır satır, her satır tam bayta tamamlanır, 1 = SİYAH.
    """
    g = fitz.Pixmap(fitz.csGRAY, pix) if pix.n > 1 else pix
    w, h = g.width, g.height
    if w > AZAMI_NOKTA:
        raise ZplError(f"Etiket çok geniş: {w} nokta (azami {AZAMI_NOKTA})")
    satir_bayt = (w + 7) // 8
    ham = g.samples                     # bytes, w*h (gray)
    parcalar = []
    for y in range(h):
        satir = bytearray(satir_bayt)
        taban = y * w
        for x in range(w):
            if ham[taban + x] < esik:    # koyu piksel -> 1
                satir[x >> 3] |= 0x80 >> (x & 7)
        parcalar.append(satir.hex().upper())
    return "".join(parcalar), satir_bayt, satir_bayt * h


def _belge_zpl(doc: fitz.Document, dpi: int, esik: int,
               w_mm: float | None = None, h_mm: float | None = None,
               doldur: bool = True) -> str:
    """Etiketi w_mm x h_mm ölçüsünde bas.

    doldur=True (varsayılan): iki eksen AYRI ölçeklenir, etiket TAMAMEN dolar.
      Kaynak etiketin oranı stoğunkiyle aynı olmadığı için oran korunduğunda
      kenarda büyük boşluk kalıyordu (8x10 stokta içerik ~2/3'ünü kaplıyordu).
      Barkod okunabilirliği bundan etkilenmez: tüm çubuklar aynı oranda
      genişlediği için çubuk genişlik ORANLARI korunur.
    doldur=False: oran korunur, kenarda boşluk kalabilir.
    """
    if doc.page_count == 0:
        raise ZplError("Etiket boş")
    sayfa = doc[0]
    if w_mm and h_mm:
        hedef_w = w_mm / 25.4 * dpi
        hedef_h = h_mm / 25.4 * dpi
        ox = hedef_w / sayfa.rect.width
        oy = hedef_h / sayfa.rect.height
        if not doldur:
            ox = oy = min(ox, oy)
        matris = fitz.Matrix(ox, oy)
    else:
        olcek = dpi / 72.0
        matris = fitz.Matrix(olcek, olcek)
    pix = sayfa.get_pixmap(matrix=matris, alpha=False)
    veri, satir_bayt, toplam = _pixmap_to_zpl_gfa(pix, esik)
    # ^PW: baskı genişliği, ^LL: etiket uzunluğu — yazıcının kendi ayarını ezer,
    # böylece çıktı yazıcıda ne ayarlı olduğundan bağımsız doğru gelir.
    return (
        "^XA"
        "^CI28"                     # UTF-8
        f"^PW{pix.width}"
        f"^LL{pix.height}"
        "^LH0,0"
        f"^FO0,0^GFA,{toplam},{toplam},{satir_bayt},{veri}^FS"
        "^XZ"
    )


# SVG'deki font adlarini yakala: hem font-family="X" hem style="font-family:X"
_FONT_NITELIK = re.compile(r'font-family\s*=\s*(["\'])(.*?)\1', re.I)
_FONT_CSS = re.compile(r'font-family\s*:\s*([^;"\'}]+)', re.I)

# MuPDF'in dahili olarak TANIDIGI sans font. Tanimadigi her adi Times'a
# (serif) dusuruyor — etiket bu yuzden serif basiliyordu.
GUVENLI_SANS = "Helvetica"


def fontlari_sadelestir(svg: str, font: str = GUVENLI_SANS) -> str:
    """SVG'deki TUM yazilara MuPDF'in tanidigi bir sans font ata.

    Basit Kargo'nun etiketinde 12 <text> var ama font tanimi yalnizca 2'sinde
    ve o da BOS. Tanimi olmayan yazilar MuPDF'in varsayilanina, yani Times'a
    (serif) dusuyor ve etiket serif basiliyordu. Tarayicidan basarken sorun yok
    cunku tarayicinin varsayilani sans.

    Bu yuzden var olan tanimi degistirmek YETMEZ; her <text>/<tspan> ogesine
    font ATANIR. Kalinlik (font-weight) ve olcu (font-size) korunur.
    """
    # 1) Mevcut (bos ya da dolu) tanimlari duzelt
    svg = _FONT_NITELIK.sub(lambda m: f'font-family="{font}"', svg)
    svg = _FONT_CSS.sub(lambda m: f"font-family:{font}", svg)

    # 2) Tanimi OLMAYAN yazi ogelerine ekle
    def _ekle(m):
        etiket = m.group(0)
        if re.search(r"font-family", etiket, re.I):
            return etiket
        return f"{m.group(1)} font-family=\"{font}\"{m.group(2)}"

    svg = re.sub(r"(<(?:text|tspan)\b)([^>]*>)", _ekle, svg, flags=re.I)

    # 3) Emniyet kemeri: stil bloguyla da tanimla (nitelik yakalanmayan
    #    bicimlerde devreye girer; nitelik varsa o kazanir, zarari yok)
    stil = f"<style>text,tspan{{font-family:{font},sans-serif}}</style>"
    if "<svg" in svg:
        kapanis = svg.index(">", svg.index("<svg")) + 1
        svg = svg[:kapanis] + stil + svg[kapanis:]
    return svg


def svg_to_zpl(svg: str, dpi: int = VARSAYILAN_DPI, esik: int = 128,
               w_mm: float | None = None, h_mm: float | None = None,
               doldur: bool = True) -> str:
    try:
        doc = fitz.open(stream=fontlari_sadelestir(svg).encode("utf-8"), filetype="svg")
    except Exception as e:  # noqa: BLE001
        raise ZplError(f"SVG okunamadı: {str(e)[:120]}") from e
    try:
        return _belge_zpl(doc, dpi, esik, w_mm, h_mm, doldur)
    finally:
        doc.close()


def pdf_to_zpl(pdf: bytes, dpi: int = VARSAYILAN_DPI, esik: int = 128,
               w_mm: float | None = None, h_mm: float | None = None,
               doldur: bool = True) -> str:
    try:
        doc = fitz.open(stream=pdf, filetype="pdf")
    except Exception as e:  # noqa: BLE001
        raise ZplError(f"PDF okunamadı: {str(e)[:120]}") from e
    try:
        return _belge_zpl(doc, dpi, esik, w_mm, h_mm, doldur)
    finally:
        doc.close()
