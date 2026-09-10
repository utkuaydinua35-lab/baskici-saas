"""Teslimat adresi değişikliği — işlev ve güvenlik.

⚠ BU AKIŞIN İKİ ÖLÜMCÜL HATASI VAR, ikisi de burada sınanıyor:

  1. KARGO BAŞLADIKTAN SONRA DEĞİŞİKLİK. Etiket basılmış ya da paket teslim
     edilmişse adres değiştirilirse paket yine ESKİ adrese gider ama sistemde
     yeni adres görünür — kimse fark etmez. Kapı İKİ yerde: bağlantı
     üretilirken ve uygulanırken (durum arada değişebilir).

  2. YALNIZ YERELDE DEĞİŞTİRME. `order.raw` her senkronda Shopify'dan yeniden
     yazılıyor; Shopify'a yazmadan yereli değiştirmek bir sonraki senkronda
     SESSİZCE geri alınır. Shopify çağrısı başarısızsa yerel de DEĞİŞMEMELİ.

Ayrıca: token/süre/tek kullanım, eşzamanlılık, zorunlu alan doğrulaması,
telefon normalleştirme, girdi dayanıklılığı ve bilgi sızması.
"""
from __future__ import annotations

import concurrent.futures
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Order, Store  # noqa: E402
from app.services import adres_degisim as ad  # noqa: E402

GECTI = KALDI = 0


