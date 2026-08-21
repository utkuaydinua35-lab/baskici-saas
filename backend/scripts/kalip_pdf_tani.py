"""Kalıp PDF üretimi neden yavaş — slot slot ölçüm. HİÇBİR ŞEY DEĞİŞTİRMEZ.

Kullanım (VPS, baskici kullanıcısı):
    cd ~/baskici-saas/backend && .venv/bin/python scripts/kalip_pdf_tani.py [KALIP_KODU]

Kod verilmezse en son oluşturulan kalıp ölçülür.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Design, Mold, MoldTemplate  # noqa: E402
from app.services import mold_pdf as MP  # noqa: E402
from app.services import phone_models as pm  # noqa: E402


def main() -> None:
    kod = sys.argv[1] if len(sys.argv) > 1 else None
    db = SessionLocal()
    try:
        q = select(Mold).order_by(desc(Mold.created_at))
        if kod:
            q = select(Mold).where(Mold.kod == kod)
        mo = db.scalar(q)
        if not mo:
            print("Kalıp bulunamadı.")
            return
        print(f"Kalıp: {mo.kod} · {len(mo.items)} kalem · varyasyon={mo.variation}\n")

        dmap = {}
        dids = {it.design_id for it in mo.items if it.design_id}
        if dids:
            for d in db.scalars(select(Design).where(Design.id.in_(dids))).all():
                dmap[d.id] = d

        tpl = db.scalar(select(MoldTemplate).where(
            MoldTemplate.tenant_id == mo.tenant_id,
            MoldTemplate.is_active == True).order_by(desc(MoldTemplate.created_at)))  # noqa: E712
        if not tpl or not tpl.boxes:
            print("Aktif kalıp şablonu yok.")
            return

        slot_items = []
        print("── Slot slot kaynak dosyalar ──")
        for it in mo.items:
            d = dmap.get(it.design_id)
            boyut = 0
            if d and d.file_path:
                p = MP._abs_path(d.file_path)
                boyut = p.stat().st_size if p.exists() else -1
            print(f"  slot {str(it.slot_index):>2}  {str(it.model)[:22]:<24}"
                  f" {str(d.file_format if d else '—'):<5}"
                  f" {boyut/1024/1024:7.1f} MB" + ("  ← DOSYA YOK" if boyut < 0 else ""))
            slot_items.append({
                "slot_index": it.slot_index, "kalip_kodu": it.kalip_kodu,
                "model": it.model,
                "spec": pm.get_spec(db, mo.tenant_id, it.model or ""),
                "design_file_path": d.file_path if d else None,
                "design_format": d.file_format if d else None,
            })

        template = {"page_w_pt": tpl.page_w_pt, "page_h_pt": tpl.page_h_pt,
                    "cols": tpl.cols, "rows": tpl.rows, "boxes": tpl.boxes}

        # Slot başına süre — hangi kalem pahalı, tek tek görünsün
        print("\n── Slot başına üretim süresi ──")
        toplam = 0.0
        for si in slot_items:
            t = time.time()
            try:
                MP.render_mold_pdf([si], template)
            except Exception as e:  # noqa: BLE001
                print(f"  slot {si['slot_index']}: HATA {str(e)[:60]}")
                continue
            sure = time.time() - t
            toplam += sure
            isaret = "  ← YAVAŞ" if sure > 3 else ""
            print(f"  slot {str(si['slot_index']):>2}  {str(si['model'])[:22]:<24}"
                  f" {str(si['design_format']):<5} {sure:6.2f} sn{isaret}")

        print(f"\n  slotların toplamı: {toplam:.1f} sn")

        print("\n── Tam kalıp (gerçek akış) ──")
        t = time.time()
        pdf, bilgi = MP.render_mold_pdf(slot_items, template)
        sure = time.time() - t
        print(f"  süre        : {sure:.1f} sn")
        print(f"  çıktı       : {len(pdf)/1024/1024:.1f} MB")
        print(f"  yerleşen    : {bilgi['placed']}/{bilgi['total']}")
        if bilgi["skipped"]:
            print(f"  atlanan     : {bilgi['skipped_count']}")
            for s in bilgi["skipped"][:5]:
                print(f"     slot {s.get('slot')}: {s.get('reason')}")

        print("\n" + "=" * 58)
        print("KARAR")
        if sure > 60:
            print(f"  {sure:.0f} sn — Cloudflare 100 sn'de vazgeçiyor, 524 buradan.")
        elif sure > 20:
            print(f"  {sure:.0f} sn — sınırda; ağır slotlar yukarıda işaretli.")
        else:
            print(f"  {sure:.0f} sn — üretim hızlı. Sorun PDF üretiminde DEĞİL,")
            print("  aktarımda ya da başka bir katmanda.")
        print("=" * 58)
    finally:
        db.close()


if __name__ == "__main__":
    main()
