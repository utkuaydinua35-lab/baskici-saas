"""Düşman testi: katalog gizleme ve dosya temizliği YANLIŞ silebilir mi?

Buradaki her bölüm, önce BULUNAN bir hatayı kanıtlamak için yazıldı.

  A) İKİNCİ TASARIM (assigned_design_id_2). Couple / kişiye özel kalemde bir
     satırın İKİ tasarımı var. Hem katalog süzgeci hem dosya temizliği
     yalnızca birinci sütuna bakıyordu:
       · katalog: silinmiş siparişte 1. tasarım + CANLI siparişte 2. tasarım
         olan görsel, hâlâ kullanılıyorken katalogdan düşüyordu.
       · temizlik: canlı üretimdeki siparişin 2. tasarımı, dosyası
         SİLİNEBİLİR sayılıyordu — basılacak kılıfın dosyası yok olurdu.

  B) ÇÖP KUTUSU HİÇ BOŞALTILMIYOR. Silinen sipariş süresiz duruyor ve her an
     geri alınabiliyor. Silinme yaşı 48 saat olsaydı, iki gün sonra geri
     alınan siparişin tasarım dosyası çoktan silinmiş olurdu.
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import hash_password, verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Dealer, Design, LineItem, Order, Store,  # noqa: E402
                        Tenant, User)
from app.services import tasarim_temizlik  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
_ad = next((u for u in db.scalars(select(User).where(
    User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
    if u.password_hash and verify_password("DevAdmin12345!", u.password_hash)), None)
if _ad is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
tenant = db.get(Tenant, _ad.tenant_id)

store = Store(tenant_id=tenant.id, slug=f"{IZ}-d", name="Dusman Test",
              platform="bayii", is_active=True)
db.add(store); db.flush()
dealer = Dealer(tenant_id=tenant.id, store_id=store.id, name=f"DUS-{IZ}",
                is_active=True, unit_price=100, currency="TRY", shipping_fee=0)
db.add(dealer); db.flush()
bayi_kul = User(tenant_id=tenant.id, email=f"dus-{IZ}@bayitest.com",
                full_name="Dusman Bayi", role="bayii_portal", is_active=True,
                dealer_id=dealer.id, password_hash=hash_password("DevBayi12345!"),
                permissions=["bayii_portal"])
db.add(bayi_kul); db.flush()


def tasarim(kod: str) -> Design:
    d = Design(tenant_id=tenant.id, store_id=store.id, code=kod, name=kod,
               file_path=f"test/{kod}.jpg", file_format="jpg", file_size_bytes=1)
    db.add(d); db.flush()
    return d


def siparis(no: str, asama: int = 1) -> Order:
    o = Order(tenant_id=tenant.id, store_id=store.id, order_number=no,
              external_id=no, customer_name="T", current_stage=asama,
              raw={"dealer_id": str(dealer.id)})
    db.add(o); db.flush()
    return o


def kalem(o: Order, birinci: Design, ikinci: Design | None = None):
    db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="k", quantity=1,
                    device_model_override="iPhone 15",
                    assigned_design_id=birinci.id,
                    assigned_design_id_2=ikinci.id if ikinci else None))
    db.flush()


C = TestClient(app)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
BH = {"Authorization": "Bearer " + C.post("/api/auth/login", json={
    "email": bayi_kul.email, "password": "DevBayi12345!"}).json()["access_token"]}


def katalog() -> set[str]:
    return {x["kod"] for x in C.get("/api/bayii/tasarimlar", headers=BH).json()["items"]}


def adaylar() -> set[str]:
    return {d.code for d in tasarim_temizlik.adaylari_bul(db)}


print("\n── A. İKİNCİ TASARIM (couple / kişiye özel) ──")
# t_ikinci: SİLİNMİŞ siparişte 1. tasarım, CANLI siparişte 2. tasarım.
t_ikinci = tasarim(f"{IZ}-IKI")
t_esli = tasarim(f"{IZ}-ESLI")     # canlı siparişin 1. tasarımı (yardımcı)
o_silinmis = siparis(f"{IZ}-S1")
kalem(o_silinmis, t_ikinci)
o_canli = siparis(f"{IZ}-S2")
kalem(o_canli, t_esli, t_ikinci)   # 2. sütunda kullanılıyor
o_silinmis.deleted_at = datetime.now(UTC)
db.commit()
es("2. sütunda kullanılan tasarım katalogda DURUYOR", True, f"{IZ}-IKI" in katalog())

# Temizlik: canlı ve üretimdeki sipariş, 2. tasarımın dosyasını korumalı.
t_uretim = tasarim(f"{IZ}-URT")
o_kargolanan = siparis(f"{IZ}-S3", asama=9)
kalem(o_kargolanan, t_uretim)
db.add_all([])
db.commit()
db.execute(text("""insert into order_status_history
      (id, tenant_id, order_id, from_stage, to_stage, action, created_at)
    values (gen_random_uuid(), :t, :o, 8, 9, 'kargoya_verildi', now() - interval '72 hours')"""),
    {"t": str(tenant.id), "o": str(o_kargolanan.id)})
o_uretimde = siparis(f"{IZ}-S4", asama=3)
kalem(o_uretimde, t_esli, t_uretim)   # üretimdeki siparişin 2. tasarımı
db.commit()
es("üretimdeki siparişin 2. tasarımı silme adayı DEĞİL", False, f"{IZ}-URT" in adaylar())

print("\n── B. ÇÖP KUTUSU SÜRESİZ: silme yaşı penceresi ──")
t_cop = tasarim(f"{IZ}-COP")
o_cop = siparis(f"{IZ}-S5")
kalem(o_cop, t_cop)
db.commit()
for saat, bekle in ((1, False), (72, False), (24 * 20, False), (24 * 40, True)):
    db.execute(text("update orders set deleted_at = now() - make_interval(hours => :s) "
                    "where id = :o"), {"s": saat, "o": str(o_cop.id)})
    db.commit()
    _gun = saat / 24
    es(f"{_gun:.0f} gün önce silinmiş → aday {bekle}", bekle, f"{IZ}-COP" in adaylar())

print("\n── C. gizleme yine de çalışıyor (gerilemedi) ──")
es("silinen siparişin tek tasarımı katalogda YOK", False, f"{IZ}-COP" in katalog())
es("canlı siparişin tasarımı katalogda", True, f"{IZ}-ESLI" in katalog())

for _sql in ("delete from order_status_history where order_id in "
             "(select id from orders where store_id=:s)",
             "delete from line_items where order_id in "
             "(select id from orders where store_id=:s)",
             "delete from orders where store_id=:s",
             "delete from designs where store_id=:s"):
    db.execute(text(_sql), {"s": str(store.id)})
db.execute(text("delete from users where id=:u"), {"u": str(bayi_kul.id)})
db.execute(text("delete from dealers where id=:d"), {"d": str(dealer.id)})
db.execute(text("delete from stores where id=:s"), {"s": str(store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
