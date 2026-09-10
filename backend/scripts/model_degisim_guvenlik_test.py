"""Model değişikliği bağlantısı — güvenlik ve sağlamlık.

Bu sayfa AUTH'SUZ ve müşterinin adres/telefon bilgisini gösteriyor; üstelik
uygulanan değişiklik ÜRETİMİ etkiliyor (kalem kalıptan çekiliyor). Yani
saldırı yüzeyi gerçek. Burada sınananlar:

  KİMLİK / ERİŞİM
    · token tahmin edilemez mi (uzunluk + entropi)
    · başka bir siparişin token'ıyla bu siparişe müdahale edilebiliyor mu
    · süresi dolmuş / kullanılmış token reddediliyor mu
    · token olmadan uçlar erişilebiliyor mu

  YETKİ SINIRI (asıl risk)
    · ürün id'si BAŞKA bir koleksiyondan verilirse
    · model listede olmayan bir değerse
    · Special'da stokta OLMAYAN model doğrudan istekle gönderilirse
    · başka tenant'ın kalemi hedeflenirse

  GİRDİ DAYANIKLILIĞI
    · aşırı uzun / boş / tip uyumsuz gövde
    · XSS denemesi (sayfa metni kaçırıyor mu)
    · SQL enjeksiyon denemesi
    · eşzamanlı iki istek (çift uygulama)

  BİLGİ SIZMASI
    · yanıtta e-posta / token / iç kimlik sızıyor mu
    · hata mesajları sistem detayı veriyor mu
"""
from __future__ import annotations

import concurrent.futures
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LineItem, Order  # noqa: E402
from app.services import model_degisim as md  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


C = TestClient(app)
db = SessionLocal()


# Hız sınırı IP başına (services/rate_limit.py, CF-Connecting-IP önceliği).
# Her BÖLÜM için ayrı IP kullanıyoruz: aksi halde testin kendi trafiği
# sınıra takılıp sonraki doğrulamaları anlamsız kılıyor — nitekim ilk
# denemede tam olarak bu oldu.
_SAYAC = [0]


def _ip() -> dict:
    _SAYAC[0] += 1
    return {"CF-Connecting-IP": f"10.9.0.{_SAYAC[0]}"}


def GET(yol: str, **kw):
    return C.get(yol, headers=_ip(), **kw)


def POST(yol: str, **kw):
    return C.post(yol, headers=_ip(), **kw)

_oid = db.execute(select(LineItem.order_id).group_by(LineItem.order_id)
                  .having(func.count() > 1).limit(1)).scalar()
if _oid is None:
    print("Uygun sipariş yok — sınama atlandı.")
    sys.exit(0)

_ord = db.get(Order, _oid)
_li = db.scalar(select(LineItem).where(LineItem.order_id == _oid).limit(1))
_t = md.talep_olustur(db, _ord, _li, urun_adi="Güvenlik Testi",
                      model="iPhone 14 Pro", mold_variation="PARLAK")
db.commit()
TOKEN = _t.token

_veri = GET(f"/api/public/model-degisim/{TOKEN}").json()
_markalar = _veri.get("markalar") or []
_hepsi = [m for g in _markalar for m in g["modeller"]]
_gecerli = next((m["deger"] for m in _hepsi if m.get("stokta")), None)
_stoksuz = next((m["deger"] for m in _hepsi if m.get("stokta") is False), None)

print("\n── token tahmin edilemez ──")
es("token en az 30 karakter", True, len(TOKEN) >= 30)
es("token'lar birbirinden farklı", 5,
   len({md.secrets.token_urlsafe(24) for _ in range(5)}))
es("bilinmeyen token 404", 404,
   GET(f"/api/public/model-degisim/{'a' * 32}").status_code)
es("boş token 404", 404, GET("/api/public/model-degisim/ ").status_code)
es("token'sız uç 404", 404, GET("/api/public/model-degisim/").status_code)

