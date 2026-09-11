"""Siparişe yazılan model adı OKUNUR mu — ve kalıp ölçüsü ASLA değişmiyor mu?

⚠ NEDEN: aynı alanda hem "iPhone 16 Pro Max" hem ham katalog anahtarı
"16-PROMAX" / "11" yazıyordu (canlıda 49 farklı değerin 12'si ham). Raporlar
aynı telefonu ikiye bölüyor, panelde "11" gibi anlamsız adlar görünüyordu.

EN ÖNEMLİ KURAL: yeni ad yalnız AYNI kalıp ölçüsüne çözülüyorsa kullanılır.
Yanlış model yazmaktansa çirkin ad kalır.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LineItem, Order, User  # noqa: E402
from app.services import phone_models as pm  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
T = uuid.uuid4()   # tenant'a özel model YOK → yalnız katalog (baseline)

print("\n── ham Apple anahtarı → okunur ad ──")
for ham, okunur in (("16-PROMAX", "iPhone 16 Pro Max"), ("11", "iPhone 11"),
                    ("15-PRO", "iPhone 15 Pro"), ("IPHONE-16-PRO", "iPhone 16 Pro"),
                    ("12-MINI", "iPhone 12 Mini"), ("13-PROMAX", "iPhone 13 Pro Max"),
                    ("14", "iPhone 14")):
    yeni = pm.gorunen_ad(db, T, ham)
    es(f"{ham} → {okunur}", okunur, yeni)
    es(f"{ham}: kalıp ölçüsü AYNI", pm.get_spec(db, T, ham), pm.get_spec(db, T, yeni))

print("\n── dokunulmaması gerekenler ──")
es("zaten okunur ad aynen kalır", "iPhone 16 Pro Max", pm.gorunen_ad(db, T, "iPhone 16 Pro Max"))
es("ölçüsü bulunamayan ad aynen kalır", "Nokia 3310 Ultra", pm.gorunen_ad(db, T, "Nokia 3310 Ultra"))
es("boş dize", "", pm.gorunen_ad(db, T, ""))
es("None", None, pm.gorunen_ad(db, T, None))
es("baştaki/sondaki boşluk kırpılır", "iPhone 15", pm.gorunen_ad(db, T, "  15  "))

print("\n── Samsung: sonuç ne olursa olsun ÖLÇÜ KORUNUR ──")
for ham in ("S23", "S25-ULTRA", "A57"):
    yeni = pm.gorunen_ad(db, T, ham)
    es(f"{ham} ({yeni}): ölçü aynı", pm.get_spec(db, T, ham), pm.get_spec(db, T, yeni))

print("\n── iki kez uygulamak bir şey değiştirmez ──")
for ham in ("16-PROMAX", "11", "S25-ULTRA", "Nokia 3310 Ultra"):
    bir = pm.gorunen_ad(db, T, ham)
    es(f"{ham}: kararlı", bir, pm.gorunen_ad(db, T, bir))

print("\n── uçtan uca: panelden ham anahtar yazılınca okunur ad kaydediliyor ──")
admin = next((u for u in db.scalars(select(User).where(User.role.in_(("yonetici", "owner")))
              .order_by(User.email)).all()
              if u.password_hash and verify_password("DevAdmin12345!", u.password_hash)), None)
li = db.scalar(select(LineItem).join(Order, Order.id == LineItem.order_id)
               .where(Order.tenant_id == admin.tenant_id).limit(1)) if admin else None
if li is None:
    print("  · yönetici/kalem yok — uçtan uca atlandı")
else:
    eski, oid = li.device_model_override, li.order_id
    C = TestClient(app)
    db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')")); db.commit()
    H = {"Authorization": "Bearer " + C.post("/api/auth/login", json={
        "email": admin.email, "password": "DevAdmin12345!"}).json()["access_token"]}
    try:
        r = C.patch(f"/api/orders/{oid}/line-items/{li.id}", headers=H,
                    json={"device_model_override": "16-PROMAX",
                          "fields_to_update": ["device_model_override"]})
        es("güncelleme kabul edildi", 200, r.status_code)
        db.expire_all()
        es("kaydedilen ad okunur", "iPhone 16 Pro Max",
           db.get(LineItem, li.id).device_model_override)
    finally:
        db.execute(text("update line_items set device_model_override=:v where id=:i"),
                   {"v": eski, "i": str(li.id)})
        db.execute(text("delete from order_status_history where order_id=:o "
                        "and action='kalem_model_degisti' and note like '%iPhone 16 Pro Max%' "
                        "and created_at > now() - interval '5 minutes'"), {"o": str(oid)})
        db.commit()
        print("  · kalem eski değerine döndürüldü")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
