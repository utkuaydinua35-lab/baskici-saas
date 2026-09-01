"""Mükerrer tasarım tespiti — YANLIŞ EŞLEŞME OLMAMALI.

Yanlış eşleşme, müşteriye YANLIŞ TASARIM basılması demektir. Bu yüzden testler
ağırlıklı olarak "eşleşmemesi gereken" durumları sınar.
"""
from __future__ import annotations

import hashlib
import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import UploadFile  # noqa: E402
from sqlalchemy import func as sqlfunc, select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Dealer, Design, Store, Tenant  # noqa: E402
from app.routers import bayii_portal as bp  # noqa: E402
from app.services import storage  # noqa: E402

GECTI = KALDI = 0
IZ = f"dd{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


def _yukle(veri: bytes, ad="test.jpg") -> UploadFile:
    return UploadFile(filename=ad, file=io.BytesIO(veri))


db = SessionLocal()
tenant = db.scalar(select(Tenant).order_by(Tenant.created_at).limit(1))
s1 = Store(tenant_id=tenant.id, slug=f"{IZ}-a", name="Bayi A", platform="bayii", is_active=True)
s2 = Store(tenant_id=tenant.id, slug=f"{IZ}-b", name="Bayi B", platform="bayii", is_active=True)
db.add_all([s1, s2]); db.flush()
d1 = Dealer(tenant_id=tenant.id, store_id=s1.id, name=f"{IZ}-A", is_active=True)
d2 = Dealer(tenant_id=tenant.id, store_id=s2.id, name=f"{IZ}-B", is_active=True)
db.add_all([d1, d2]); db.commit()

# Gercek bir JPG'e benzesin diye JPEG imzasi + rastgele govde
A = b"\xff\xd8\xff\xe0" + b"AAAA" * 300 + b"\xff\xd9"
B = b"\xff\xd8\xff\xe0" + b"BBBB" * 300 + b"\xff\xd9"     # AYNI BOYUT, farkli icerik
assert len(A) == len(B)

print("\n── 1. aynı dosya ikinci kez → YENİ DOSYA YAZILMAZ ──")
t1 = bp._tasarim_kaydet(db, d1, _yukle(A), "ilk"); db.commit()
es("hash yazıldı", hashlib.sha256(A).hexdigest(), t1.icerik_hash)
es("ilk yükleme yeniden kullanım DEĞİL", False, getattr(t1, "_yeniden_kullanildi", False))
t2 = bp._tasarim_kaydet(db, d1, _yukle(A), "ikinci"); db.commit()
es("AYNI kayıt döndü", t1.id, t2.id)
es("yeniden kullanıldı işaretli", True, getattr(t2, "_yeniden_kullanildi", False))
es("mağazada tek tasarım var", 1, db.scalar(select(sqlfunc.count()).select_from(Design)
                     .where(Design.store_id == s1.id)))

print("\n── 2. FARKLI içerik, AYNI boyut → eşleşmemeli ──")
t3 = bp._tasarim_kaydet(db, d1, _yukle(B), "farkli"); db.commit()
es("yeni kayıt oluştu", True, t3.id != t1.id)
es("yeniden kullanım DEĞİL", False, getattr(t3, "_yeniden_kullanildi", False))
es("artık 2 tasarım var", 2, db.scalar(select(sqlfunc.count()).select_from(Design)
                     .where(Design.store_id == s1.id)))

print("\n── 3. BAŞKA BAYİ aynı dosyayı yüklerse → PAYLAŞILMAZ ──")
t4 = bp._tasarim_kaydet(db, d2, _yukle(A), "baska bayi"); db.commit()
es("ayrı kayıt", True, t4.id != t1.id)
es("ayrı mağaza", s2.id, t4.store_id)
es("yeniden kullanım DEĞİL", False, getattr(t4, "_yeniden_kullanildi", False))

print("\n── 4. HASH aynı ama DOSYA DEĞİŞMİŞ → eşleşmemeli ──")
# Diskteki dosyayi bozalim: hash kayitta A'yi gosteriyor ama icerik artik farkli
yol = storage.STORAGE_ROOT / t1.file_path
yol.write_bytes(B)
t5 = bp._tasarim_kaydet(db, d1, _yukle(A), "dosya degismis"); db.commit()
es("YENİ kayıt açıldı (bayt kontrolü yakaladı)", True, t5.id != t1.id)
es("yeniden kullanım DEĞİL", False, getattr(t5, "_yeniden_kullanildi", False))
yol.write_bytes(A)   # geri al