print("\n── yetki sınırı: geçersiz seçimler ──")
es("model listede yok → 400", 400,
   POST(f"/api/public/model-degisim/{TOKEN}",
          json={"model": "Nokia 3310 Ultra"}).status_code)
if _stoksuz:
    es("stokta OLMAYAN model → 400", 400,
       POST(f"/api/public/model-degisim/{TOKEN}",
              json={"model": _stoksuz}).status_code)
es("koleksiyonda olmayan ürün id → 400", 400,
   POST(f"/api/public/model-degisim/{TOKEN}",
          json={"urun_id": str(uuid.uuid4())}).status_code)
es("başka siparişin kalem id'si ürün sanılmıyor", 400,
   POST(f"/api/public/model-degisim/{TOKEN}",
          json={"urun_id": str(_li.id)}).status_code)
es("hem model hem ürün boş → 400", 400,
   POST(f"/api/public/model-degisim/{TOKEN}", json={}).status_code)

print("\n── adres bağlantısı ucu (token'a bağlı) ──")
# Bu uç, model bağlantısını elinde tutana adres değişikliği bağlantısı
# veriyor. Token yoksa/geçersizse hiçbir şey üretmemeli.
es("bilinmeyen token 404", 404,
   POST(f"/api/public/model-degisim/{'z' * 32}/adres-degisim").status_code)
es("token'sız uç 404", 404, POST("/api/public/model-degisim//adres-degisim").status_code)
es("GET ile çağrılamaz", 405,
   GET(f"/api/public/model-degisim/{TOKEN}/adres-degisim").status_code)
_ra = POST(f"/api/public/model-degisim/{TOKEN}/adres-degisim")
# 409 = bu siparişte kargo başlamış (kapı çalışıyor); ikisi de kabul, 5xx asla.
es("geçerli token'da 200 ya da 409", True, _ra.status_code in (200, 409))
if _ra.status_code == 200:
    es("yanıtta yalnız bağlantı var", ["link"], sorted(_ra.json().keys()))
    es("üretilen bağlantı model token'ını taşımıyor", False, TOKEN in _ra.text)
else:
    es("kapalıyken sebep var, sistem detayı yok", True,
       bool(_ra.json().get("detail")) and "sqlalchemy" not in _ra.text.lower())

print("\n── girdi dayanıklılığı ──")
for ad, govde in [
    ("aşırı uzun model", {"model": "A" * 5000}),
    ("aşırı uzun ürün id", {"urun_id": "B" * 5000}),
    ("model yerine sayı", {"model": 12345}),
    ("model yerine liste", {"model": ["x"]}),
    ("model yerine sözlük", {"model": {"a": 1}}),
    ("null gövde alanları", {"model": None, "urun_id": None}),
    ("XSS denemesi", {"model": "<script>alert(1)</script>"}),
    ("SQL denemesi", {"model": "'; drop table orders; --"}),
    ("boş dize", {"model": ""}),
    ("yalnız boşluk", {"model": "   "}),
]:
    r = POST(f"/api/public/model-degisim/{TOKEN}", json=govde)
    # 400 (reddedildi) ya da 422 (şema) kabul; 500 ASLA olmamalı
    es(f"{ad} → 5xx YOK", True, r.status_code < 500)

_r = POST(f"/api/public/model-degisim/{TOKEN}", json={"model": "x" * 200})
es("uzun girdide hata metni sistem detayı sızdırmıyor", True,
   all(k not in _r.text.lower() for k in
       ("traceback", "sqlalchemy", "psycopg", "select ", "line_items")))

print("\n── veritabanı hâlâ ayakta (enjeksiyon denemesi sonrası) ──")
es("orders tablosu duruyor", True,
   db.execute(text("select count(*) from orders")).scalar() > 0)

