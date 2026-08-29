"""
Kargo etiketi PDF'i — mağaza adı + sipariş no + alıcı adresi + TARANABİLİR
Code 128 barkod.

Barkod eskiden '*KOD*' diye düz metin yazılıyordu (okutulamıyordu); artık
gerçek Code 128-B çubukları çiziliyor. Kendi kargo anlaşmasıyla çalışırken
paketin üzerine yapıştırılan etiket budur.

PyMuPDF base14 fontu Türkçe ş/ğ/İ desteklemediği için METİN ASCII'ye çevrilir;
barkodun kendisi zaten ASCII (Code128-B).
"""
from __future__ import annotations

import io

import fitz  # PyMuPDF

from app.services import barcode128

CM = 28.3464567

_TR = str.maketrans({
    "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G", "İ": "I", "ı": "i",
    "ö": "o", "Ö": "O", "ü": "u", "Ü": "U", "ç": "c", "Ç": "C",
})


def _a(s) -> str:
    return (s or "").translate(_TR)


def _extract_address(order) -> list[str]:
    raw = order.raw or {}
    sa = raw.get("shipping_address")
    if sa is None and isinstance(raw.get("order"), dict):
        sa = raw["order"].get("shipping_address")
    lines: list[str] = []
    if isinstance(sa, dict):
        name = sa.get("name") or " ".join(
            filter(None, [sa.get("first_name"), sa.get("last_name")])
        )
        if name:
            lines.append(name)
        for k in ("address1", "address2"):
            if sa.get(k):
                lines.append(sa[k])
        city = " ".join(filter(None, [sa.get("zip"), sa.get("city"), sa.get("province")]))
        if city:
            lines.append(city)
        if sa.get("country"):
            lines.append(sa["country"])
        if sa.get("phone"):
            lines.append("Tel: " + str(sa["phone"]))
    elif isinstance(sa, str):
        lines = [ln for ln in sa.splitlines() if ln.strip()]
    return lines


def _barkod_ciz(pg, code: str, m: float, y: float, w: float) -> float:
    """Code 128 çubuklarını çiz + altına kodu yaz. Dönüş: yeni y."""
    try:
        genislikler = barcode128.pattern_widths(code)
    except barcode128.BarcodeError:
        pg.insert_textbox(fitz.Rect(m, y, w - m, y + 20), "BARKOD URETILEMEDI",
                          fontsize=10, fontname="helv", align=1)
        return y + 24

    kullanilabilir = w - 2 * m
    sessiz = 10                       # her iki yanda 10 modül sessiz alan (standart)
    modul = kullanilabilir / (sum(genislikler) + 2 * sessiz)
    yukseklik = 1.5 * CM

    x = m + sessiz * modul
    bar = True                        # ilk eleman HER ZAMAN bar
    for g in genislikler:
        gen = g * modul
        if bar:
            pg.draw_rect(fitz.Rect(x, y, x + gen, y + yukseklik),
                         color=(0, 0, 0), fill=(0, 0, 0))
        x += gen
        bar = not bar

    y += yukseklik + 3
    # Kutu yüksekliği font boyutundan belirgin büyük olmalı — dar kutuda
    # PyMuPDF metni HİÇ yazmıyor (sessizce boş kalıyordu).
    pg.insert_textbox(fitz.Rect(m, y, w - m, y + 22), _a(code),
                      fontsize=12, fontname="hebo", align=1)
    return y + 22


def render_label_pdf(order, store_name: str | None = None,
                     barkod_kodu: str | None = None) -> bytes:
    """barkod_kodu verilirse siparişin kendi kodu YERİNE o basılır.

    Sürat DOĞRUDAN gönderilerinde Sürat barkod görselini döndürmüyor ama gerçek
    takip numarasını veriyor; o numara Sürat'ın sisteminde KAYITLI olduğu için
    Code128 olarak basıldığında şubede karşılığı vardır. (3 Ağustos'ta başarısız
    olan deneme, karşılığı OLMAYAN kendi kodumuzu basıyordu — bu o değil.)
    """
    w, h = 10 * CM, 15 * CM
    doc = fitz.open()
    pg = doc.new_page(width=w, height=h)
    m = 0.6 * CM

    def box(text, size, yy, height=None, align=0, bold=False):
        bh = height or size * 1.9
        rect = fitz.Rect(m, yy, w - m, yy + bh)
        pg.insert_textbox(rect, text, fontsize=size,
                          fontname="hebo" if bold else "helv", align=align)
        return rect.y1

    y = m
    y = box(_a(store_name or "BASKICI"), 16, y, bold=True)
    pg.draw_line(fitz.Point(m, y + 4), fitz.Point(w - m, y + 4))
    y += 12

    y = box("Siparis: " + _a(order.name or order.order_number or ""), 13, y, bold=True)
    y += 8

    y = box("ALICI", 8, y)
    addr = _extract_address(order) or [_a(order.customer_name or "—")]
    for line in addr:
        y = box(_a(line), 11, y)
    y += 12

    code = str(barkod_kodu or order.barkod_kodu or order.order_number or "").strip()
    if code:
        y = _barkod_ciz(pg, code, m, y, w)
    else:
        y = box("BARKOD YOK", 12, y, align=1, bold=True)

    box(_a(store_name or "BASKICI") + " - kargo etiketi", 7, y + 4, align=1)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()
