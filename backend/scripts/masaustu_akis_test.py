"""Masaüstü uygulamasının YÖNETİM olay akışı (/api/notifications/akis).

Bayi tarafındaki /api/bayii/bildirimler ile AYNI sözleşmeyi konuşmalı: kabuk
iki profilde de aynı kodu kullanıyor, alan adları ayrışırsa biri sessizce
bildirim göstermez olur.

Sınananlar:
  • ilk açılışta olay dönmez, yalnız imleç (bildirim yağmuru olmasın)
  • imleç ŞİMDİDEN GERİDE (Postgres now() işlem başlangıç saati — yarış koruması)
  • since'dan sonra düşen panel bildirimi olay olarak gelir (id/tur/baslik/
    govde/at/link alanlarıyla)
  • bozuk zaman 400; kodlanmamış +00:00 kabul edilir
  • başka kiracının bildirimi sızmaz
  • bayi hesabı bu uca giremez (yönetim akışı)
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token, hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Dealer, Notification, Store, Tenant, User  # noqa: E402

GECTI = KALDI = 0
IZ = f"matest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yonetici = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                        User.role.in_(["owner", "yonetici"]),
                                        User.dealer_id.is_(None)).limit(1))
c = TestClient(app)
H = {"Authorization": "Bearer " + create_access_token(
    user_id=str(yonetici.id), tenant_id=str(tenant.id), email=yonetici.email, expires_minutes=30)}

st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="MA", platform="bayii", is_active=True)
db.add(st); db.flush()
d = Dealer(tenant_id=tenant.id, name=f"{IZ}-bayi", store_id=st.id, unit_price=100, shipping_fee=0,
           currency="TRY", is_active=True, balance=0, balance_usd=0)
db.add(d); db.flush()
bayi_kul = User(tenant_id=tenant.id, email=f"{IZ}@ornek.test", password_hash=hash_password("Portal12345!"),
                full_name="Bayi", role="bayii_portal", permissions=["bayii_portal"],
                dealer_id=d.id, is_active=True)
db.add(bayi_kul); db.commit()
HB = {"Authorization": "Bearer " + create_access_token(
    user_id=str(bayi_kul.id), tenant_id=str(tenant.id), email=bayi_kul.email, expires_minutes=30)}

try:
    print("\n── İlk açılış ──")
    r = c.get("/api/notifications/akis", headers=H)
    es("olay yok, imleç var", (200, []), (r.status_code, r.json()["olaylar"]))
    t0 = r.json()["sunucu_saati"]
    es("imleç şimdiden GERİDE (yarış koruması)", True,
       datetime.fromisoformat(t0) < datetime.now(UTC))

    print("\n── Yeni bildirim ──")
    db.add(Notification(tenant_id=tenant.id, store_id=st.id, kind="bayii",
                        title=f"{IZ} başlık", body="gövde metni", link="/bayi-sohbet"))
    db.commit()
    olaylar = c.get("/api/notifications/akis", headers=H, params={"since": t0}).json()["olaylar"]
    olay = next((o for o in olaylar if IZ in (o["baslik"] or "")), None)
    es("olay geldi", True, olay is not None)
    es("sözleşme alanları (bayi ucuyla aynı)", ["at", "baslik", "govde", "id", "link", "tur"],
       sorted(olay.keys()))
    es("gövde ve adres taşınır", ("gövde metni", "/bayi-sohbet"), (olay["govde"], olay["link"]))
    es("olay kimliği tekil", True, olay["id"].startswith("bildirim-"))

    print("\n── Dayanıklılık ──")
    es("bozuk zaman → 400", 400,
       c.get("/api/notifications/akis?since=dun", headers=H).status_code)
    es("kodlanmamış +00:00 kabul", 200,
       c.get(f"/api/notifications/akis?since={t0}", headers=H).status_code)

    print("\n── Ayrışma ──")
    es("bayi hesabı yönetim akışına giremez", 403,
       c.get("/api/notifications/akis", headers=HB).status_code)
    baska = db.scalar(select(Tenant).where(Tenant.id != tenant.id).limit(1))
    if baska is not None:
        bu = db.scalar(select(User).where(User.tenant_id == baska.id,
                                          User.dealer_id.is_(None)).limit(1))
        if bu is not None:
            H2 = {"Authorization": "Bearer " + create_access_token(
                user_id=str(bu.id), tenant_id=str(baska.id), email=bu.email, expires_minutes=30)}
            es("başka kiracı bu bildirimi görmez", 0,
               len([o for o in c.get("/api/notifications/akis", headers=H2,
                                     params={"since": t0}).json()["olaylar"]
                    if IZ in (o["baslik"] or "")]))
        else:
            print("  · başka kiracıda personel yok, atlandı")
    else:
        print("  · tek kiracı, atlandı")
finally:
    db.rollback()
    db.execute(text("delete from notifications where title like :t"), {"t": f"{IZ}%"})
    db.execute(text("delete from users where email like :e"), {"e": f"{IZ}%"})
    db.execute(text("delete from dealers where name like :d"), {"d": f"{IZ}%"})
    db.execute(text("delete from stores where slug like :s"), {"s": f"{IZ}-%"})
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
