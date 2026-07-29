"""Kalıp slotlarının ölçü eşleşmesini denetle.

Neden: marka soyma kuralı bir süre fazla gevşekti ve 'REDMI-12' gibi bir anahtar
'12'ye kadar soyulup Apple takma adına (iPhone 12) düşebiliyordu — ürün YANLIŞ
ÖLÇÜYLE basılıyordu. Bu betik her kalıp slotunun modelini bugünkü (düzeltilmiş)
kurala göre yeniden çözer ve şüpheli olanları listeler.

Kullanım (VPS, baskici kullanıcısı):
    cd ~/baskici-saas/backend && .venv/bin/python scripts/kalip_olcu_denetim.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Mold, MoldItem  # noqa: E402
from app.services import phone_models as pm  # noqa: E402

APPLE_OLCU_ESIGI = 0.15  # cm — bu kadar farklıysa "başka telefon" say


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Mold.kod, Mold.tenant_id, Mold.current_stage,
                   MoldItem.model, MoldItem.order_number, MoldItem.slot_index)
            .join(MoldItem, MoldItem.mold_id == Mold.id)
            .order_by(Mold.kod, MoldItem.slot_index)
        ).all()

        cozulemeyen: list = []
        apple_supheli: list = []
        toplam = 0

        for kod, tid, stage, model, onum, slot in rows:
            toplam += 1
            if not model:
                continue
            spec = pm.get_spec(db, tid, model)
            key = pm.normalize_key(model)
            if spec is None:
                cozulemeyen.append((kod, slot, onum, model, key))
                continue
            # Apple olmayan bir model, bir iPhone ölçüsüne mi denk geliyor?
            if not key.startswith("IPHONE") and not pm.is_apple_alias_key(key):
                parcalar = [p for p in key.split("-") if p]
                if len(parcalar) > 1 and pm.is_apple_alias_key("-".join(parcalar[1:])):
                    iph = pm.get_spec(db, tid, "IPHONE-" + "-".join(parcalar[1:]))
                    if iph and abs(iph[0] - spec[0]) < APPLE_OLCU_ESIGI \
                            and abs(iph[1] - spec[1]) < APPLE_OLCU_ESIGI:
                        apple_supheli.append((kod, slot, onum, model, key, spec))

        print(f"Toplam kalıp slotu: {toplam}\n")

        print(f"[1] Ölçüsü ÇÖZÜLEMEYEN slotlar ({len(cozulemeyen)}) — PDF bunları reddeder:")
        for kod, slot, onum, model, key in cozulemeyen:
            print(f"    {kod:14} slot {slot:>2}  sipariş {str(onum):>8}  '{model}'  -> anahtar {key}")
        if not cozulemeyen:
            print("    yok")

        print(f"\n[2] iPhone ölçüsüne düşmüş ŞÜPHELİ slotlar ({len(apple_supheli)}) — KONTROL ET:")
        for kod, slot, onum, model, key, spec in apple_supheli:
            print(f"    {kod:14} slot {slot:>2}  sipariş {str(onum):>8}  '{model}'  -> {spec}")
        if not apple_supheli:
            print("    yok")
    finally:
        db.close()


if __name__ == "__main__":
    main()
