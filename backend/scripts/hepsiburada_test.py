"""Hepsiburada kanalı — uçtan uca: form kuralı, özel etiket, paketleme akışı.

Sınananlar:
  • maskeleme / kod doğrulama (saf fonksiyonlar)
  • bayi: kod ZORUNLU, boşluklar atılır, firma varsayılan Sürat, geçersiz firma 400
  • bayi: kod düzeltme (adres ucu) + geçersiz kod reddi
  • yönetim: /label ve /zpl özel Hepsiburada etiketini verir (barkod = kod, ^BC)
  • kargo-gönder: YENİ gönderi AÇMAZ, kayıt 'hepsiburada', aşama 8,
    bayi mağazasında "Shopify'a yazılamadı" uyarısı DÜŞMEZ
Test verisi 'hbtest' önekiyle açılır ve sonunda silinir.
"""
from __future__ import annotations

import io
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Dealer, Notification, Order, Store, Tenant, User  # noqa: E402
from app.services import hepsiburada as hb  # noqa: E402

ISTEMCI = TestClient(app)
GECTI = KALDI = 0
IZ = f"hbtest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


print("\n── 1. Saf kurallar ──")
es("maske: sözcük başına ilk 3 harf", "AYŞ* NUR YIL***", hb.maskele("Ayşe Nur Yılmaz"))
es("maske: Türkçe büyük İ", "İSM***", hb.maskele("ismail"))
es("maske: boş ad", "***", hb.maskele(""))
es("kod: iç boşluklar atılır", "4010591345312288", hb.kod_dogrula(" 4010 5913 4531 2288 "))
for kotu, ad in (("", "boş"), ("12345", "çok kısa"), ("ABC$1234", "özel karakter"), ("ŞÇ123456", "Türkçe harf")):
    try:
        hb.kod_dogrula(kotu); es(f"kod reddedilir: {ad}", "hata", "geçti")
    except hb.KodHatasi:
        es(f"kod reddedilir: {ad}", "hata", "hata")
es("firma: boş -> sürat", "surat", hb.firma_dogrula(""))

# ─── Kurulum ───
db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
d = Dealer(tenant_id=tenant.id, name=f"{IZ}-bayi", unit_price=100, shipping_fee=50,
           currency="TRY", is_active=True, balance=0, balance_usd=0)
db.add(d); db.flush()
st = Store(tenant_id=tenant.id, slug=f"{IZ}-magaza", name="Bayii HB", platform="bayii", is_active=True)
db.add(st); db.flush()
d.store_id = st.id
kul = User(tenant_id=tenant.id, email=f"{IZ}.bayi@test.example.com",
           password_hash=hash_password("Portal12345!"), full_name="HB Bayi",
           role="bayii_portal", permissions=["bayii_portal"], dealer_id=d.id, is_active=True)
yon = User(tenant_id=tenant.id, email=f"{IZ}.admin@test.example.com",
           password_hash=hash_password("Portal12345!"), full_name="HB Admin",
           role="yonetici", permissions=[], is_active=True)
db.add_all([kul, yon]); db.commit()


