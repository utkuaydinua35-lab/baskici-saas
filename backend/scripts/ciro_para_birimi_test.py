"""Ciro PARA BİRİMİNE duyarlı mı? — dashboard, analitik, kâr, canlı.

⚠ NEDEN: ciro `raw.total_price` düz toplanarak hesaplanıyordu. Bayi
siparişlerinde tutar BAYİNİN PARA BİRİMİNDE: KE-MARKET ve Alysa Case USD
bayisi. Son 3 ayda 79 USD siparişin 250 doları panele 250 TL diye ekleniyordu;
bayi kargosu (`shipping_fee`, HER ZAMAN TL) ise toplama hiç girmiyordu.

Kural (services/ciro): TL ve USD AYRI toplanır, kur çevrilmez.
  TL  = TRY siparişin toplamı + bayi siparişinin kargosu
  USD = USD siparişin ürün bedeli
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Order, Store, User  # noqa: E402
from app.services import ciro  # noqa: E402

GECTI = KALDI = 0
IZ = "CIRO-TEST-" + uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


def yakin(ad, beklenen, gercek, tol=0.01):
    es(ad, True, abs(float(beklenen) - float(gercek)) <= tol)


db = SessionLocal()
admin = next((u for u in db.scalars(select(User).where(User.role.in_(("yonetici", "owner")))
              .order_by(User.email)).all()
              if u.password_hash and verify_password("DevAdmin12345!", u.password_hash)), None)
if admin is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test CALISAMAZ.")
store = db.scalar(select(Store).where(Store.tenant_id == admin.tenant_id).limit(1))
if store is None:
    raise SystemExit("Magaza YOK — test CALISAMAZ.")

C = TestClient(app)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')")); db.commit()
H = {"Authorization": "Bearer " + C.post("/api/auth/login", json={
    "email": admin.email, "password": "DevAdmin12345!"}).json()["access_token"]}
BUGUN = date.today().isoformat()


def _pano():
    return C.get("/api/dashboard/summary", headers=H).json()["ciro"]


def _analitik():
    return C.get(f"/api/analytics/summary?start={BUGUN}&end={BUGUN}", headers=H).json()


try:
    print("\n── ifadeler SQL'de hatasız çalışıyor ──")
    # dashboard._toplam hatayı 0'a çeviriyor: ifade bozuk olsa panel sessizce 0
    # gösterirdi. Burada DOĞRUDAN çalıştırıp hata olmadığını kanıtlıyoruz.
    from sqlalchemy import func
    for ad, ifade in (("tl_tutar", ciro.tl_tutar()), ("usd_tutar", ciro.usd_tutar())):
        try:
            db.scalar(select(func.sum(ifade)).where(Order.tenant_id == admin.tenant_id))
            es(f"{ad} çalışıyor", True, True)
        except Exception as e:  # noqa: BLE001
            es(f"{ad} çalışıyor", True, repr(e)[:120])
            db.rollback()

    p0, a0 = _pano(), _analitik()

    print("\n── üç tür sipariş ekleniyor ──")
    simdi = datetime.now(UTC)
    siparisler = [
        # USD bayi: 2,50 $ ürün + 132 TL kargo
        {"source": "bayii", "dealer_id": "x", "currency": "USD",
         "total_price": "2.50", "shipping_fee": "132"},
        # TRY bayi: 132 TL ürün + 50 TL kargo
        {"source": "bayii", "dealer_id": "x", "currency": "TRY",
         "total_price": "132.0", "shipping_fee": "50"},
        # Shopify: 600 TL (kargo toplamın içinde)
        {"currency": "TRY", "total_price": "600.00"},
        # Para birimi yazılmamış eski kayıt → TL sayılır
        {"total_price": "10"},
        # Boş tutar alanı → 0, patlamaz
        {"currency": "TRY", "total_price": ""},
    ]
    for i, raw in enumerate(siparisler):
        db.add(Order(tenant_id=admin.tenant_id, store_id=store.id,
                     external_id=f"{IZ}-{i}", order_number=f"{IZ}-{i}",
                     created_at_platform=simdi, raw=raw))
    db.commit()

    print("\n── dashboard ──")
    p1 = _pano()
    yakin("TL ciro +924 (600 + 132 + 50 + 132 USD siparişin kargosu + 10)",
          p0["ay"] + 924, p1["ay"])
    es("USD alanı var", True, isinstance(p1.get("usd"), dict))
    yakin("USD ciro +2,50", p0["usd"]["ay"] + 2.5, p1["usd"]["ay"])
    yakin("bugün de aynı TL farkı", p0["bugun"] + 924, p1["bugun"])
    es("2,50 $ TL'ye EKLENMEDİ", True, abs((p1["ay"] - p0["ay"]) - 924) < 0.01)

    print("\n── analitik özet ──")
    a1 = _analitik()
    yakin("revenue TL +924", a0["revenue"] + 924, a1["revenue"])
    yakin("revenue_usd +2,50", a0.get("revenue_usd", 0) + 2.5, a1["revenue_usd"])
    _mag = next((s for s in a1["by_store"] if s["store"] == store.name), None)
    es("mağaza satırında revenue_usd var", True, bool(_mag) and "revenue_usd" in _mag)

    print("\n── kâr raporu yalnız TL ──")
    k = C.get(f"/api/analytics/profit?start={BUGUN}&end={BUGUN}", headers=H).json()
    es("USD sipariş dışarıda sayıldı", True, k.get("haric_usd_siparis", 0) >= 1)

    print("\n── canlı ──")
    c = C.get("/api/analytics/live", headers=H).json()
    es("canlı bugün revenue_usd ≥ 2,50", True, c["today"].get("revenue_usd", 0) >= 2.5)
finally:
    db.rollback()
    db.execute(text("delete from orders where external_id like :p"), {"p": f"{IZ}-%"})
    db.commit()
    print("\n  · test siparişleri silindi")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
