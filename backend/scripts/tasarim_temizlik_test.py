"""Tasarım dosyası temizliği — YANLIŞ SİLME OLMAMALI.

Üretimdeki bir dosyayı silmek boş/yanlış baskı demektir. Testlerin ağırlığı
bilerek "SİLİNMEMESİ gereken" durumlarda.
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (Design, LineItem, Mold, MoldItem, Order,  # noqa: E402
                        OrderStatusHistory, Store, Tenant)
from app.services import storage, tasarim_temizlik as tt  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).order_by(Tenant.created_at).limit(1))
store = Store(tenant_id=tenant.id, slug=f"{IZ}-t", name="Temizlik Test",
              platform="bayii", is_active=True)
db.add(store); db.flush()
ESKI = datetime.now(UTC) - timedelta(hours=72)


def tasarim(kod, fmt="jpg"):
    d = Design(tenant_id=tenant.id, store_id=store.id, code=f"{IZ}-{kod}",
               name=kod, file_path="", file_format=fmt, file_size_bytes=10)
    db.add(d); db.flush()
    d.file_path = storage.save_design_file(
        tenant_id=tenant.id, design_id=d.id, file_data=b"\xff\xd8\xff\xe0veri\xff\xd9",
        original_filename=f"x.{fmt}", skip_thumbnail=True)["relative_path"]
    db.flush()
    return d


def siparis(ds, asama, kargo_saat_once=None):
    o = Order(tenant_id=tenant.id, store_id=store.id,
              order_number=f"{IZ}-{uuid.uuid4().hex[:4]}",
              external_id=str(uuid.uuid4()), customer_name="T",
              current_stage=asama, raw={})
    db.add(o); db.flush()
    db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="k", quantity=1,
                    assigned_design_id=ds.id, device_model_override="iPhone 15"))
    if kargo_saat_once is not None:
        db.add(OrderStatusHistory(
            tenant_id=tenant.id, order_id=o.id, from_stage=7, to_stage=8,
            action="kargoya_verildi", note="test",
            created_at=datetime.now(UTC) - timedelta(hours=kargo_saat_once)))
    db.flush()
    return o


# --- senaryolar
d_silinir = tasarim("SILINIR");        siparis(d_silinir, 8, 72)
d_uretimde = tasarim("URETIMDE");      siparis(d_uretimde, 4)
d_yeni = tasarim("YENI-KARGO");        siparis(d_yeni, 8, 5)      # 5 saat önce
d_pdf = tasarim("PDF", "pdf");         siparis(d_pdf, 8, 72)
d_katalog = tasarim("KATALOG")                                     # hiç siparişe bağlı değil
d_karma = tasarim("KARMA");            siparis(d_karma, 8, 72); siparis(d_karma, 4)
d_kalipta = tasarim("KALIPTA");        _o = siparis(d_kalipta, 8, 72)
mold = Mold(tenant_id=tenant.id, store_id=store.id, kod=f"{IZ}-K", variation="SİYAH")
db.add(mold); db.flush()
db.add(MoldItem(tenant_id=tenant.id, mold_id=mold.id,
                line_item_id=db.scalar(select(LineItem.id).where(LineItem.order_id == _o.id)),
                design_id=d_kalipta.id, store_id=store.id, slot_index=1,
                kalip_kodu=f"{IZ}-K", design_code=d_kalipta.code, model="iPhone 15",
                order_number=_o.order_number))
db.commit()

adaylar = {d.code for d in tt.adaylari_bul(db)}

print("\n── 1. SİLİNMESİ gereken ──")
es("kargolanmış + 48 saat geçmiş", True, f"{IZ}-SILINIR" in adaylar)

print("\n── 2. SİLİNMEMESİ gerekenler (asıl sınama) ──")
es("hâlâ ÜRETİMDE", False, f"{IZ}-URETIMDE" in adaylar)
es("kargolanalı 5 saat olmuş", False, f"{IZ}-YENI-KARGO" in adaylar)
es("PDF (baskıya hazır dosya)", False, f"{IZ}-PDF" in adaylar)
es("hiç siparişe bağlı değil (katalog)", False, f"{IZ}-KATALOG" in adaylar)
es("bir siparişi kargolanmış AMA diğeri üretimde", False, f"{IZ}-KARMA" in adaylar)
es("hâlâ KALIP slotunda", False, f"{IZ}-KALIPTA" in adaylar)

print("\n── 3. kuru çalışma HİÇBİR ŞEY silmez ──")
kuru = tt.calistir(db, kuru=True)
es("silinen = 0", 0, kuru["silinen"])
db.expire_all()
es("dosya duruyor", True,
   storage.read_design_file(db.get(Design, d_silinir.id).file_path) is not None)

print("\n── 4. gerçek çalışma ──")
sonuc = tt.calistir(db)
es("1 dosya silindi", 1, sonuc["silinen"])
db.expire_all()
_d = db.get(Design, d_silinir.id)
es("dosya diskten gitti", None, storage.read_design_file(_d.file_path))
es("KAYIT duruyor (geçmiş bozulmasın)", True, _d is not None)
es("işaretlendi", True, _d.dosya_silindi_at is not None)
es("üretimdekine dokunulmadı", True,
   storage.read_design_file(db.get(Design, d_uretimde.id).file_path) is not None)
es("ikinci çalıştırma tekrar silmez", 0, tt.calistir(db)["silinen"])

# temizlik
for d in (d_silinir, d_uretimde, d_yeni, d_pdf, d_katalog, d_karma, d_kalipta):
    storage.delete_design_file(d.file_path)
db.execute(text("delete from mold_items where mold_id=:m"), {"m": str(mold.id)})
db.execute(text("delete from molds where id=:m"), {"m": str(mold.id)})
db.execute(text("delete from order_status_history where order_id in "
                "(select id from orders where store_id=:s)"), {"s": str(store.id)})
db.execute(text("delete from line_items where order_id in "
                "(select id from orders where store_id=:s)"), {"s": str(store.id)})
db.execute(text("delete from orders where store_id=:s"), {"s": str(store.id)})
db.execute(text("delete from designs where store_id=:s"), {"s": str(store.id)})
db.execute(text("delete from stores where id=:s"), {"s": str(store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
