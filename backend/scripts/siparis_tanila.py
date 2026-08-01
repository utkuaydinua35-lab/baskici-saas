"""Bir siparişin kalıp/planlama durumunu tam dök — neden planlanıyor/planlanmıyor.

Kullanım (VPS, baskici kullanıcısı):
    cd ~/baskici-saas/backend && .venv/bin/python scripts/siparis_tanila.py 11437
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    CoupleProduct, Design, KisiyeOzelProduct, LineItem, Mold, MoldItem, Order,
)


def main() -> None:
    if len(sys.argv) < 2:
        print("Kullanım: siparis_tanila.py <siparis_no>")
        return
    onum = sys.argv[1].strip().lstrip("#")
    db = SessionLocal()
    try:
        orders = db.scalars(select(Order).where(Order.order_number == onum)).all()
        if not orders:
            print(f"Sipariş {onum} bulunamadı")
            return
        for o in orders:
            print(f"═══ Sipariş {o.name or onum}  (id={o.id})")
            print(f"    aşama={o.current_stage}  iptal={o.is_iptal}  "
                  f"fulfillment={o.fulfillment_status}  kalip_haric={o.kalip_haric}")
            lis = db.scalars(
                select(LineItem).where(LineItem.order_id == o.id)
                .order_by(LineItem.position)
            ).all()
            for li in lis:
                pid = str(li.product_id) if li.product_id else None
                cp = db.scalar(select(CoupleProduct).where(
                    CoupleProduct.product_id == pid)) if pid else None
                ko = db.scalar(select(KisiyeOzelProduct).where(
                    KisiyeOzelProduct.product_id == pid)) if pid else None
                print(f"\n  ── KALEM {li.title[:52]!r}")
                print(f"     line_item_id = {li.id}")
                print(f"     external_id  = {li.external_id}   adet={li.quantity}")
                print(f"     couple={'EVET' if cp else 'hayır'}"
                      f"{' (kişiye özel)' if cp and cp.is_kisiye_ozel else ''}"
                      f"   kisiye_ozel_urun={'EVET' if ko else 'hayır'}")
                print(f"     bayraklar: kaliba_eklendi={li.is_kaliba_eklendi} "
                      f"hazir={li.is_hazir} hazir_2={getattr(li, 'is_hazir_2', None)}")
                print(f"     model1={li.device_model_override!r}  model2={li.device_model_override_2!r}")
                print(f"     varyasyon1={li.kilif_varyasyon!r}  varyasyon2={li.kilif_varyasyon_2!r}")
                print(f"     assigned_design_id  = {li.assigned_design_id}")
                print(f"     assigned_design_id_2= {li.assigned_design_id_2}")
                if cp:
                    print(f"     CoupleProduct.design_id_1 = {cp.design_id_1}")
                    print(f"     CoupleProduct.design_id_2 = {cp.design_id_2}")
                    # Planlayicinin kullanacagi GERCEK slot tasarimlari
                    if cp.is_kisiye_ozel:
                        d1, d2 = li.assigned_design_id, li.assigned_design_id_2
                    else:
                        d1, d2 = cp.design_id_1, cp.design_id_2
                    print(f"     -> planlayıcının slot tasarımları: d1={d1}  d2={d2}")

                mis = db.execute(
                    select(MoldItem, Mold.kod, Mold.current_stage, Mold.print_status)
                    .join(Mold, Mold.id == MoldItem.mold_id)
                    .where(MoldItem.order_number == str(onum))
                ).all()
                mine = [x for x in mis if x[0].line_item_id == li.id]
                print(f"     KALIP SLOTLARI (bu kaleme bağlı): {len(mine)}")
                for mi, kod, stage, pstat in mine:
                    print(f"        {kod:12} slot#{mi.slot_index:<3} design_id={mi.design_id} "
                          f"model={mi.model!r} stage={stage} print={pstat}")
                bagsiz = [x for x in mis if x[0].line_item_id is None]
                if bagsiz:
                    print(f"     ⚠ BAĞI KOPUK slot ({len(bagsiz)}) — line_item_id NULL:")
                    for mi, kod, stage, pstat in bagsiz:
                        print(f"        {kod:12} slot#{mi.slot_index:<3} design_id={mi.design_id} "
                              f"model={mi.model!r} design_code={mi.design_code!r}")
                baska = [x for x in mis if x[0].line_item_id not in (None, li.id)]
                if baska:
                    print(f"     (bu siparişin diğer kalemlerine bağlı slot: {len(baska)})")
            print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
