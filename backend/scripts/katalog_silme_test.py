"""Silinen siparişin tasarımı katalogdan düşüyor mu?

Sınanan sözler:
  • Siparişi silinen tasarım bayi kataloğunda GÖRÜNMEZ.
  • Sipariş çöpten geri alınınca tasarım GERİ GELİR.
  • Tasarım başka bir CANLI siparişte de kullanılıyorsa GİZLENMEZ (asıl
    tehlike bu: aynı tasarım birden çok siparişe bağlanabiliyor).
  • Hiç siparişi olmayan tasarıma dokunulmaz.
  • İPTAL edilmiş sipariş gizlemez — iptal silme değildir.
  • Yönetim tarafındaki seçici (katalog=1) aynı listeyi verir, çıplak
    /api/designs ise her şeyi görmeye devam eder.
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

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()

# Yonetici ve bayi AYNI tenant'tan secilir; bagimsiz secim 404/izolasyon
# hatasi veriyordu (baska testlerde yanmisti).
_ad = next((u for u in db.scalars(select(User).where(
    User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
    if u.password_hash and verify_password("DevAdmin12345!", u.password_hash)), None)
if _ad is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
tenant = db.get(Tenant, _ad.tenant_id)

store = Store(tenant_id=tenant.id, slug=f"{IZ}-k", name="Katalog Test",
              platform="bayii", is_active=True)
db.add(store); db.flush()
dealer = Dealer(tenant_id=tenant.id, store_id=store.id, name=f"KAT-{IZ}",
                is_active=True, unit_price=100, currency="TRY", shipping_fee=0)
db.add(dealer); db.flush()
bayi_kul = User(tenant_id=tenant.id, email=f"kat-{IZ}@bayitest.com",
                full_name="Katalog Bayi", role="bayii_portal", is_active=True,
                dealer_id=dealer.id, password_hash=hash_password("DevBayi12345!"),
                # Rol tek basina YETMIYOR: uclar require_permission ile
                # korunuyor (403 "Bu panel icin yetkin yok").
                permissions=["bayii_portal"])
db.add(bayi_kul); db.flush()


def tasarim(kod: str) -> Design:
    d = Design(tenant_id=tenant.id, store_id=store.id, code=kod, name=kod,
               file_path=f"test/{kod}.jpg", file_format="jpg", file_size_bytes=1)
    db.add(d); db.flush()
    return d


def siparis(no: str, *tasarimlar: Design) -> Order:
    o = Order(tenant_id=tenant.id, store_id=store.id, order_number=no,
              external_id=no, customer_name="T", current_stage=1,
              raw={"dealer_id": str(dealer.id)})
    db.add(o); db.flush()
    for t in tasarimlar:
        db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="k", quantity=1,
                        device_model_override="iPhone 15", assigned_design_id=t.id))
    db.flush()
    return o


t_silinen = tasarim(f"{IZ}-SIL")      # yalnız silinecek siparişte
t_paylasik = tasarim(f"{IZ}-PAY")     # hem silinecek hem canlı siparişte
t_bos = tasarim(f"{IZ}-BOS")          # hiç siparişi yok
t_iptal = tasarim(f"{IZ}-IPT")        # yalnız iptal edilmiş siparişte

o_sil = siparis(f"{IZ}-1", t_silinen, t_paylasik)
o_canli = siparis(f"{IZ}-2", t_paylasik)
o_iptal = siparis(f"{IZ}-3", t_iptal)
o_iptal.is_iptal = True
db.commit()

C = TestClient(app)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
_bt = C.post("/api/auth/login", json={"email": bayi_kul.email, "password": "DevBayi12345!"})
BH = {"Authorization": f"Bearer {_bt.json()['access_token']}"}
_at = C.post("/api/auth/login", json={"email": _ad.email, "password": "DevAdmin12345!"})
AH = {"Authorization": f"Bearer {_at.json()['access_token']}"}
_SID = str(store.id)


def katalog() -> set[str]:
    r = C.get("/api/bayii/tasarimlar", headers=BH)
    return {x["kod"] for x in r.json().get("items", [])}


def yonetim(katalog_suzgeci: bool) -> set[str]:
    r = C.get(f"/api/designs?store_id={_SID}&per_page=200"
              + ("&katalog=1" if katalog_suzgeci else ""), headers=AH)
    return {x["code"] for x in r.json().get("items", [])}


print("\n── 1. silmeden önce hepsi katalogda ──")
k = katalog()
es("silinecek siparişin tasarımı var", True, f"{IZ}-SIL" in k)
es("paylaşık tasarım var", True, f"{IZ}-PAY" in k)
es("siparişsiz tasarım var", True, f"{IZ}-BOS" in k)
es("iptal siparişin tasarımı var", True, f"{IZ}-IPT" in k)

print("\n── 2. sipariş silindi (asıl sınama) ──")
o_sil.deleted_at = datetime.now(UTC)
db.commit()
k = katalog()
es("silinen siparişin tasarımı KATALOGDAN ÇIKTI", False, f"{IZ}-SIL" in k)
es("başka canlı siparişte de olan tasarım DURUYOR", True, f"{IZ}-PAY" in k)
es("hiç siparişi olmayan tasarım DURUYOR", True, f"{IZ}-BOS" in k)
es("iptal edilmiş sipariş gizlemez", True, f"{IZ}-IPT" in k)

print("\n── 3. çöpten geri alınınca tasarım da döner ──")
o_sil.deleted_at = None
db.commit()
es("geri gelen siparişin tasarımı katalogda", True, f"{IZ}-SIL" in katalog())

print("\n── 4. paylaşık tasarım: TÜM siparişleri silinirse gizlenir ──")
o_sil.deleted_at = datetime.now(UTC)
o_canli.deleted_at = datetime.now(UTC)
db.commit()
k = katalog()
es("her iki siparişi de silinen tasarım gizlendi", False, f"{IZ}-PAY" in k)
es("siparişsiz tasarım hâlâ duruyor", True, f"{IZ}-BOS" in k)

print("\n── 5. yönetim tarafı ──")
es("katalog=1 aynı sonucu verir", katalog(), yonetim(True))
_hepsi = yonetim(False)
es("çıplak liste silinmiş siparişin tasarımını GÖRÜR", True, f"{IZ}-SIL" in _hepsi)
es("çıplak liste paylaşık tasarımı GÖRÜR", True, f"{IZ}-PAY" in _hepsi)

print("\n── 6. dosya temizliği: silinen sipariş artık engel değil ──")
from app.services import tasarim_temizlik  # noqa: E402

# Yeni silinmiş sipariş (48 saat dolmadı) → dosya DURMALI: çöpten geri
# alınabilir, tasarımı yok etmek geri almayı bozardı.
_aday = {d.code for d in tasarim_temizlik.adaylari_bul(db)}
es("48 saat dolmadan aday DEĞİL", False, f"{IZ}-SIL" in _aday)
db.execute(text("update orders set deleted_at = now() - interval '72 hours' "
                "where id in (:a, :b)"), {"a": str(o_sil.id), "b": str(o_canli.id)})
db.commit()
_aday = {d.code for d in tasarim_temizlik.adaylari_bul(db)}
es("72 saat sonra aday", True, f"{IZ}-SIL" in _aday)
es("iptal (silinmemiş) siparişin tasarımı aday DEĞİL", False, f"{IZ}-IPT" in _aday)
es("siparişsiz tasarım aday DEĞİL (kural 4)", False, f"{IZ}-BOS" in _aday)

for _sql in ("delete from line_items where order_id in "
             "(select id from orders where store_id=:s)",
             "delete from orders where store_id=:s",
             "delete from designs where store_id=:s"):
    db.execute(text(_sql), {"s": _SID})
db.execute(text("delete from users where id=:u"), {"u": str(bayi_kul.id)})
db.execute(text("delete from dealers where id=:d"), {"d": str(dealer.id)})
db.execute(text("delete from stores where id=:s"), {"s": _SID})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
