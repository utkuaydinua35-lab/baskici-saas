"""Birikmiş MÜKERRER tasarım dosyalarını raporla — HİÇBİR ŞEY DEĞİŞTİRMEZ.

Sadece okur ve yazdırır. Silme/birleştirme yapmaz; karar kullanıcınındır.
Eşleştirme, dedup mantığının aynısı: aynı mağaza + aynı boyut + aynı SHA-256
+ BAYT BAYT doğrulama.
"""
from __future__ import annotations

import hashlib
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Design, LineItem, Store  # noqa: E402
from app.services import storage  # noqa: E402


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


db = SessionLocal()
magazalar = {s.id: s.name for s in db.scalars(select(Store)).all()}
tasarimlar = db.scalars(select(Design).order_by(Design.created_at.asc())).all()
print(f"Toplam tasarım kaydı: {len(tasarimlar)}")

gruplar: dict[tuple, list] = defaultdict(list)
okunamayan = 0
toplam_bayt = 0
for d in tasarimlar:
    veri = storage.read_design_file(d.file_path)
    if veri is None:
        okunamayan += 1
        continue
    toplam_bayt += len(veri)
    gruplar[(d.store_id, len(veri), hashlib.sha256(veri).hexdigest())].append((d, veri))

print(f"Diskte bulunamayan dosya: {okunamayan}")
print(f"Diskteki toplam tasarım boyutu: {mb(toplam_bayt)}\n")

israf = 0
kopya_sayisi = 0
satirlar = []
for (store_id, _boyut, _h), uyeler in gruplar.items():
    if len(uyeler) < 2:
        continue
    # BAYT BAYT dogrula — hash'e tek basina guvenme
    ilk_veri = uyeler[0][1]
    gercek = [u for u in uyeler if u[1] == ilk_veri]
    if len(gercek) < 2:
        continue
    fazla = len(gercek) - 1
    kopya_sayisi += fazla
    israf += fazla * len(ilk_veri)
    kullanim = []
    for d, _ in gercek:
        n = db.scalar(select(__import__("sqlalchemy").func.count())
                      .select_from(LineItem)
                      .where(LineItem.assigned_design_id == d.id)) or 0
        kullanim.append(f"{d.code}({n} kalem)")
    satirlar.append((fazla * len(ilk_veri), magazalar.get(store_id, "?"),
                     mb(len(ilk_veri)), fazla, kullanim))

satirlar.sort(reverse=True)
if not satirlar:
    print("Mükerrer dosya YOK.")
else:
    print(f"{'mağaza':22} {'dosya':>9} {'fazla':>6}  kayıtlar")
    print("-" * 78)
    for _, magaza, boyut, fazla, kullanim in satirlar[:25]:
        print(f"{magaza[:20]:22} {boyut:>9} {fazla:>6}  {', '.join(kullanim)[:60]}")
    if len(satirlar) > 25:
        print(f"… ve {len(satirlar) - 25} grup daha")

print(f"\nFAZLADAN duran kopya: {kopya_sayisi} dosya · {mb(israf)}")
print("\nBu betik HİÇBİR ŞEY DEĞİŞTİRMEDİ. Hiç kalemde kullanılmayan (0 kalem)")
print("kopyalar güvenle silinebilir; kullanımda olanlar için önce siparişler")
print("aynı tasarıma bağlanmalı.")
