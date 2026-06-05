"""
Kalıp şablonu parser — kullanıcının yüklediği şablon PDF'inden 27 kutu
koordinatını otomatik okur.

Her kullanıcının kendi Illustrator çıktısı şablonu farklı kutu yerleşimine
sahip olabilir. Bu modül şablon PDF'indeki dikdörtgen çizimlerini bulur,
boyut filtresiyle gerçek slot kutularını ayıklar ve panel ile aynı sırada
(satır satır, üstten alta; satır içinde soldan sağa) döndürür.

Çıktı: pt cinsinden kutu listesi [{x0,y0,x1,y1,w,h}], sayfa boyutu, satır/sütun.
"""
from __future__ import annotations

import fitz  # PyMuPDF

CM_TO_PT = 28.3464567

# Slot kutusu boyut filtresi (pt) — telefon kılıfı kutusu makul aralığı
MIN_W, MAX_W = 100, 500
MIN_H, MAX_H = 250, 800
ROW_SNAP_TOL = 60  # aynı satır kabul toleransı (pt)


def parse_template(pdf_bytes: bytes) -> dict:
    """
    Şablon PDF'inden kutu koordinatlarını çıkar.

    Dönüş:
      {
        "page_w_pt", "page_h_pt", "page_w_cm", "page_h_cm",
        "box_count", "cols", "rows",
        "boxes": [{x0,y0,x1,y1,w,h} ...]  # panel sırası: üst-sol -> alt-sağ
      }
    Hata durumunda ValueError.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.page_count == 0:
        raise ValueError("Boş PDF")
    page = doc[0]
    pw, ph = page.rect.width, page.rect.height

    candidates = []
    for d in page.get_drawings():
        r = d.get("rect")
        if not r:
            continue
        w, h = r.width, r.height
        if MIN_W < w < MAX_W and MIN_H < h < MAX_H:
            candidates.append(fitz.Rect(r))

    doc.close()

    if not candidates:
        raise ValueError("Şablonda kutu bulunamadı (dikdörtgen çizim yok veya boyut filtresine takıldı)")

    # Yinelenenleri temizle (aynı konumda iç içe çizimler olabilir)
    uniq = []
    for r in candidates:
        dup = False
        for u in uniq:
            if abs(r.x0 - u.x0) < 5 and abs(r.y0 - u.y0) < 5 and abs(r.width - u.width) < 5:
                dup = True
                break
        if not dup:
            uniq.append(r)

    # Satır satır sırala: önce y'ye göre satırlara grupla, satır içinde x'e göre
    uniq.sort(key=lambda r: r.y0)
    rows = []
    cur_row = []
    cur_y = None
    for r in uniq:
        if cur_y is None or abs(r.y0 - cur_y) <= ROW_SNAP_TOL:
            cur_row.append(r)
            cur_y = r.y0 if cur_y is None else cur_y
        else:
            rows.append(cur_row)
            cur_row = [r]
            cur_y = r.y0
    if cur_row:
        rows.append(cur_row)

    ordered = []
    for row in rows:
        row.sort(key=lambda r: r.x0)  # soldan sağa
        ordered.extend(row)

    cols = max((len(row) for row in rows), default=0)
    boxes = [{
        "x0": round(r.x0, 2), "y0": round(r.y0, 2),
        "x1": round(r.x1, 2), "y1": round(r.y1, 2),
        "w": round(r.width, 2), "h": round(r.height, 2),
    } for r in ordered]

    return {
        "page_w_pt": round(pw, 2), "page_h_pt": round(ph, 2),
        "page_w_cm": round(pw / CM_TO_PT, 2), "page_h_cm": round(ph / CM_TO_PT, 2),
        "box_count": len(boxes),
        "cols": cols,
        "rows": len(rows),
        "boxes": boxes,
    }