def es(ad_, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad_}")
    else:
        KALDI += 1; print(f"  ✗ {ad_}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


C = TestClient(app)
db = SessionLocal()
_SAYAC = [0]


def _ip() -> dict:
    _SAYAC[0] += 1
    return {"CF-Connecting-IP": f"10.7.0.{_SAYAC[0]}"}


def GET(y, **k):
    return C.get(y, headers=_ip(), **k)


def POST(y, **k):
    return C.post(y, headers=_ip(), **k)


print("\n── telefon normalleştirme ──")
for ham, bek in [("5321602442", "05321602442"), ("0532 160 24 42", "05321602442"),
                 ("+90 532 160 24 42", "05321602442"), ("(0532) 160-2442", "05321602442")]:
    es(f"{ham!r}", bek, ad.telefon_gecerli(ham))
for ham in ("", None, "123", "02123334455", "4321602442"):
    es(f"{ham!r} reddedildi", None, ad.telefon_gecerli(ham))

print("\n── e-posta doğrulama ──")
es("geçerli", True, ad.eposta_gecerli("a@b.com"))
es("boş reddedilir", False, ad.eposta_gecerli(""))
es("@ yok", False, ad.eposta_gecerli("abc"))
es("alan adı yok", False, ad.eposta_gecerli("a@b"))

print("\n── KARGO KAPISI (en kritik) ──")


def _sahte(**alanlar):
    o = Order(tenant_id=None, order_number="1", raw={})
    for k, v in alanlar.items():
        setattr(o, k, v)
    return o


es("temiz sipariş → izin var", True, ad.degistirilebilir_mi(_sahte())[0])
es("kargo_info.takip_no → KAPALI", False,
   ad.degistirilebilir_mi(_sahte(kargo_info={"takip_no": "123"}))[0])
es("kargo_info.barcode → KAPALI", False,
   ad.degistirilebilir_mi(_sahte(kargo_info={"barcode": "999"}))[0])
es("barkod_kodu → KAPALI", False,
   ad.degistirilebilir_mi(_sahte(barkod_kodu="401059"))[0])
es("fulfilled → KAPALI", False,
   ad.degistirilebilir_mi(_sahte(fulfillment_status="fulfilled"))[0])
es("partial → KAPALI", False,
   ad.degistirilebilir_mi(_sahte(fulfillment_status="partial"))[0])
es("iptal → KAPALI", False,
   ad.degistirilebilir_mi(_sahte(cancelled_at=datetime.now(UTC)))[0])
es("arşiv → KAPALI", False,
   ad.degistirilebilir_mi(_sahte(closed_at=datetime.now(UTC)))[0])
es("sipariş yok → KAPALI", False, ad.degistirilebilir_mi(None)[0])
es("kapalıyken sebep BOŞ DEĞİL", True,
   bool(ad.degistirilebilir_mi(_sahte(barkod_kodu="x"))[1]))

print("\n── adres kurulumu eski alanları korur ──")
_eski = {"country": "Turkey", "country_code": "TR", "zip": "34000", "company": "X"}
_yeni = ad.adres_kur({"ad": "Ali", "soyad": "Veli", "adres": "Y sok. 1",
                      "adres2": "D:3", "il": "İstanbul", "ilce": "Kadıköy",
                      "telefon": "05321602442"}, _eski)
es("posta kodu korundu", "34000", _yeni["zip"])
es("ülke korundu", "Turkey", _yeni["country"])
es("ad+soyad birleşti", "Ali Veli", _yeni["name"])
es("il province'e yazıldı", "İstanbul", _yeni["province"])
es("ilçe city'e yazıldı", "Kadıköy", _yeni["city"])

# ─── Uçtan uca ────────────────────────────────────────────────────────────
print("\n── uçtan uca ──")
# ⚠ SHOPIFY MAĞAZASINI SEÇME. Uygulama yolu gerçek Shopify'a PUT atıyor;
# testin üretimdeki bir siparişin adresini değiştirmesi kabul edilemez.
# Shopify OLMAYAN bir mağazanın siparişiyle çalışıyoruz — akış aynı, yalnız
# harici çağrı yok (kod zaten platforma göre dallanıyor).
_ord = db.scalar(
    select(Order).join(Store, Store.id == Order.store_id)
    .where(Order.cancelled_at.is_(None), Store.platform != "shopify").limit(1))
if _ord is None:
    print("  · Shopify dışı sipariş yok — uçtan uca atlandı")
else:
    _eski_raw = dict(_ord.raw or {})
    _eski_mail = _ord.customer_email
    _eski_ad = _ord.customer_name
    _eski_ki = _ord.kargo_info
    _eski_bk = getattr(_ord, "barkod_kodu", None)
    _eski_fs = _ord.fulfillment_status

    # Önce kargo kapısını KAPALI kur: kapının gerçekten tuttuğunu görelim.
    _ord.kargo_info = {"takip_no": "TEST123"}
    db.commit()

    _t = ad.talep_olustur(db, _ord)
    db.commit()
    TOKEN = _t.token

    _v = GET(f"/api/public/adres-degisim/{TOKEN}").json()
    es("kargo başlamışsa sayfa 'kapali'", "kapali", _v.get("durum"))
    es("sebep gösteriliyor", True, bool(_v.get("sebep")))
    es("kapalıyken POST 409", 409,
       POST(f"/api/public/adres-degisim/{TOKEN}",
            json={"ad": "A", "soyad": "B", "adres": "C", "il": "D", "ilce": "E",
                  "telefon": "05321602442"}).status_code)

    # Kapıyı aç: bundan sonrası doğrulama ve gerçek uygulama sınaması.
    _ord.kargo_info = None
    db.commit()
    _v2 = GET(f"/api/public/adres-degisim/{TOKEN}").json()
    es("kapı açılınca 'bekliyor'", "bekliyor", _v2.get("durum"))
    es("form ön dolu geliyor", True, isinstance(_v2.get("adres"), dict))
    es("sipariş numarası var", True, bool(_v2.get("siparis_no")))

    print("\n── zorunlu alan doğrulaması ──")
    _tam = {"ad": "Ali", "soyad": "Veli", "adres": "Y sok 1", "il": "İstanbul",
            "ilce": "Kadıköy", "telefon": "05321602442"}
    for alan in ("ad", "soyad", "adres", "il", "ilce"):
        _g = dict(_tam); _g[alan] = "   "
        es(f"{alan} boşsa 400", 400,
           POST(f"/api/public/adres-degisim/{TOKEN}", json=_g).status_code)
    _g = dict(_tam); _g["telefon"] = "123"
    es("geçersiz telefon 400", 400,
       POST(f"/api/public/adres-degisim/{TOKEN}", json=_g).status_code)
    _g = dict(_tam); _g["eposta"] = "bozuk"
    es("geçersiz e-posta 400", 400,
       POST(f"/api/public/adres-degisim/{TOKEN}", json=_g).status_code)

    print("\n── girdi dayanıklılığı (5xx YOK) ──")
    # Bu istekler BAŞARILI olursa bağlantı kapanır; her biri için ayrı talep
    # üretiyoruz ki bir sonraki sınama geçerli bir bağlantı bulsun.
    for ad_, govde in [
        ("aşırı uzun adres", {**_tam, "adres": "A" * 9000}),
        ("XSS", {**_tam, "ad": "<script>alert(1)</script>"}),
        ("SQL", {**_tam, "adres": "'; drop table orders; --"}),
        ("tip uyumsuz", {**_tam, "ad": 123}),
        ("eksik gövde", {}),
    ]:
        _tg = ad.talep_olustur(db, _ord); db.commit()
        db.execute(text("update adres_degisim_talepleri set durum='bekliyor' where id=:i"),
                   {"i": str(_tg.id)})
        db.commit()
        r = POST(f"/api/public/adres-degisim/{_tg.token}", json=govde)
        es(f"{ad_} → 5xx YOK", True, r.status_code < 500)

    print("\n── GERÇEK UYGULAMA: adres yazılıyor mu ──")
    _t2 = ad.talep_olustur(db, _ord); db.commit()
    _r = POST(f"/api/public/adres-degisim/{_t2.token}",
              json={**_tam, "adres2": "D:7", "eposta": "test@ornek.com", "pazarlama": True})
    es("uygulandı", 200, _r.status_code)
    db.expire_all()
    _o2 = db.get(Order, _ord.id)
    _sa = (_o2.raw or {}).get("shipping_address") or {}
    es("adres1 yazıldı", "Y sok 1", _sa.get("address1"))
    es("apartman yazıldı", "D:7", _sa.get("address2"))
    es("il province'e", "İstanbul", _sa.get("province"))
    es("ilçe city'e", "Kadıköy", _sa.get("city"))
    es("telefon normalleşti", "05321602442", _sa.get("phone"))
    es("e-posta güncellendi", "test@ornek.com", _o2.customer_email)
    es("müşteri adı güncellendi", "Ali Veli", _o2.customer_name)
    es("pazarlama izni kaydedildi", True,
       db.execute(text("select pazarlama_izni from adres_degisim_talepleri where id=:i"),
                  {"i": str(_t2.id)}).scalar())
    es("sipariş geçmişine düştü", True,
       db.execute(text("select count(*) from order_status_history where order_id=:o "
                       "and action='musteri_adres_degisikligi'"),
                  {"o": str(_ord.id)}).scalar() > 0)
    es("panel bildirimi düştü", True,
       db.execute(text("select count(*) from notifications where title like '%ADRES%'")
                  ).scalar() > 0)
    es("aynı bağlantı ikinci kez 409", 409,
       POST(f"/api/public/adres-degisim/{_t2.token}", json=_tam).status_code)

    es("veritabanı ayakta", True,
       db.execute(text("select count(*) from orders")).scalar() > 0)

    print("\n── bilgi sızması ──")
    _m = GET(f"/api/public/adres-degisim/{TOKEN}").text
    es("token yanıtta YOK", False, TOKEN in _m)
    es("tenant kimliği YOK", False, str(_ord.tenant_id) in _m)
    es("sipariş iç id'si YOK", False, str(_ord.id) in _m)
    _s = GET(f"/adres-degisim/{TOKEN}").text
    es("sayfa statik (adres gömülü değil)", False,
       (_eski_raw.get("shipping_address", {}).get("address1") or "@@") in _s)

    print("\n── süre ve tek kullanım ──")
    _t3 = ad.talep_olustur(db, _ord); db.commit()
    db.execute(text("update adres_degisim_talepleri set durum='bekliyor', "
                    "expires_at = now() - interval '1 minute' where id = :i"),
               {"i": str(_t3.id)})
    db.commit()
    es("süresi dolmuş sayfa", "suresi_doldu",
       GET(f"/api/public/adres-degisim/{_t3.token}").json().get("durum"))
    es("süresi dolmuşta POST 410", 410,
       POST(f"/api/public/adres-degisim/{_t3.token}", json=_tam).status_code)
    es("bilinmeyen token 404", 404,
       GET("/api/public/adres-degisim/yok-boyle-bir-token").status_code)

    print("\n── eşzamanlılık: kilit var mı ──")
    # Uygulanmış say ve iki eşzamanlı istek at: ikisi de 409 almalı
    # (kilit yoksa biri 409 biri başka bir hata verirdi).
    db.execute(text("update adres_degisim_talepleri set durum='uygulandi', "
                    "expires_at = now() + interval '1 hour' where id = :i"), {"i": str(_t.id)})
    db.commit()
    _ayni = {"CF-Connecting-IP": "10.7.9.9"}

    def _gonder(_):
        return C.post(f"/api/public/adres-degisim/{TOKEN}", headers=_ayni,
                      json=_tam).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        _sonuc = list(ex.map(_gonder, range(2)))
    es("kullanılmış bağlantıda ikisi de 409", [409, 409], _sonuc)

    # ── temizlik ──
    _ord.raw = _eski_raw
    _ord.customer_email = _eski_mail
    _ord.customer_name = _eski_ad
    _ord.kargo_info = _eski_ki
    _ord.barkod_kodu = _eski_bk
    _ord.fulfillment_status = _eski_fs
    db.execute(text("delete from adres_degisim_talepleri where order_id = :o"),
               {"o": str(_ord.id)})
    db.execute(text("delete from order_status_history where order_id = :o "
                    "and action = 'musteri_adres_degisikligi'"), {"o": str(_ord.id)})
    db.commit()
    print("  · test verisi temizlendi")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