print("\n── 5. DOSYA SİLİNMİŞSE → eşleşmemeli ──")
yedek = yol.read_bytes(); yol.unlink()
t6 = bp._tasarim_kaydet(db, d1, _yukle(A), "dosya yok"); db.commit()
es("YENİ kayıt açıldı", True, t6.id != t1.id)
yol.write_bytes(yedek)

print("\n── 6. kaydı var ama DOSYASI OLMAYAN tasarım eşleşme vermemeli ──")
C = b"\xff\xd8\xff\xe0" + b"CCCC" * 300 + b"\xff\xd9"
sahte = Design(tenant_id=tenant.id, store_id=s1.id, code=f"{IZ}-SAHTE",
               name="sahte", file_path="olmayan/yol.jpg", file_format="jpg",
               file_size_bytes=len(C), icerik_hash=hashlib.sha256(C).hexdigest())
db.add(sahte); db.commit()
es("dosyası olmayan kayıt eşleşme vermez", None,
   bp._ayni_tasarimi_bul(db, d1, C, hashlib.sha256(C).hexdigest()))
es("C için YENİ kayıt açılır", False,
   getattr(bp._tasarim_kaydet(db, d1, _yukle(C), "c"), "_yeniden_kullanildi", False))
db.commit()

print("\n── 7. AYNI tasarım + AYNI model, 2 kalem → İKİSİ DE planlanmalı ──")
# Dedup'ın en kritik yan etkisi burada olurdu: iki kalem artık AYNI design_code'u
# paylaşıyor. Planlayıcı bunları tek sanarsa bir ürün BASILMADAN kalır.
from app.models import LineItem, Order, PhoneModel  # noqa: E402
from app.services import mold_planner  # noqa: E402

_model = db.scalar(select(PhoneModel).where(
    PhoneModel.tenant_id == tenant.id, PhoneModel.is_active.is_(True)).limit(1))
_model_gecici = False
if _model is None:
    _model = PhoneModel(tenant_id=tenant.id, spec_key=f"{IZ}-key",
                        display_name=f"{IZ} Test Telefon", brand="Test",
                        width_cm=7.0, height_cm=14.5, radius_cm=1.0, is_active=True)
    db.add(_model); db.commit()
    _model_gecici = True
if True:
    o = Order(tenant_id=tenant.id, store_id=s1.id, order_number=f"{IZ}-P1",
              external_id=f"{IZ}-P1", customer_name="Plan", current_stage=1, raw={})
    db.add(o); db.flush()
    for i in range(2):
        db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title=f"k{i}",
                        quantity=1, position=i, assigned_design_id=t1.id,
                        device_model_override=_model.display_name, properties=[], raw={}))
    db.commit()
    plan = mold_planner.plan_molds(db, tenant_id=tenant.id, store_id=s1.id)
    _slot = sum(1 for m in (plan.get("molds") or [])
                for it in (m.get("items") or [])
                if str(it.get("order_number")) == f"{IZ}-P1")
    _eksik = sum(int(e.get("count") or 0) for e in (plan.get("eksikler") or [])
                 if str(e.get("order_number") or "") == f"{IZ}-P1")
    es("iki kalem de görüldü (hiçbiri sessizce yutulmadı)", 2, _slot + _eksik)
    db.execute(text("delete from line_items where order_id=:o"), {"o": str(o.id)})
    db.execute(text("delete from orders where id=:o"), {"o": str(o.id)})
    if _model_gecici:
        db.execute(text("delete from phone_models where id=:m"), {"m": str(_model.id)})
    db.commit()

# temizlik
db.execute(text("delete from designs where store_id in (:a,:b)"),
           {"a": str(s1.id), "b": str(s2.id)})
db.execute(text("delete from dealers where store_id in (:a,:b)"),
           {"a": str(s1.id), "b": str(s2.id)})
db.execute(text("delete from stores where id in (:a,:b)"),
           {"a": str(s1.id), "b": str(s2.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
