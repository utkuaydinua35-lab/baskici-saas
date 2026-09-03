"""Telefon modeli ölçüsü değişince kalıp PDF'i BAYAT KALMAMALI.

Ölçü kalıp kaydında saklanmıyor, PDF üretilirken DB'den okunuyor; ve PDF
önbellek anahtarı ölçüyü de karıyor. Yani ölçü değişince eski PDF yeniden
KULLANILAMAZ hale gelir — kalıbı silip yeniden oluşturmaya gerek yoktur.
Bu testin işi o zinciri kanıtlamak.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import PhoneModel, Tenant  # noqa: E402
from app.services import mold_pdf_job as job, phone_models as pm  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:5].upper()
MODEL = f"Samsung Galaxy S{IZ}FE"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


class _SahteKalip:
    id = uuid.uuid4()


SABLON = {"page_w_pt": 1000, "page_h_pt": 700,
          "boxes": [{"x0": 0, "y0": 0, "x": 0, "y": 0, "w": 400, "h": 700}]}

db = SessionLocal()
tenant = db.scalar(select(Tenant).order_by(Tenant.created_at).limit(1))
key = pm.normalize_key(MODEL)
db.add(PhoneModel(tenant_id=tenant.id, spec_key=key, display_name=MODEL,
                  width_cm=7.6, height_cm=16.0, radius_cm=1.0, is_active=True))
db.commit()


def anahtar():
    """PDF üretiminin yaptığının aynısı: ölçüyü DB'den TAZE oku, anahtarı üret."""
    kalemler = [{"slot_index": 1, "model": MODEL,
                 "spec": pm.get_spec(db, tenant.id, MODEL),
                 "design_file_path": "x/a.pdf"}]
    return job.anahtar_uret(_SahteKalip, kalemler, SABLON)


print("\n── 1. ölçü DEĞİŞMEDEN anahtar sabit ──")
a1 = anahtar()
es("aynı ölçü → aynı anahtar", a1, anahtar())

print("\n── 2. ölçü DEĞİŞİNCE anahtar da değişir ──")
m = db.scalar(select(PhoneModel).where(PhoneModel.tenant_id == tenant.id,
                                       PhoneModel.spec_key == key))
m.width_cm = 7.9
db.commit(); db.expire_all()
a2 = anahtar()
es("ölçü DB'den taze okundu", (7.9, 16.0, 1.0), pm.get_spec(db, tenant.id, MODEL))
es("anahtar DEĞİŞTİ (eski PDF kullanılamaz)", True, a1 != a2)

print("\n── 3. yalnız köşe yarıçapı değişse bile ──")
m.radius_cm = 1.4
db.commit(); db.expire_all()
es("anahtar yine değişti", True, anahtar() not in (a1, a2))

print("\n── 4. eski ölçüye dönülürse eski anahtar geri gelir ──")
m.width_cm, m.radius_cm = 7.6, 1.0
db.commit(); db.expire_all()
es("ilk anahtara dönüldü", a1, anahtar())

print("\n── 5. hazır PDF durumu: yeni anahtarda 'yok' döner ──")
es("olmayan anahtar için durum 'yok'", "yok",
   job.durum(_SahteKalip.id, "olmayan-anahtar-" + IZ)["durum"])

db.execute(text("delete from phone_models where spec_key=:k"), {"k": key})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
