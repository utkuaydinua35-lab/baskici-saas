"""Yavaş PDF'in HANGİ adımı pahalı + kayıp tasarım dosyası taraması.

Kullanım:
    cd ~/baskici-saas/backend && .venv/bin/python scripts/kalip_pdf_tani2.py [KALIP_KODU]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402
from sqlalchemy import desc, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Design, Mold  # noqa: E402
from app.services import mold_pdf as MP  # noqa: E402


def adim_adim(yol: Path, w_pt: float, h_pt: float) -> None:
    """_make_clipped_design'in adımlarını ayrı ayrı ölç."""
    t0 = time.time()
    src = fitz.open(str(yol))
    t_open = time.time() - t0

    sayfa = src[0]
    gorseller = sayfa.get_images(full=True)
    bilgi = []
    for g in gorseller[:4]:
        try:
            px = src.extract_image(g[0])
            bilgi.append(f"{px['width']}x{px['height']} {px['ext']}"
                         f" {len(px['image'])/1024/1024:.1f}MB")
        except Exception:  # noqa: BLE001
            bilgi.append("okunamadi")

    tmp = fitz.open()
    pg = tmp.new_page(width=w_pt, height=h_pt)
    t0 = time.time()
    pg.show_pdf_page(pg.rect, src, 0, keep_proportion=False)
    t_show = time.time() - t0

    t0 = time.time()
    out1 = tmp.tobytes(garbage=4, deflate=True)
    t_gc4 = time.time() - t0

    tmp2 = fitz.open()
    pg2 = tmp2.new_page(width=w_pt, height=h_pt)
    pg2.show_pdf_page(pg2.rect, src, 0, keep_proportion=False)
    t0 = time.time()
    out2 = tmp2.tobytes(garbage=0, deflate=False)
    t_ham = time.time() - t0

    src.close(); tmp.close(); tmp2.close()
    print(f"      sayfa gorselleri : {bilgi or 'yok'}")
    print(f"      acma             : {t_open:6.2f} sn")
    print(f"      show_pdf_page    : {t_show:6.2f} sn")
    print(f"      tobytes(gc=4,def): {t_gc4:6.2f} sn  -> {len(out1)/1024/1024:.1f} MB")
    print(f"      tobytes(ham)     : {t_ham:6.2f} sn  -> {len(out2)/1024/1024:.1f} MB")


def main() -> None:
    kod = sys.argv[1] if len(sys.argv) > 1 else None
    db = SessionLocal()
    try:
        q = select(Mold).order_by(desc(Mold.created_at))
        if kod:
            q = select(Mold).where(Mold.kod == kod)
        mo = db.scalar(q)
        if mo:
            print(f"── {mo.kod}: yavaş slotların adım dökümü ──")
            dids = {it.design_id for it in mo.items if it.design_id}
            dmap = {d.id: d for d in db.scalars(
                select(Design).where(Design.id.in_(dids))).all()} if dids else {}
            w_pt, h_pt = 7.9 / 2.54 * 72, 17.0 / 2.54 * 72
            for it in mo.items:
                d = dmap.get(it.design_id)
                if not d or not d.file_path or (d.file_format or "").lower() != "pdf":
                    continue
                p = MP._abs_path(d.file_path)
                if not p.exists() or p.stat().st_size < 5 * 1024 * 1024:
                    continue
                print(f"\n  slot {it.slot_index} · {p.stat().st_size/1024/1024:.1f} MB")
                adim_adim(p, w_pt, h_pt)

        print("\n\n── Kayıp tasarım dosyası taraması (tüm sistem) ──")
        tum = db.scalars(select(Design)).all()
        yok, var, bos = [], 0, 0
        for d in tum:
            if not d.file_path:
                bos += 1
                continue
            if MP._abs_path(d.file_path).exists():
                var += 1
            else:
                yok.append(d)
        print(f"  toplam tasarım : {len(tum)}")
        print(f"  dosyası var    : {var}")
        print(f"  dosyası YOK    : {len(yok)}")
        print(f"  yolu boş       : {bos}")
        if yok:
            print("\n  ilk 10 kayıp:")
            for d in yok[:10]:
                print(f"    {str(d.code)[:18]:<20} {str(d.file_format):<5}"
                      f" {str(d.created_at)[:10]}  {str(d.file_path)[:60]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
