"""
Kalıp PDF render motoru v7 — kullanıcının şablon kutularına KALICI vektör clip ile basar.

jsx (bernz_unified_script_v5) mantığı birebir:
- Tasarım, modelin gerçek kılıf ölçüsünde (gizli MODEL_SPECS, -trim), şablon
  kutusunun SAĞ-ALT köşesine yaslanır.
- Köşe yuvarlatma: her tasarım, kendi yuvarlak-dikdörtgen clip path'iyle (W n)
  geçici sayfada hazırlanır, KALICI hale getirilip (tobytes -> tekrar aç) ana
  tablaya gömülür. Böylece çoklu slotta frame-eşleşme kayması OLMAZ; her tasarım
  bağımsız clip'lenir. Köşeler pürüzsüz vektör, modelin radius'u kadar.
- radius=0 modeller (S23/S24 Ultra vb.) keskin kalır.
- Beyaz zemin YOK -> boş alan ve köşe payları şeffaf (basılmaz, boya maliyeti yok).

Gizli ölçü modülü yalnızca burada okunur; ölçüler API'den dışa verilmez.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import fitz  # PyMuPDF

from app.services._private import case_dimensions as cd
from app.services.storage import STORAGE_ROOT

CM_TO_PT = 28.3464567


def _abs_path(relative_path: str) -> Path:
    return STORAGE_ROOT / relative_path


def _ordered_slots(items, cols, rows):
    """Panel düzeniyle aynı sıra: gruplar kendi satır(lar)ında, sağa yaslı."""
    order = []
    by_kod = {}
    for it in items:
        kod = it.get("kalip_kodu") or it.get("kod") or "?"
        if kod not in by_kod:
            by_kod[kod] = []
            order.append(kod)
        by_kod[kod].append(it)

    grid_rows = []
    for kod in order:
        g = by_kod[kod]
        for i in range(0, len(g), cols):
            grid_rows.append(g[i:i + cols])
    while len(grid_rows) < rows:
        grid_rows.append([])

    slots = []
    for r in range(rows):
        row = grid_rows[r] if r < len(grid_rows) else []
        pad = [None] * max(0, cols - len(row)) + list(row)
        slots.extend(pad[:cols])
    return slots[:cols * rows]


def _placement_rect(box, model):
    """Şablon kutusu içinde modelin gerçek kılıf ölçüsünde rect + radius_pt.
    Tasarım kutunun SAĞ-ALT köşesine yaslanır. Dönüş: (fitz.Rect, radius_pt) | None."""
    spec = cd.get_spec(model)
    if not spec:
        return None
    w_cm, h_cm, r_cm = spec
    # TRIM kaldırıldı: gerçek kılıf ölçüsünde basılır (8.0 × 16.25 gibi).
    w_pt = max(0.0, w_cm) * CM_TO_PT
    h_pt = max(0.0, h_cm) * CM_TO_PT
    bw, bh = box["w"], box["h"]
    scale = min(1.0, bw / w_pt if w_pt else 1.0, bh / h_pt if h_pt else 1.0)
    w_pt *= scale
    h_pt *= scale
    r_pt = r_cm * CM_TO_PT * scale
    x1 = box["x0"] + bw
    y1 = box["y0"] + bh
    rect = fitz.Rect(x1 - w_pt, y1 - h_pt, x1, y1)
    return rect, r_pt


def _make_clipped_design(src_path, w_pt, h_pt, radius):
    """Tasarımı w×h tek sayfaya koy, yuvarlak köşe VEKTÖR clip uygula, KALICI
    hale getir (tobytes). Dönüş: pdf bytes. Köşe payı şeffaf, pürüzsüz."""
    tmp = fitz.open()
    pg = tmp.new_page(width=w_pt, height=h_pt)
    src = fitz.open(str(src_path))
    # keep_proportion=False: tasarım rect'i tam doldurur, alt/üst boşluk olmaz
    # (oran sapması olsa bile clip alanını tam kaplar). Aksi halde yuvarlak clip'imiz
    # dış katmanda kalır, tasarım iç katmanda kayıp, "alt birden bitiyor" hatası olur.
    pg.show_pdf_page(pg.rect, src, 0, keep_proportion=False)
    src.close()

    if radius > 0:
        rr = min(radius, w_pt / 2, h_pt / 2)
        k = 0.5523 * rr  # bezier kappa = matematiksel çeyrek daire
        x0, x1 = 0.0, w_pt
        pb, pt = 0.0, h_pt  # PDF: alt=0, üst=h_pt (bu sayfa için)
        ops = (
            f"{x0+rr:.3f} {pb:.3f} m {x1-rr:.3f} {pb:.3f} l "
            f"{x1-rr+k:.3f} {pb:.3f} {x1:.3f} {pb+rr-k:.3f} {x1:.3f} {pb+rr:.3f} c "
            f"{x1:.3f} {pt-rr:.3f} l {x1:.3f} {pt-rr+k:.3f} {x1-rr+k:.3f} {pt:.3f} {x1-rr:.3f} {pt:.3f} c "
            f"{x0+rr:.3f} {pt:.3f} l {x0+rr-k:.3f} {pt:.3f} {x0:.3f} {pt-rr+k:.3f} {x0:.3f} {pt-rr:.3f} c "
            f"{x0:.3f} {pb+rr:.3f} l {x0:.3f} {pb+rr-k:.3f} {x0+rr-k:.3f} {pb:.3f} {x0+rr:.3f} {pb:.3f} c h W n "
        )
        xref = pg.get_contents()[0]
        c = tmp.xref_stream(xref).decode("latin-1")
        m = re.search(r" q /fzFrm\d+ Do Q", c)
        if m:
            ins = m.start() + len(" q ")
            c = c[:ins] + ops + c[ins:]
            tmp.update_stream(xref, c.encode("latin-1"))

    out = tmp.tobytes(garbage=4, deflate=True)  # clip KALICI
    tmp.close()
    return out


def render_mold_pdf(mold_items, template=None):
    """
    Kalıp slotlarından baskıya hazır PDF üret. Kalıcı vektör clip ile pürüzsüz
    yuvarlak köşe (modelin radius'u kadar), şeffaf zemin.
    template: {page_w_pt, page_h_pt, cols, rows, boxes:[...]}.
    """
    if not template or not template.get("boxes"):
        raise ValueError("Kalıp şablonu tanımlı değil — önce şablon yükleyin")

    page_w = template["page_w_pt"]
    page_h = template["page_h_pt"]
    cols = template.get("cols") or 9
    rows = template.get("rows") or 3
    boxes = template["boxes"]

    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)
    # BEYAZ ZEMİN YOK — boş alan şeffaf

    placed = 0
    skipped = []
    slots = _ordered_slots(mold_items, cols, rows)

    for idx, it in enumerate(slots):
        if it is None:
            continue
        if idx >= len(boxes):
            skipped.append({"slot": idx, "reason": "sablon_kutu_yetersiz"})
            continue
        box = boxes[idx]
        model = it.get("model")
        rel = it.get("design_file_path")
        fmt = (it.get("design_format") or "").lower()

        pr = _placement_rect(box, model or "")
        if pr is None:
            skipped.append({"slot": idx, "model": model, "reason": "olcu_yok"})
            continue
        rect, radius = pr

        if not rel:
            skipped.append({"slot": idx, "model": model, "reason": "tasarim_dosyasi_yok"})
            continue
        path = _abs_path(rel)
        if not path.exists():
            skipped.append({"slot": idx, "model": model, "reason": "dosya_bulunamadi"})
            continue

        try:
            if fmt == "pdf":
                clipped_bytes = _make_clipped_design(path, rect.width, rect.height, radius)
                clipped = fitz.open(stream=clipped_bytes, filetype="pdf")
                page.show_pdf_page(rect, clipped, 0)
                clipped.close()
            else:
                page.insert_image(rect, filename=str(path))
            placed += 1
        except Exception as e:
            skipped.append({"slot": idx, "model": model, "reason": f"yerlestirme_hatasi: {e}"})

    buf = io.BytesIO()
    doc.save(buf, deflate=True)
    doc.close()
    return buf.getvalue(), {
        "placed": placed,
        "skipped": skipped,
        "skipped_count": len(skipped),
        "total": sum(1 for s in slots if s is not None),
        "page_cm": [round(page_w / CM_TO_PT, 1), round(page_h / CM_TO_PT, 1)],
        "grid": [cols, rows],
    }
