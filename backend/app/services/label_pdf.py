"""
Basit kargo etiketi PDF'i (placeholder — Paket: Paketleme).

Gerçek kargo entegrasyonu (Sürat/Yurtiçi API, taranabilir barkod, takip no)
"Kargo paketi"nde gelecek. Şimdilik: mağaza adı + sipariş no + alıcı adresi +
barkod değeri (metin). PyMuPDF base14 fontu Türkçe ş/ğ/İ desteklemediği için
metin ASCII'ye çevrilir (kargo için yeterli; gerçek font embed (c)'de).
"""
from __future__ import annotations

import io

import fitz  # PyMuPDF

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


def render_label_pdf(order, store_name: str | None = None) -> bytes:
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

    code = order.barkod_kodu or order.order_number or ""
    pg.draw_rect(fitz.Rect(m, y, w - m, y + 1.4 * CM))
    box("*" + _a(code) + "*", 18, y + 0.32 * CM, align=1, bold=True)
    y += 1.4 * CM + 8

    box("Baskici paneli - kargo etiketi (placeholder)", 7, y, align=1)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()
