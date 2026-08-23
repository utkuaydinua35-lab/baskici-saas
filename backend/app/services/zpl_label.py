"""Etiketi ZPL'e çevir — Zebra yazıcıya DOĞRUDAN gönderilmek üzere.

Neden: tarayıcıdan yazdırınca hem onay penceresi çıkıyor hem de ölçekleme
ayarları çıktıyı bozabiliyor (barkod küçülüyor). Zebra GX420t ZPL konuşuyor;
etiketi 203 dpi'da 1-bit bitmap'e çevirip ^GFA ile gömdüğümüzde çıktı piksel
piksel bizim kontrolümüzde olur — yazıcı ayarlarından bağımsız.

Akış: SVG/PDF -> PyMuPDF ile raster -> eşikle 1-bit -> ^GFA hex -> ZPL
"""
from __future__ import annotations

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


def _belge_zpl(doc: fitz.Document, dpi: int, esik: int) -> str:
    if doc.page_count == 0:
        raise ZplError("Etiket boş")
    sayfa = doc[0]
    olcek = dpi / 72.0
    pix = sayfa.get_pixmap(matrix=fitz.Matrix(olcek, olcek), alpha=False)
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


def svg_to_zpl(svg: str, dpi: int = VARSAYILAN_DPI, esik: int = 128) -> str:
    try:
        doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    except Exception as e:  # noqa: BLE001
        raise ZplError(f"SVG okunamadı: {str(e)[:120]}") from e
    try:
        return _belge_zpl(doc, dpi, esik)
    finally:
        doc.close()


def pdf_to_zpl(pdf: bytes, dpi: int = VARSAYILAN_DPI, esik: int = 128) -> str:
    try:
        doc = fitz.open(stream=pdf, filetype="pdf")
    except Exception as e:  # noqa: BLE001
        raise ZplError(f"PDF okunamadı: {str(e)[:120]}") from e
    try:
        return _belge_zpl(doc, dpi, esik)
    finally:
        doc.close()
