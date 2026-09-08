"""Parola değişince ESKİ oturumlar ölüyor mu?

BULGU (2026-09-08): JWT durumsuzdu ve geri alınamıyordu. Token 7 gün
geçerli, `logout` sunucuda no-op. Sonuç: parola değiştirmek mevcut
oturumları DÜŞÜRMÜYORDU — "hesabıma girilmiş, şifremi değiştireyim"
saldırganı atmıyor, erişimi 7 gün daha sürüyordu. Aynı şey şifre
sıfırlamada ve 2FA kapatmada da geçerliydi.

Çözüm: User.sessions_valid_from. Token'ın `iat`'i bu damgadan eskiyse
token reddedilir. Parola değişimi/sıfırlama ve 2FA kapatma damgayı ileri
alır ve kullanıcıyı kendi cihazında düşürmemek için TAZE token döner.

Bu test iki yönü de sınar: eski token ölmeli, taze token çalışmalı.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import hash_password, verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Tenant, User  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]
ILK, YENI = "DevKurban12345!", "YeniParola98765!"


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

kurban = User(tenant_id=tenant.id, email=f"kur-{IZ}@bayitest.com",
              full_name="Kurban", role="personel", is_active=True,
              password_hash=hash_password(ILK), permissions=["siparisler"])
db.add(kurban); db.commit()

C = TestClient(app)


def temizle():
    db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
    db.commit()


def giris(sifre: str):
    temizle()
    return C.post("/api/auth/login", json={"email": kurban.email, "password": sifre})


def kimim(token: str) -> int:
    return C.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code


print("\n── saldırgan ve kurban aynı anda giriş yapmış ──")
saldirgan = giris(ILK).json()["access_token"]     # çalınmış oturum
kurban_tk = giris(ILK).json()["access_token"]
es("çalınmış token çalışıyor", 200, kimim(saldirgan))
es("kurbanın token'ı çalışıyor", 200, kimim(kurban_tk))

# Damga saniyeye yuvarlandığı için AYNI saniyede üretilen token hayatta
# kalır (bilinçli: taze token ölmesin diye). Gerçek bir oturum dakikalar
# öncesinden gelir; testte de token'ları damgadan gerçekten ESKİ yapıyoruz.
import time  # noqa: E402

time.sleep(1.1)

print("\n── kurban parolasını değiştiriyor ──")
r = C.post("/api/auth/change-password",
           headers={"Authorization": f"Bearer {kurban_tk}"},
           json={"current_password": ILK, "new_password": YENI})
es("parola değişti", 200, r.status_code)

# ASIL SÖZ: çalınmış oturum ARTIK ÖLÜ.
es("ÇALINMIŞ token artık geçersiz", 401, kimim(saldirgan))
es("eski (değiştirmeden önceki) kendi token'ı da geçersiz", 401, kimim(kurban_tk))

taze = (r.json() or {}).get("access_token")
es("uç taze token döndü (kullanıcı düşmesin)", True, bool(taze))
if taze:
    es("taze token çalışıyor", 200, kimim(taze))

print("\n── yeni parolayla giriş çalışıyor ──")
r2 = giris(YENI)
es("yeni parola geçerli", 200, r2.status_code)
es("eski parola artık geçersiz", 401, giris(ILK).status_code)
yeni_tk = r2.json()["access_token"]
es("yeni oturum çalışıyor", 200, kimim(yeni_tk))

print("\n── şifre SIFIRLAMA da oturumları düşürmeli ──")
db.refresh(kurban)
kurban.password_hash = hash_password(ILK)
kurban.sessions_valid_from = None      # damgayı temizle: sıfırlamayı izole sına
db.commit()
temizle()
onceki = giris(ILK).json()["access_token"]
es("sıfırlama öncesi token çalışıyor", 200, kimim(onceki))
# reset_password'ün yaptığını doğrudan uygula (token'lı e-posta akışı
# olmadan): parola + damga birlikte ilerler.
time.sleep(1.1)   # iat saniye hassasiyetinde — damga token'dan SONRA olmalı
from datetime import UTC, datetime  # noqa: E402

kurban.password_hash = hash_password(YENI)
kurban.sessions_valid_from = datetime.now(UTC)
db.commit()
es("sıfırlama sonrası eski token geçersiz", 401, kimim(onceki))

db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.execute(text("delete from users where id=:u"), {"u": str(kurban.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