print("\n── bilgi sızması ──")
_metin = GET(f"/api/public/model-degisim/{TOKEN}").text
es("yanıtta e-posta YOK", False, "@" in _metin and (_ord.customer_email or "@@") in _metin)
es("yanıtta token YOK", False, TOKEN in _metin)
es("yanıtta tenant/iç kimlik YOK", False, str(_ord.tenant_id) in _metin)
es("yanıtta sipariş iç id'si YOK", False, str(_ord.id) in _metin)

print("\n── sayfa HTML'i kullanıcı verisi basmıyor (XSS) ──")
_sayfa = GET(f"/model-degisim/{TOKEN}").text
es("sayfa statik — sipariş verisi gömülü değil", False, (_ord.customer_name or "@@") in _sayfa)
es("kaçırma yardımcısı sayfada var", True, "const kacir" in _sayfa)

print("\n── eşzamanlı iki istek: yalnız BİRİ uygulanmalı ──")
# Aynı bağlantıya iki tarayıcıdan aynı anda basılırsa kalem İKİ kez
# işlenmemeli (kalıptan iki kez çekme / çift bildirim).
if _gecerli:
    _ayni = {"CF-Connecting-IP": "10.9.9.9"}   # tek kullanıcı, iki sekme

    def _gonder(_):
        return C.post(f"/api/public/model-degisim/{TOKEN}",
                      headers=_ayni, json={"model": _gecerli}).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        _sonuc = list(ex.map(_gonder, range(2)))
    es("tam olarak bir istek başarılı", 1, sum(1 for s in _sonuc if s == 200))
    es("öteki reddedildi (409)", True, any(s == 409 for s in _sonuc))
else:
    print("  · seçilebilir model yok — atlandı")

print("\n── kullanılmış bağlantı kapalı ──")
es("tekrar kullanım 409", 409,
   POST(f"/api/public/model-degisim/{TOKEN}", json={"model": _gecerli}).status_code)
es("sayfa 'uygulandi' diyor", "uygulandi",
   GET(f"/api/public/model-degisim/{TOKEN}").json().get("durum"))

print("\n── süresi dolmuş bağlantı ──")
_t2 = md.talep_olustur(db, _ord, None, urun_adi="Güvenlik Testi 2",
                       model="X", mold_variation="SİYAH")
db.commit()
db.execute(text("update model_degisim_talepleri set expires_at = now() - interval '1 second' "
                "where id = :i"), {"i": str(_t2.id)})
db.commit()
es("süresi dolmuşta POST 410", 410,
   POST(f"/api/public/model-degisim/{_t2.token}",
          json={"model": _gecerli}).status_code)
es("süresi dolmuşta veri 'suresi_doldu'", "suresi_doldu",
   GET(f"/api/public/model-degisim/{_t2.token}").json().get("durum"))
es("süresi 1 saniye dolmuş bile olsa kapalı", True,
   (_t2.expires_at - datetime.now(UTC)) < timedelta(seconds=0))

print("\n── hız sınırı ──")
_tekIp = {"CF-Connecting-IP": "10.9.8.8"}
_kodlar = [C.get(f"/api/public/model-degisim/{TOKEN}", headers=_tekIp).status_code
           for _ in range(25)]
es("aşırı istekte 429 devreye giriyor", True, 429 in _kodlar)
es("ilk istekler geçiyor (sınır makul)", True, _kodlar[0] != 429)
# Sınır IP BAŞINA olmalı: bir müşterinin taşması ötekini kilitlemesin.
es("başka IP etkilenmiyor", True,
   C.get(f"/api/public/model-degisim/{TOKEN}",
         headers={"CF-Connecting-IP": "10.9.7.7"}).status_code != 429)

# ── temizlik ──
db.execute(text("delete from adres_degisim_talepleri where order_id = :o"), {"o": str(_oid)})
db.execute(text("delete from model_degisim_talepleri where urun_adi like 'Güvenlik Testi%'"))
db.execute(text("delete from order_status_history where order_id = :o "
                "and action = 'musteri_model_degisikligi'"), {"o": str(_oid)})
db.commit()
print("\n  · test verisi temizlendi")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