def token(email):
    r = ISTEMCI.post("/api/auth/login", json={"email": email, "password": "Portal12345!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


H_B, H_Y = token(kul.email), token(yon.email)


def jpg():
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (64, 64), (200, 90, 20)).save(b, "JPEG"); return b.getvalue()


def ac(**alan):
    veri = {"kanal": "hepsiburada", "ad_soyad": "Ayşe Yılmaz", "model": "IPHONE-15", "adet": "1"}
    veri |= alan
    return ISTEMCI.post("/api/bayii/siparis", headers=H_B, data=veri,
                        files=[("tasarim", ("t.jpg", jpg(), "image/jpeg"))])


try:
    print("\n── 2. Bayi formu ──")
    es("kodsuz 400", 400, ac().status_code)
    es("kodsuz hata metni", True, "entegrasyon kodu" in ac().json().get("detail", ""))
    es("geçersiz firma 400", 400, ac(kargo_kodu="4010591345312288", kargo_firma="dhl").status_code)
    r = ac(kargo_kodu="4010 5913 4531 2288")
    es("kodlu 201 (adres istenmez)", 201, r.status_code)
    oid = r.json()["id"]
    det = ISTEMCI.get(f"/api/bayii/siparis/{oid}", headers=H_B).json()
    es("kod boşluksuz kaydedildi", "4010591345312288", det.get("kargo_kodu"))
    es("firma varsayılan sürat", "surat", det.get("kargo_firma"))
    es("kanal hepsiburada", "hepsiburada", det.get("kanal"))
    o = db.get(Order, uuid.UUID(oid)); db.refresh(o)
    es("kargo ücreti yazılmaz (Trendyol gibi)", "0", (o.raw or {}).get("shipping_fee"))

    print("\n── 3. Kod düzeltme ──")
    es("geçersiz kodla düzeltme 400", 400, ISTEMCI.patch(
        f"/api/bayii/siparis/{oid}/adres", headers=H_B,
        json={"ad_soyad": "Ayşe Yılmaz", "kargo_kodu": "12"}).status_code)
    r = ISTEMCI.patch(f"/api/bayii/siparis/{oid}/adres", headers=H_B,
                      json={"ad_soyad": "Ayşe Yılmaz", "kargo_kodu": "7300123456789012", "kargo_firma": "aras"})
    es("düzeltme 200 + değişiklik", (200, True), (r.status_code, r.json().get("degisiklik")))
    det = ISTEMCI.get(f"/api/bayii/siparis/{oid}", headers=H_B).json()
    es("yeni kod + firma", ("7300123456789012", "aras"), (det.get("kargo_kodu"), det.get("kargo_firma")))
    r = ISTEMCI.patch(f"/api/bayii/siparis/{oid}/adres", headers=H_B,
                      json={"ad_soyad": "Ayşe Yılmaz", "kargo_firma": "surat"})
    es("kod verilmeden firma değişir, kod korunur", "7300123456789012",
       ISTEMCI.get(f"/api/bayii/siparis/{oid}", headers=H_B).json().get("kargo_kodu"))

    print("\n── 4. Etiket ──")
    r = ISTEMCI.get(f"/api/packaging/order/{oid}/label", headers=H_Y)
    es("label PDF", (200, "application/pdf"), (r.status_code, r.headers.get("content-type")))
    # PyMuPDF sözcük arasını bölünmez boşluk (\xa0) olarak çıkarıyor
    metin = fitz.open("pdf", r.content)[0].get_text().replace("\xa0", " ")
    es("etikette maskeli ad", True, "AYŞ* YIL***" in metin)
    es("etikette tam ad YOK", False, "YILMAZ" in metin.upper())
    es("etikette firma", True, "SÜRAT KARGO" in metin)
    es("etikette kod rakamları", True, "7300123456789012" in metin)
    es("mağaza adı / sipariş no yok", False, "Bayii" in metin or "#B" in metin)
    for tip in ("adres", "kargo"):
        z = ISTEMCI.get(f"/api/packaging/order/{oid}/zpl?tip={tip}&w_mm=100&h_mm=150", headers=H_Y)
        bc = re.search(r"\^BC[^\^]*\^FD([^\^]*)\^FS", z.text)
        es(f"ZPL ({tip}): yazıcı barkodu = kod", ">;7300123456789012", bc.group(1) if bc else z.text[:120])
    r = ISTEMCI.get(f"/api/packaging/order/{oid}/kargo-label", headers=H_Y)
    es("kargo-label (yeniden yazdır) PDF", (200, "application/pdf"),
       (r.status_code, r.headers.get("content-type")))

    print("\n── 5. Kargoya ver ──")
    once_bildirim = db.scalar(select(text("count(*)")).select_from(Notification).where(
        Notification.store_id == st.id, Notification.title.like("%Shopify%")))
    r = ISTEMCI.post(f"/api/packaging/order/{oid}/kargo-gonder", headers=H_Y, json={})
    es("kargo-gönder 200", 200, r.status_code)
    j = r.json()
    es("takip no = kod, firma Sürat", ("7300123456789012", "Sürat Kargo"),
       (j.get("takip_no"), j.get("handler_name")))
    db.expire_all(); o = db.get(Order, uuid.UUID(oid))
    es("kayıt sağlayıcısı hepsiburada", "hepsiburada", (o.kargo_info or {}).get("provider"))
    es("aşama 8", 8, o.current_stage)
    sonra_bildirim = db.scalar(select(text("count(*)")).select_from(Notification).where(
        Notification.store_id == st.id, Notification.title.like("%Shopify%")))
    es("bayi siparişinde Shopify uyarısı DÜŞMEDİ", once_bildirim, sonra_bildirim)
    r = ISTEMCI.post(f"/api/packaging/order/{oid}/kargo-iptal", headers=H_Y)
    db.expire_all(); o = db.get(Order, uuid.UUID(oid))
    es("kargo iptali geri alır (aşama 7)", (200, 7, None), (r.status_code, o.current_stage, o.kargo_info))

    print("\n── 6. Kodsuz eski kayıt ──")
    raw = dict(o.raw); raw.pop("kargo_entegrasyon_kodu"); o.raw = raw; db.commit()
    es("kodsuz sipariş kargoya verilemez", 400,
       ISTEMCI.post(f"/api/packaging/order/{oid}/kargo-gonder", headers=H_Y, json={}).status_code)
    es("kodsuz etikette 400", 400, ISTEMCI.get(f"/api/packaging/order/{oid}/label", headers=H_Y).status_code)
finally:
    print("\n── Temizlik ──")
    db.rollback()
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.store_id == st.id)).all()]
    if oids:
        for q in ("delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    db.execute(text("delete from notifications where store_id = :s").bindparams(s=st.id))
    db.execute(text("delete from designs where store_id = :s").bindparams(s=st.id))
    db.execute(text("delete from users where email like :p").bindparams(p=f"{IZ}%"))
    db.execute(text("delete from dealers where name like :p").bindparams(p=f"{IZ}%"))
    db.execute(text("delete from stores where slug like :p").bindparams(p=f"{IZ}%"))
    db.commit()
    print("  temizlendi")

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
