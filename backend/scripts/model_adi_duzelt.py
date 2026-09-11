"""Mevcut sipariş kalemlerindeki HAM model adlarını okunur ada çevirir.

    .venv/bin/python scripts/model_adi_duzelt.py            # KURU: yalnız listeler
    .venv/bin/python scripts/model_adi_duzelt.py --uygula   # yazar

Yeni kayıtlar zaten okunur adla yazılıyor (phone_models.gorunen_ad); bu betik
geçmişe dönük temizlik içindir. Kural aynı: ad YALNIZ kalıp ölçüsü birebir aynı
kalıyorsa değişir — "A57" gibi tenant'a özel ya da ölçüsü bulunamayan değerlere
dokunulmaz.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import LineItem  # noqa: E402
from app.services.phone_models import gorunen_ad  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true", help="değişiklikleri YAZ")
    arg = ap.parse_args()

    db = SessionLocal()
    satirlar = db.execute(
        select(LineItem.id, LineItem.tenant_id,
               LineItem.device_model_override, LineItem.device_model_override_2)
        .where(or_(LineItem.device_model_override.isnot(None),
                   LineItem.device_model_override_2.isnot(None)))
    ).all()

    onbellek: dict = {}
    degisim: list[tuple] = []
    for kid, tid, v1, v2 in satirlar:
        for alan, v in (("device_model_override", v1), ("device_model_override_2", v2)):
            if not v:
                continue
            yeni = onbellek.setdefault((tid, v), gorunen_ad(db, tid, v))
            if yeni and yeni != v:
                degisim.append((kid, alan, v, yeni))

    ozet = collections.Counter((v, y) for _, _, v, y in degisim)
    print(f"taranan kalem: {len(satirlar)} · değişecek alan: {len(degisim)}")
    for (v, y), n in ozet.most_common():
        print(f"  {v!r:>22} → {y!r:<24} ({n})")

    if not arg.uygula:
        print("\nKURU ÇALIŞMA — hiçbir şey yazılmadı. Yazmak için --uygula ekleyin.")
        return 0
    for kid, alan, _v, yeni in degisim:
        li = db.get(LineItem, kid)
        setattr(li, alan, yeni)
    db.commit()
    print(f"\n{len(degisim)} alan güncellendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
