"""E-posta TEŞHİSİ — "mail ulaştı mı?" sorusu artık cevaplanabiliyor mu?

⚠ NEDEN VAR: müşteri "mail gelmedi" dediğinde elimizde HİÇBİR kanıt yoktu.
`send_email` yalnız True/False dönüyordu, Resend'in message id'si atılıyordu,
bounce bildirimi hiç toplanmıyordu ve `email_logs` tablosuna kimse yazmıyordu
(canlıda 0 satır). Eksik stok akışının WhatsApp'a taşınmasının asıl sebebi buydu.

Sınananlar:
  · gönderim kaydı açılıyor mu (sağlayıcı + message id ile)
  · Resend webhook'u iletildi/sekti/şikayet durumlarını işliyor mu
  · "sekti" sonrası geç gelen "delivered" gerçeği GİZLEMİYOR mu
  · yanlış/eksik secret ile webhook 404
  · bilinmeyen message id 200 ile yutuluyor mu (Resend yeniden denemesin)
  · panel ucu yetki + tenant izolasyonu
  · "bilinmiyor" ile "ulaşmadı" ayrı gösteriliyor mu
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import verify_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EmailLog, Order, User  # noqa: E402
from app.services import email_log  # noqa: E402
from app.services.email_service import Sonuc  # noqa: E402

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
    raise SystemExit(f"YONETICI GIRISI BASARISIZ ({_r.status_code}).")
H = {"Authorization": f"Bearer {_r.json()['access_token']}"}

_ord = db.scalar(select(Order).where(Order.tenant_id == admin.tenant_id).limit(1))
if _ord is None:
    print("Sipariş yok — atlandı."); sys.exit(0)
YOL = f"/api/orders/{_ord.id}/eposta-gecmisi"
MID = f"test-{uuid.uuid4().hex[:16]}"

# Webhook secret'ini testin süresince tanımla (canlı ayarı bozmadan).
_s = get_settings()
_eski_secret = _s.resend_webhook_secret
_s.resend_webhook_secret = "test-secret-" + uuid.uuid4().hex[:8]
SEC = _s.resend_webhook_secret


def _wh(olay, mid=MID, secret=None, zaman=None):
    return C.post(f"/api/webhooks/resend/{secret or SEC}", json={
        "type": olay,
        "created_at": (zaman or datetime.now(UTC)).isoformat(),
        "data": {"email_id": mid},
    })


try:
    db.execute(text("delete from email_logs where provider_message_id like 'test-%'"))
    db.commit()

    print("\n── gönderim kaydı açılıyor ──")
    email_log.kaydet(db, tenant_id=_ord.tenant_id, to="musteri@ornek.com",
                     subject="Siparişinizdeki bir ürün hakkında",
                     sonuc=Sonuc(True, "resend", MID),
                     order_id=_ord.id, template_key="stok_eksik", html="<p>x</p>")
    db.commit()
    _k = db.scalar(select(EmailLog).where(EmailLog.provider_message_id == MID))
    es("kayıt yazıldı", True, _k is not None)
    es("sağlayıcı kaydedildi", "resend", _k.provider)
    es("başlangıç durumu 'gonderildi'", "gonderildi", _k.status)
    es("siparişe bağlandı", str(_ord.id), str(_k.order_id))

    print("\n── panel ucu ──")
    _d = C.get(YOL, headers=H).json()
    _m = next((x for x in _d["items"] if x["id"] == str(_k.id)), None)
    es("kayıt panelde", True, _m is not None)
    es("okunur etiket var", "Gönderildi", _m["durum_etiket"])
    # ⚠ "bilinmiyor" ile "ulaşmadı" AYRI: karıştırmak olmayan bilgiyi varmış
    # gibi sunmak olurdu.
    es("geri bildirim BEKLENİYOR olarak işaretli", True, _m["geri_bildirim_bekleniyor"])

    print("\n── webhook: teslim edildi ──")
    es("webhook 200", 200, _wh("email.delivered").status_code)
    es("eşleşti", True, _wh("email.delivered").json()["matched"])
    db.expire_all()
    _k = db.scalar(select(EmailLog).where(EmailLog.provider_message_id == MID))
    es("durum 'iletildi'", "iletildi", _k.status)
    es("iletilme zamanı yazıldı", True, _k.delivered_at is not None)
    _m = next(x for x in C.get(YOL, headers=H).json()["items"] if x["id"] == str(_k.id))
    es("panelde 'Ulaştı'", "Ulaştı", _m["durum_etiket"])
    es("artık beklenmiyor", False, _m["geri_bildirim_bekleniyor"])

    print("\n── webhook: açıldı (durumu DEĞİŞTİRMEZ) ──")
    _wh("email.opened")
    db.expire_all()
    _k = db.scalar(select(EmailLog).where(EmailLog.provider_message_id == MID))
    es("durum hâlâ 'iletildi'", "iletildi", _k.status)
    es("açılma zamanı yazıldı", True, _k.opened_at is not None)

    print("\n── webhook: SEKTİ (asıl aranan cevap) ──")
    MID2 = f"test-{uuid.uuid4().hex[:16]}"
    email_log.kaydet(db, tenant_id=_ord.tenant_id, to="yok@olmayan-alan-adi.tr",
                     subject="Siparişinizdeki bir ürün hakkında",
                     sonuc=Sonuc(True, "resend", MID2), order_id=_ord.id)
    db.commit()
    _wh("email.bounced", MID2)
    db.expire_all()
    _k2 = db.scalar(select(EmailLog).where(EmailLog.provider_message_id == MID2))
    es("durum 'sekti'", "sekti", _k2.status)
    es("sekme zamanı yazıldı", True, _k2.bounced_at is not None)
    _m2 = next(x for x in C.get(YOL, headers=H).json()["items"] if x["id"] == str(_k2.id))
    es("panelde açıkça 'ULAŞMADI'", True, "ULAŞMADI" in _m2["durum_etiket"])

    # ⚠ Geç gelen "delivered" gerçeği GİZLEMEMELİ: sağlayıcılar olayları sırasız
    # gönderebiliyor ve "sekti"nin üstüne "iletildi" yazmak yanlış cevap olurdu.
    _wh("email.delivered", MID2)
    db.expire_all()
    es("geç gelen 'delivered' sekmeyi EZMİYOR", "sekti",
       db.scalar(select(EmailLog).where(EmailLog.provider_message_id == MID2)).status)

    print("\n── şikayet (spam) ──")
    MID3 = f"test-{uuid.uuid4().hex[:16]}"
    email_log.kaydet(db, tenant_id=_ord.tenant_id, to="a@b.com", subject="x",
                     sonuc=Sonuc(True, "resend", MID3), order_id=_ord.id)
    db.commit()
    _wh("email.complained", MID3)
    db.expire_all()
    es("durum 'sikayet'", "sikayet",
       db.scalar(select(EmailLog).where(EmailLog.provider_message_id == MID3)).status)

    print("\n── başarısız gönderim de kaydediliyor ──")
    MID4 = f"test-{uuid.uuid4().hex[:16]}"
    email_log.kaydet(db, tenant_id=_ord.tenant_id, to="a@b.com", subject="x",
                     sonuc=Sonuc(False, "resend", None, "HTTP 422: domain not verified"),
                     order_id=_ord.id)
    db.commit()
    _kb = db.scalar(select(EmailLog).where(
        EmailLog.order_id == _ord.id, EmailLog.status == "basarisiz").limit(1))
    es("durum 'basarisiz'", True, _kb is not None)
    es("HATA METNİ saklandı", True, "domain not verified" in (_kb.error or ""))
    _mb = next(x for x in C.get(YOL, headers=H).json()["items"] if x["id"] == str(_kb.id))
    es("panelde hata gösteriliyor", True, "domain not verified" in (_mb["hata"] or ""))

    print("\n── webhook güvenliği ──")
    es("yanlış secret 404", 404, _wh("email.delivered", secret="yanlis").status_code)
    es("boş secret 404", 404,
       C.post("/api/webhooks/resend/ ", json={"type": "email.delivered"}).status_code)
    es("bilinmeyen message id 200 (Resend tekrar denemesin)", 200,
       _wh("email.delivered", mid="hic-boyle-bir-id-yok").status_code)
    es("bilinmeyen id eşleşmedi", False,
       _wh("email.delivered", mid="hic-boyle-bir-id-yok").json()["matched"])
    es("bilinmeyen olay türü 200", 200, _wh("email.zurna").status_code)
    _secretsiz = get_settings()
    _secretsiz.resend_webhook_secret = ""
    es("secret tanımsızsa webhook KAPALI (404)", 404,
       C.post("/api/webhooks/resend/herhangi", json={"type": "email.delivered"}).status_code)
    _secretsiz.resend_webhook_secret = SEC

    print("\n── panel ucu yetki ──")
    es("token'sız 401/403", True, C.get(YOL).status_code in (401, 403))
    _baska = db.scalar(select(Order).where(Order.tenant_id != admin.tenant_id).limit(1))
    if _baska is not None:
        es("başka tenant'ın siparişi 404", 404,
           C.get(f"/api/orders/{_baska.id}/eposta-gecmisi", headers=H).status_code)

    print("\n── SMTP'de teslimat bilgisi beklenmez ──")
    # SMTP'de webhook yok; "gonderildi"de kalması normaldir, panel bunu
    # "bekleniyor" diye göstermemeli (boşuna beklenti yaratır).
    MID5 = f"test-{uuid.uuid4().hex[:16]}"
    email_log.kaydet(db, tenant_id=_ord.tenant_id, to="a@b.com", subject="x",
                     sonuc=Sonuc(True, "smtp", MID5), order_id=_ord.id)
    db.commit()
    _ks = db.scalar(select(EmailLog).where(EmailLog.provider_message_id == MID5))
    es("smtp kaydında beklenti YOK", False,
       email_log.ozet(_ks)["geri_bildirim_bekleniyor"])

    print("\n── log yazılamazsa ÇAĞIRANIN işi geri alınmaz (savepoint) ──")
    # Düz rollback, kargo bildirimi gönderilirken az önce yazılmış kargo
    # kaydını da silerdi. Bozuk bir kayıtla savepoint'in tuttuğunu görelim.
    _isaret = f"savepoint-{uuid.uuid4().hex[:8]}"
    _r0 = dict(_ord.raw or {})
    _r0["_test_isaret"] = _isaret
    _ord.raw = _r0
    db.flush()
    # tenant_id yerine geçersiz UUID: INSERT FK'da patlar
    email_log.kaydet(db, tenant_id=uuid.uuid4(), to="a@b.com", subject="x",
                     sonuc=Sonuc(True, "resend", f"test-{uuid.uuid4().hex[:8]}"),
                     order_id=_ord.id)
    es("oturum hâlâ kullanılabilir", True,
       db.execute(text("select 1")).scalar() == 1)
    es("çağıranın yazdığı veri DURUYOR", _isaret,
       (db.get(Order, _ord.id).raw or {}).get("_test_isaret"))
    _r1 = dict(_ord.raw or {})
    _r1.pop("_test_isaret", None)
    _ord.raw = _r1
    db.commit()

finally:
    _s.resend_webhook_secret = _eski_secret
    db.rollback()
    db.execute(text("delete from email_logs where provider_message_id like 'test-%' "
                    "or error like 'HTTP 422: domain not verified%'"))
    db.commit()
    print("\n  · test verisi temizlendi")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
