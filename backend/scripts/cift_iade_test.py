"""Bayi siparişinde borç İKİ KEZ geri alınabiliyor mu?

Senaryo: bayi siparişi geri çeker (borç iade edilir), sonra yönetici aynı
siparişi panelden siler. İkinci işlem bakiyeyi TEKRAR düşürmemeli — düşürürse
bayiye borcu kadar haksız alacak yazılır.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func as sqlfunc, select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (Dealer, DealerTransaction, LineItem, Order,  # noqa: E402
                        Store, Tenant)
from app.services import dealer_debt  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
from app.auth.security import verify_password as _vp  # noqa: E402
from app.models import User as _U  # noqa: E402

_ad = next((u for u in db.scalars(select(_U).where(
    _U.role.in_(("yonetici", "owner"))).order_by(_U.email)).all()
    if u.password_hash and _vp("DevAdmin12345!", u.password_hash)), None)
if _ad is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
tenant = db.get(Tenant, _ad.tenant_id)
store = Store(tenant_id=tenant.id, slug=f"{IZ}-c", name="Cift Iade Test",
              platform="bayii", is_active=True)
db.add(store); db.flush()
dealer = Dealer(tenant_id=tenant.id, store_id=store.id, name=f"CIFT-{IZ}",
                is_active=True, unit_price=100, currency="TRY", shipping_fee=25)
db.add(dealer); db.flush()
o = Order(tenant_id=tenant.id, store_id=store.id, order_number=f"{IZ}-1",
          external_id=f"{IZ}-1", customer_name="T", current_stage=1,
          raw={"dealer_id": str(dealer.id)})
db.add(o); db.flush()
db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="k", quantity=2,
                device_model_override="iPhone 15"))
db.commit()


def bakiye():
    db.expire_all()
    return float(db.get(Dealer, dealer.id).balance or 0)


def hareket_sayisi():
    return db.scalar(select(sqlfunc.count()).select_from(DealerTransaction)
                     .where(DealerTransaction.ref_order_id == o.id)) or 0


print("\n── 1. sipariş onaylandı: borç yazıldı ──")
ozet = dealer_debt.ilk_borc(db, dealer, o, adet=2, kargo_uygula=True)
db.commit()
borc = bakiye()
es("borç yazıldı (2×100 + 25 kargo)", 225.0, borc)
# NOT: borç POZİTİF tutuluyor (225 = bayi 225 borçlu) ve ilk_borc
# İKİ hareket yazıyor: "siparis" + "kargo".
es("2 hareket (sipariş + kargo)", 2, hareket_sayisi())

print("\n── 2. BAYİ geri çekti: borç iade edildi ──")
i1 = dealer_debt.uygula(db, o, reverse=True); db.commit()
es("iade uygulandı", 1, len(i1))
es("bakiye sıfırlandı", 0.0, bakiye())
es("3 hareket (sipariş + kargo + iade)", 3, hareket_sayisi())

print("\n── 3. YÖNETİCİ aynı siparişi sildi (asıl sınama) ──")
i2 = dealer_debt.uygula(db, o, reverse=True); db.commit()
es("İKİNCİ iade HİÇBİR ŞEY yapmadı", [], i2)
es("bakiye DEĞİŞMEDİ", 0.0, bakiye())
es("yeni hareket YAZILMADI", 3, hareket_sayisi())

print("\n── 4. üçüncü kez de güvenli ──")
dealer_debt.uygula(db, o, reverse=True); db.commit()
es("bakiye hâlâ 0", 0.0, bakiye())
es("hareket sayısı hâlâ 3", 3, hareket_sayisi())

print("\n── 5. geri alma (restore): borç TEKRAR yazılır ──")
g = dealer_debt.uygula(db, o, reverse=False); db.commit()
es("borç geri geldi", 225.0, bakiye())
es("ikinci restore etkisiz", [], dealer_debt.uygula(db, o, reverse=False))
es("bakiye değişmedi", 225.0, bakiye())

print("\n── 6. saf hesap: aynı girdi, tekrar çalıştırınca boş ──")
h = [{"dealer_id": dealer.id, "currency": "TRY", "kind": "siparis", "amount": 225}]
es("ilk ters çevirme fark üretir", 1, len(dealer_debt.hesapla(h, reverse=True)))
h2 = h + [{"dealer_id": dealer.id, "currency": "TRY", "kind": "duzeltme", "amount": -225}]
es("iade sonrası fark YOK", 0, len(dealer_debt.hesapla(h2, reverse=True)))

print("\n── 7. silme onayı DOĞRU cümleyi kurabilsin (borc_acik) ──")
# Panel "cari borcundan düşülecek" derken borcun hâlâ açık olduğunu varsayıyordu;
# iade edilmiş siparişte bu yanıltıcıydı. Uç artık gerçeği söylüyor.
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app as _app  # noqa: E402

_C = TestClient(_app)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
_t = _C.post("/api/auth/login", json={"email": _ad.email, "password": "DevAdmin12345!"})
_H = {"Authorization": f"Bearer {_t.json()['access_token']}"}


# ORM örnekleri expire_all sonrası tazelenmek isteyecek; uçlar kendi
# oturumunda çalıştığı için burada sade değerlerle iş görüyoruz.
_DID, _OID = str(dealer.id), str(o.id)


def _kayit():
    r = _C.get(f"/api/dealers/{_DID}/orders", headers=_H)
    return next((x for x in r.json() if x["id"] == _OID), None)


# şu an borç AÇIK (5. bölümde geri yazıldı)
_k = _kayit()
es("borç açıkken borc_acik=True", True, _k and _k["borc_acik"])
es("cari kaydı var", True, _k and _k["cari_kayit_var"])
# Para birimleri ayrı: ürün TRY + kargo TRY tek satırda toplanır.
es("açık tutar 225 TRY", {"TRY": 225.0}, _k and _k["cari_acik"])
dealer_debt.uygula(db, o, reverse=True); db.commit()
_k = _kayit()
es("iade sonrası borc_acik=False", False, _k and _k["borc_acik"])
es("açık tutar kalmadı", {}, _k and _k["cari_acik"])
es("cari kaydı HÂLÂ var (iade edilmiş ≠ hiç yazılmamış)", True,
   _k and _k["cari_kayit_var"])

print("\n── 8. ONAYLANMAMIŞ sipariş: borç hiç yazılmamış ──")
# 2026-09-08'de yandı: onay metni siparişin TUTARINA bakıyordu, tutar ise
# sipariş açılırken doluyor. Onaylanmamış siparişte "borcu zaten iade
# edilmiş" deniyordu — oysa hiç borç yazılmamıştı.
o2 = Order(tenant_id=tenant.id, store_id=store.id, order_number=f"{IZ}-2",
           external_id=f"{IZ}-2", customer_name="T2", current_stage=1,
           raw={"dealer_id": _DID, "total_price": 300, "currency": "TRY"})
db.add(o2); db.commit()
_O2 = str(o2.id)
_r = _C.get(f"/api/dealers/{_DID}/orders", headers=_H)
_k2 = next((x for x in _r.json() if x["id"] == _O2), None)
es("onaylanmamış: tutar VAR", 300, _k2 and _k2["total_price"])
es("onaylanmamış: cari kaydı YOK", False, _k2 and _k2["cari_kayit_var"])
es("onaylanmamış: borc_acik=False", False, _k2 and _k2["borc_acik"])
es("onaylanmamış: açık tutar boş", {}, _k2 and _k2["cari_acik"])
db.execute(text("delete from orders where id=:o"), {"o": _O2})
db.commit()

db.execute(text("delete from dealer_transactions where dealer_id=:d"), {"d": _DID})
db.execute(text("delete from line_items where order_id=:o"), {"o": _OID})
db.execute(text("delete from orders where id=:o"), {"o": _OID})
db.execute(text("delete from dealers where id=:d"), {"d": _DID})
db.execute(text("delete from stores where id=:s"), {"s": str(store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
