"""Panelden müşteri bağlantılarını TEKRAR gösterme ucu.

NEDEN VAR: bağlantı yalnız üretildiği anda (kalıptan çıkarma penceresinde)
görünüyordu. WhatsApp sekmesi kapanır ya da mesaj gönderilemezse operatörün
tek çıkışı kalemi TEKRAR kalıptan çıkarmaktı — yani üretimi bozmak.

Burada sınananlar:
  · geçerli bağlantı mesaj + wa.me ile geri geliyor
  · ÖLÜ bağlantının mesajı ÜRETİLMİYOR (operatör yanlışlıkla göndermesin)
  · kullanılmış bağlantı "uygulandi" olarak görünüyor, seçilen model yazıyor
  · adres bağlantısı üretme kapısı doğru açılıp kapanıyor
  · başka tenant'ın siparişi görülemiyor
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LineItem, ModelDegisimTalebi, Order, User  # noqa: E402
from app.services import model_degisim as md  # noqa: E402

DEV_SIFRE = "DevAdmin12345!"
GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


C = TestClient(app)
db = SessionLocal()

_adaylar = db.scalars(
    select(User).where(User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
admin = next((u for u in _adaylar
              if u.password_hash and verify_password(DEV_SIFRE, u.password_hash)), None)
if admin is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test CALISAMAZ.")
_r = C.post("/api/auth/login", json={"email": admin.email, "password": DEV_SIFRE})
if _r.status_code != 200:
    db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
    db.commit()
    _r = C.post("/api/auth/login", json={"email": admin.email, "password": DEV_SIFRE})
if _r.status_code != 200:
    raise SystemExit(f"YONETICI GIRISI BASARISIZ ({_r.status_code}) — test durduruldu.")
H = {"Authorization": f"Bearer {_r.json()['access_token']}"}

_ord = db.scalar(select(Order).where(Order.tenant_id == admin.tenant_id,
                                     Order.cancelled_at.is_(None)).limit(1))
if _ord is None:
    print("Sipariş yok — sınama atlandı."); sys.exit(0)
_li = db.scalar(select(LineItem).where(LineItem.order_id == _ord.id).limit(1))
YOL = f"/api/orders/{_ord.id}/musteri-baglantilari"

try:
    db.execute(text("delete from model_degisim_talepleri where urun_adi like 'BAGLANTI TEST%'"))
    db.commit()

    print("\n── geçerli bağlantı geri geliyor ──")
    _t = md.talep_olustur(db, _ord, _li, urun_adi="BAGLANTI TEST ürün",
                          model="iPhone 14 Pro", mold_variation="PARLAK")
    db.commit()
    d = C.get(YOL, headers=H).json()
    _m = next((x for x in d["model"] if x["id"] == str(_t.id)), None)
    es("bağlantı listede", True, _m is not None)
    es("geçerli işaretli", True, _m["gecerli"])
    es("mesaj üretildi", True, bool(_m.get("message")))
    es("mesajın içinde link var", True, (_m.get("link") or "@@") in (_m.get("message") or ""))
    es("ürün adı taşınıyor", "BAGLANTI TEST ürün", _m["urun_adi"])
    es("wa.me adresi var (telefon varsa)", bool(d.get("phone")), bool(_m.get("wa_url")))
    es("geçerlilik süresi bildiriliyor", 12, d["model_gecerlilik_saat"])

    print("\n── SÜRESİ DOLMUŞ bağlantının mesajı ÜRETİLMEZ ──")
    # Operatör ölü bir bağlantı gönderirse müşteri açılmayan sayfaya düşer.
    db.execute(text("update model_degisim_talepleri set expires_at = now() - interval '1 hour' "
                    "where id = :i"), {"i": str(_t.id)})
    db.commit()
    _m2 = next(x for x in C.get(YOL, headers=H).json()["model"] if x["id"] == str(_t.id))
    es("geçerli değil", False, _m2["gecerli"])
    es("mesaj YOK", None, _m2.get("message"))
    es("link YOK", None, _m2.get("link"))
    es("wa.me YOK", None, _m2.get("wa_url"))

    print("\n── kullanılmış bağlantı ──")
    db.execute(text("update model_degisim_talepleri set durum='uygulandi', "
                    "secilen_model='iPhone 15', expires_at = now() + interval '5 hours' "
                    "where id = :i"), {"i": str(_t.id)})
    db.commit()
    _m3 = next(x for x in C.get(YOL, headers=H).json()["model"] if x["id"] == str(_t.id))
    es("durum 'uygulandi'", "uygulandi", _m3["durum"])
    es("süresi dolmamış olsa da geçerli DEĞİL", False, _m3["gecerli"])
    es("müşterinin seçtiği model görünüyor", "iPhone 15", _m3["secilen_model"])

    print("\n── 30 günden eski bağlantı listelenmez ──")
    db.execute(text("update model_degisim_talepleri set created_at = now() - interval '40 days' "
                    "where id = :i"), {"i": str(_t.id)})
    db.commit()
    es("listede yok", True,
       all(x["id"] != str(_t.id) for x in C.get(YOL, headers=H).json()["model"]))

    print("\n── adres bağlantısı üretme kapısı ──")
    d2 = C.get(YOL, headers=H).json()
    es("kapı bilgisi var", True, "acik" in (d2.get("adres_uretilebilir") or {}))
    es("kapalıysa sebep var", True,
       d2["adres_uretilebilir"]["acik"] or bool(d2["adres_uretilebilir"]["sebep"]))
    es("adres süresi bildiriliyor", 60, d2["adres_gecerlilik_dk"])

    print("\n── yetki ──")
    es("token'sız 401/403", True,
       C.get(YOL).status_code in (401, 403))
    _baska = db.scalar(select(Order).where(Order.tenant_id != admin.tenant_id).limit(1))
    if _baska is not None:
        es("başka tenant'ın siparişi 404", 404,
           C.get(f"/api/orders/{_baska.id}/musteri-baglantilari", headers=H).status_code)
    else:
        print("  · başka tenant yok — atlandı")

finally:
    db.rollback()
    db.execute(text("delete from model_degisim_talepleri where urun_adi like 'BAGLANTI TEST%'"))
    db.commit()
    print("\n  · test verisi temizlendi")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
