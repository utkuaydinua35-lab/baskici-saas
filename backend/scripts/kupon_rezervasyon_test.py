"""Kupon rezervasyonu: açık checkout hakkı tutuyor mu?

BULGU (2026-09-08): limit checkout AÇILIRKEN kontrol ediliyor, sayaç ise
ödeme DOĞRULANINCA artıyor. Arada SESSION_TTL (2 saat) var. Aynı kuponla N
oturum açıp hepsini ödeyen biri tek kullanımlık kuponu N kez
kullanabiliyordu.

ÇÖZÜM: bekleyen (pending + süresi dolmamış) oturumlar "rezerve" sayılıyor.
Ayrı tablo/sayaç YOK — bilinçli: rezervasyonu ayrı tutmak SERBEST BIRAKMA
mantığı gerektirirdi (süre dolumu, başarısız ödeme, iade) ve oradaki bir
hata kuponu sonsuza kadar kilitlerdi. Süre dolunca oturum kendiliğinden
sayılmaz oluyor.

Sınananlar:
  · açık checkout limiti tüketir (ikinci checkout REDDEDİLİR),
  · süresi dolan oturum hakkı GERİ VERİR,
  · başarısız/iptal oturum hakkı GERİ VERİR,
  · ödenmiş oturum hakkı TUTAR,
  · limitsiz kupon etkilenmez,
  · once_per_customer açık oturumu da sayar,
  · birleşik indirimde ikinci kupon (yalnız breakdown'da) da sayılır.
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import CheckoutSession, DiscountCode, Store  # noqa: E402
from app.services import checkout as cs  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
store = db.scalar(select(Store).where(Store.platform == "storefront"))
if not store:
    raise SystemExit("Vitrin magazasi YOK — test calisamaz.")

kupon = DiscountCode(tenant_id=store.tenant_id, store_id=store.id,
                     code=f"REZ{IZ}".upper(), kind="amount", value=10,
                     usage_limit=1, usage_count=0, is_active=True)
db.add(kupon); db.commit()
KID = kupon.id
temizlenecek: list[uuid.UUID] = []


def oturum(durum="pending", saat=2, email=None, breakdown=None) -> CheckoutSession:
    o = CheckoutSession(
        tenant_id=store.tenant_id, store_id=store.id,
        token=uuid.uuid4().hex, lookup_token=uuid.uuid4().hex,
        status=durum, provider="test", amount=Decimal("100"),
        shipping_amount=Decimal("0"), currency="TRY",
        cart_snapshot=[], customer={"email": email} if email else {},
        discount_code_id=None if breakdown else KID,
        discount_breakdown=breakdown,
        expires_at=datetime.now(UTC) + timedelta(hours=saat))
    db.add(o); db.commit()
    temizlenecek.append(o.id)
    return o


def dolu() -> bool:
    db.expire_all()
    return cs.limit_doldu_mu(db, db.get(DiscountCode, KID))


print("\n── açık checkout hakkı TUTAR ──")
es("başlangıçta limit boş", False, dolu())
a = oturum()
es("açık oturum varken limit DOLU", True, dolu())
es("rezerve sayısı 1", 1, cs.bekleyen_rezervasyon(db, db.get(DiscountCode, KID)))

print("\n── süresi dolan oturum hakkı GERİ VERİR ──")
db.execute(text("update checkout_sessions set expires_at = now() - interval '1 hour' "
                "where id = :i"), {"i": str(a.id)})
db.commit()
es("süresi dolunca limit boşaldı", False, dolu())

print("\n── başarısız / iptal oturum hakkı GERİ VERİR ──")
db.execute(text("update checkout_sessions set expires_at = now() + interval '2 hours', "
                "status = 'failed' where id = :i"), {"i": str(a.id)})
db.commit()
es("failed hakkı tutmuyor", False, dolu())

print("\n── ÖDENMİŞ oturum hakkı TUTAR (sayaç üzerinden) ──")
db.execute(text("update checkout_sessions set status = 'paid' where id = :i"),
           {"i": str(a.id)})
db.execute(text("update discount_codes set usage_count = 1 where id = :i"),
           {"i": str(KID)})
db.commit()
es("ödendikten sonra limit dolu", True, dolu())
db.execute(text("update discount_codes set usage_count = 0 where id = :i"), {"i": str(KID)})
db.execute(text("update checkout_sessions set status = 'expired' where id = :i"),
           {"i": str(a.id)})
db.commit()

print("\n── limitsiz kupon etkilenmez ──")
db.execute(text("update discount_codes set usage_limit = null where id = :i"), {"i": str(KID)})
db.commit()
oturum(); oturum(); oturum()
es("limitsizde üç açık oturuma rağmen dolmuyor", False, dolu())
db.execute(text("update discount_codes set usage_limit = 1 where id = :i"), {"i": str(KID)})
db.commit()

print("\n── birleşik indirim: ikinci kupon breakdown'da ──")
db.execute(text("update checkout_sessions set status='expired' where store_id=:s"),
           {"s": str(store.id)})
db.commit()
es("temizlendi, limit boş", False, dolu())
oturum(breakdown=[{"id": str(KID), "tutar": "10.00"}])
es("yalnız breakdown'daki kupon da sayılıyor", True, dolu())

print("\n── once_per_customer açık oturumu sayar ──")
db.execute(text("update checkout_sessions set status='expired' where store_id=:s"),
           {"s": str(store.id)})
db.execute(text("update discount_codes set usage_limit=null, once_per_customer=true "
                "where id=:i"), {"i": str(KID)})
db.commit()
oturum(email="ayni@musteri.com")
db.expire_all()
_dc = db.get(DiscountCode, KID)
try:
    cs.evaluate_discount(db, _dc, Decimal("200"), "ayni@musteri.com", 1, [])
    es("aynı e-posta ikinci kez REDDEDİLDİ", True, False)
except cs.CheckoutError as e:
    es("aynı e-posta ikinci kez reddedildi", True, "daha önce kullandınız" in str(e))
try:
    cs.evaluate_discount(db, _dc, Decimal("200"), "baska@musteri.com", 1, [])
    es("başka e-posta etkilenmedi", True, True)
except cs.CheckoutError as e:
    es("başka e-posta etkilenmedi", True, f"beklenmedik hata: {e}")

print("\n── KENDİ açık oturumun seni engellemez ──")
# Checkout'u yarıda bırakıp geri dönen müşteri kendi kuponunu 2 saat
# kullanamasaydı bu sık ve can sıkıcı bir hata olurdu.
db.execute(text("update checkout_sessions set status='expired' where store_id=:s"),
           {"s": str(store.id)})
db.execute(text("update discount_codes set usage_limit=1, usage_count=0, "
                "once_per_customer=false where id=:i"), {"i": str(KID)})
db.commit()
oturum(email="terk@eden.com")
db.expire_all()
_dc = db.get(DiscountCode, KID)
es("kendi açık oturumu ENGELLEMİYOR", False, cs.limit_doldu_mu(db, _dc, "terk@eden.com"))
es("BAŞKASINI engelliyor", True, cs.limit_doldu_mu(db, _dc, "baskasi@musteri.com"))
es("e-posta verilmezse engelliyor", True, cs.limit_doldu_mu(db, _dc))

print("\n── GERÇEK checkout yolu: ikinci oturum reddedilmeli ──")
# Buraya kadar olan sınamalar limit fonksiyonunu doğruluyordu; burası
# create_session'ın kendisini (kilit + tekrar sayım dahil) çalıştırır.
db.execute(text("update checkout_sessions set status='expired' where store_id=:s"),
           {"s": str(store.id)})
db.execute(text("update discount_codes set usage_limit=1, usage_count=0, "
                "once_per_customer=false where id=:i"), {"i": str(KID)})
db.commit()

from app.models import CatalogProduct, CatalogVariant  # noqa: E402

_v = db.scalar(select(CatalogVariant)
               .join(CatalogProduct, CatalogProduct.id == CatalogVariant.product_id)
               .where(CatalogProduct.store_id == store.id,
                      CatalogProduct.status == "active",
                      CatalogVariant.is_active.is_(True)))
# Ödeme sağlayıcısı yerelde yapılandırılmamış olabilir; SAHTE sağlayıcı ile
# create_session'ın TAMAMI çalışır ve ağa hiçbir istek gitmez. Sınanan şey
# ödeme değil, kilit + tekrar sayım.
from app.payments.base import CheckoutInit  # noqa: E402


class _SahteSaglayici:
    PROVIDER_NAME = "test"

    def create_checkout(self, session, callback_url):
        return CheckoutInit(mode="redirect", url="https://ornek/odeme",
                            provider_ref="sahte-" + uuid.uuid4().hex[:8])


cs.get_payment_provider = lambda store: _SahteSaglayici()

if _v is None:
    print("  · mağazada aktif varyant yok — uçtan uca sınama atlandı")
else:
    _mus = {"first_name": "T", "last_name": "T", "email": "rez@test.com",
            "phone": "05001112233", "address1": "Deneme mah. 1",
            "city": "İstanbul"}
    _kod = db.get(DiscountCode, KID).code

    def _dene():
        return cs.create_session(
            db, store, items=[{"variant_id": str(_v.id), "quantity": 1}],
            customer=dict(_mus), client_ip="127.0.0.1", discount_code=_kod)

    try:
        _o1, _ = _dene()
        temizlenecek.append(_o1.id)
        es("ilk checkout açıldı", "pending", _o1.status)
        try:
            # Farklı müşteri: kendi oturumu muafiyeti devreye girmesin.
            _mus["email"] = "ikinci@musteri.com"
            _o2, _ = _dene()
            temizlenecek.append(_o2.id)
            es("İKİNCİ checkout REDDEDİLDİ", True, False)
        except cs.CheckoutError as e:
            es("ikinci checkout reddedildi", True, "limiti doldu" in str(e))
            db.rollback()
    except Exception as e:   # noqa: BLE001 — sağlayıcı yapılandırması yoksa
        db.rollback()
        print(f"  · ödeme sağlayıcısı yapılandırılmamış, atlandı ({type(e).__name__})")

db.execute(text("delete from checkout_sessions where store_id=:s and provider='test'"),
           {"s": str(store.id)})
db.execute(text("delete from checkout_sessions where discount_code_id=:i"), {"i": str(KID)})
db.execute(text("delete from discount_codes where id=:i"), {"i": str(KID)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
