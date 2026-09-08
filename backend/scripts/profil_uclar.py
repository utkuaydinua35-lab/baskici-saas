"""Sıcak uçlarda SORGU SAYISI ve SÜRE ölçümü.

N+1'i tahmin etmek yerine ölçer: her uca istek atar, SQLAlchemy olaylarıyla
çalışan sorguları sayar ve en çok tekrar eden SQL'i gösterir. "Bir sorgu N
kez tekrarlanıyor" N+1'in imzasıdır.

Kullanım:  .venv/bin/python scripts/profil_uclar.py
"""
from __future__ import annotations

import collections
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event, select, text  # noqa: E402

from app.auth.security import verify_password  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Store, User  # noqa: E402

db = SessionLocal()
_ad = next((u for u in db.scalars(select(User).where(
    User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
    if u.password_hash and verify_password("DevAdmin12345!", u.password_hash)), None)
if _ad is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK.")
store = db.scalar(select(Store).where(Store.tenant_id == _ad.tenant_id))
SID = str(store.id) if store else ""

C = TestClient(app)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
H = {"Authorization": "Bearer " + C.post("/api/auth/login", json={
    "email": _ad.email, "password": "DevAdmin12345!"}).json()["access_token"]}

_sorgular: list[str] = []


@event.listens_for(engine, "before_cursor_execute")
def _kaydet(conn, cursor, statement, params, context, executemany):
    _sorgular.append(statement)


def _sadelestir(sql: str) -> str:
    """Parametreleri sil ki aynı şablon tek satırda toplansın."""
    s = " ".join(sql.split())
    s = re.sub(r"%\(\w+\)s", "?", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    return s[:110]


# Kimlik gerektiren uçlar için örnek kayıtlar
from app.models import Dealer, Mold, Order  # noqa: E402

_o = db.scalar(select(Order).where(Order.tenant_id == _ad.tenant_id))
_m = db.scalar(select(Mold).where(Mold.tenant_id == _ad.tenant_id))
_d = db.scalar(select(Dealer).where(Dealer.tenant_id == _ad.tenant_id))
OID = str(_o.id) if _o else ""
MID = str(_m.id) if _m else ""
DID = str(_d.id) if _d else ""

UCLAR = [
    ("siparişler (liste)",        "GET", "/api/orders?per_page=50"),
    ("sipariş sekme sayaçları",   "GET", "/api/orders/tab-counts"),
    ("kalıplar",                  "GET", "/api/molds"),
    ("paketleme kuyruğu",         "GET", "/api/packaging/queue"),
    ("stok grupları",             "GET", "/api/stock/groups"),
    ("tasarımlar",                "GET", f"/api/designs?store_id={SID}&per_page=60"),
    ("dashboard özet",            "GET", "/api/dashboard/summary"),
    ("bildirimler",               "GET", "/api/notifications"),
    ("mağazalar",                 "GET", "/api/stores"),
    ("sipariş detayı",            "GET", f"/api/orders/{OID}" if OID else ""),
    ("kalıp detayı",              "GET", f"/api/molds/{MID}" if MID else ""),
    ("kalıp PDF durumu",          "GET", f"/api/molds/{MID}/pdf-durum" if MID else ""),
    ("bayi siparişleri",          "GET", f"/api/dealers/{DID}/orders" if DID else ""),
    ("bayi cari",                 "GET", f"/api/dealers/{DID}" if DID else ""),
    ("paketleme sipariş",         "GET", f"/api/packaging/order/{OID}" if OID else ""),
    ("arama",                     "GET", "/api/search?q=iph"),
    ("kalıp atanabilir kalemler", "GET", "/api/molds/assignable-line-items"),
]
UCLAR = [u for u in UCLAR if u[2]]

print(f"{'uç':<28} {'sorgu':>6} {'süre':>9}   en çok tekrarlanan")
print("─" * 100)
sonuclar = []
for ad, yontem, yol in UCLAR:
    _sorgular.clear()
    t0 = time.perf_counter()
    r = C.request(yontem, yol, headers=H)
    sure = (time.perf_counter() - t0) * 1000
    if r.status_code == 404:
        print(f"{ad:<28} {'—':>6} {'—':>9}   (uç yok)")
        continue
    n = len(_sorgular)
    sayac = collections.Counter(_sadelestir(s) for s in _sorgular)
    tekrar, adet = sayac.most_common(1)[0] if sayac else ("", 0)
    isaret = " ⚠" if adet >= 10 else ""
    print(f"{ad:<28} {n:>6} {sure:>7.0f}ms   {adet}× {tekrar[:64]}{isaret}")
    sonuclar.append((ad, n, sure, adet, tekrar))

print("\n── N+1 şüphelileri (aynı sorgu 10+ kez) ──")
var = False
for ad, n, sure, adet, tekrar in sonuclar:
    if adet >= 10:
        var = True
        print(f"\n  {ad}: {adet} kez\n    {tekrar}")
if not var:
    print("  yok")
