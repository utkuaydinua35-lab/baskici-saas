"""Tasarım talebine ÖZEL ürün — yalnız linkle görünür, sepet/ödeme normal işler.

Kontrol edilenler:
  • panel: baskı dosyası + fiyat → ürün (status='ozel'), tasarım kaydı bağlı,
    model seti uygulanmış, kılıfa giydirilmiş fotoğraf + düz tasarım görseli
  • vitrin: ürün adresiyle AÇILIR; listede/aramada/katalog akışında YOK
  • sepet teklifi ve kargo: sepetteki her ürün gibi (ücretsiz kargo sınırı dahil)
  • bildirim: e-posta link+fiyatla gider, WhatsApp bağlantısı ülke kodlu numarayla
  • güncelleme (fiyat), satıştan kaldırma (link 404) ve yeniden açma
  • müşteri hesabında "Ürünüme git"
"""
from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (CaseTemplate, CatalogImage, CatalogProduct, Customer, Design,  # noqa: E402
                        DesignRequest, Store, Tenant, User, VariantSet)
from app.services import email_service  # noqa: E402
from app.services import storage as storage_svc  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


gonderilen: list[tuple] = []
email_service.send_email = lambda to, konu, html, *a, **k: gonderilen.append((to, konu, html)) or True

db = SessionLocal()
IZ = f"ozel{uuid.uuid4().hex[:6]}"
tenant = db.scalar(select(Tenant).limit(1))
admin = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                     User.role.in_(["owner", "yonetici"])).limit(1))
H = {"Authorization": "Bearer " + create_access_token(
    user_id=str(admin.id), tenant_id=str(admin.tenant_id), email=admin.email, expires_minutes=30)}
c = TestClient(app)

st = Store(tenant_id=tenant.id, slug=f"{IZ}-v", name="Özel Test", platform="storefront",
           config={"storefront_url": "https://ornek.test", "free_shipping_over": 500,
                   "shipping_fee": 60})
db.add(st); db.flush()
vs = VariantSet(tenant_id=tenant.id, store_id=st.id, name="Kılıf modelleri", items=[
    {"model_key": "iphone-15", "model_display": "iPhone 15"},
    {"model_key": "galaxy-s24", "model_display": "Galaxy S24"}])
db.add(vs)
kyol = storage_svc.STORAGE_ROOT / "tenants" / "_test" / f"{IZ}-kilif.png"
kyol.parent.mkdir(parents=True, exist_ok=True)
Image.new("RGBA", (200, 400), (30, 30, 30, 255)).save(kyol)
tpl = CaseTemplate(tenant_id=tenant.id, store_id=st.id, key=f"{IZ}", label="Siyah",
                   image_path=kyol.relative_to(storage_svc.STORAGE_ROOT).as_posix(),
                   area_x=0.1, area_y=0.1, area_w=0.8, area_h=0.8, area_radius=0.1,
                   cutouts=[], print_width_mm=70, print_height_mm=145, is_active=True)
db.add(tpl)
eposta = f"{IZ}@ornek.test"
db.add(Customer(tenant_id=tenant.id, email=eposta, name="Ayşe Kaya", phone="0532 111 22 33"))
r = DesignRequest(tenant_id=tenant.id, store_id=st.id, customer_email=eposta, customer_name="Ayşe Kaya",
                  image_url="/storage/yok.png", phone_model="iPhone 15")
db.add(r); db.commit()
rid = str(r.id)

buf = io.BytesIO()
Image.new("RGB", (700, 1450), (220, 30, 60)).save(buf, "PNG")
baski = buf.getvalue()
urun_id = None
try:
    print("\n── Ürün oluşturma ──")
    yok = c.post(f"/api/design-requests/{rid}/urun", headers=H, data={"fiyat": "449"})
    es("baskı dosyası olmadan ürün kurulmaz", 422, yok.status_code)
    s = c.get(f"/api/design-requests/secenekler?store_id={st.id}", headers=H).json()
    es("seçenekler: varsayılan model seti ve kılıf", (str(vs.id), [str(tpl.id)]),
       (s["varsayilan_set"], [k["id"] for k in s["kiliflar"]]))
    res = c.post(f"/api/design-requests/{rid}/urun", headers=H,
                 data={"fiyat": "449.9", "template_id": str(tpl.id)},
                 files={"baski": ("tasarim.png", baski, "image/png")})
    es("ürün oluştu", 200, res.status_code)
    t = res.json()
    u = t["urun"]
    urun_id = u["id"]
    es("başlık müşterinin adıyla, fiyat doğru, satışta", ("Özel Tasarım Kılıf — Ayşe", 449.9, True),
       (u["title"], u["price"], u["satista"]))
    es("link tahmin edilemez adres", True, u["url"].startswith("https://ornek.test/urun/ozel-") and len(u["slug"]) == 15)
    es("talep durumu 'teklif'e geçti", "teklif", t["status"])
    es("müşteri telefonu panelde görünür", "0532 111 22 33", t["customer_phone"])
    db.expire_all()
    p = db.get(CatalogProduct, uuid.UUID(urun_id))
    es("ürün durumu 'ozel'", "ozel", p.status)
    es("model seti uygulandı (2 model)", ["Galaxy S24", "iPhone 15"], sorted(v.model_display for v in p.variants))
    d = db.get(Design, p.design_id) if p.design_id else None
    es("baskı dosyası tasarım kaydı olarak bağlı (kalıp planlayıcı bulur)", (True, "png", True),
       (d is not None, d.file_format if d else None, bool(d and d.is_kisiye_ozel)))
    gorseller = sorted(db.scalars(select(CatalogImage).where(CatalogImage.product_id == p.id)).all(),
                       key=lambda im: im.position)
    es("iki görsel: kılıfa giydirilmiş kapak + düz tasarım", 2, len(gorseller))
    kapak = Image.open(storage_svc.STORAGE_ROOT / gorseller[0].file_path)
    es("kapak kare ve tasarım kılıfın üstünde (kırmızı)", (True, True),
       (kapak.width == kapak.height,
        (lambda px: px[0] > 150 and px[1] < 90)(kapak.convert("RGB").getpixel((kapak.width // 2, kapak.height // 2)))))

    print("\n── Vitrin: yalnız linkle ──")
    pd = c.get(f"/api/shop/{st.slug}/products/{p.slug}")
    es("ürün adresiyle açılır, 'ozel' işaretli", (200, True), (pd.status_code, pd.json().get("ozel")))
    liste = c.get(f"/api/shop/{st.slug}/products").json()
    sluglar = [x.get("slug") for x in (liste.get("products") or liste.get("items") or [])]
    es("ürün listesinde YOK", False, p.slug in sluglar)
    ara = c.get(f"/api/shop/{st.slug}/products?q=Özel").json()
    es("aramada YOK", False, p.slug in [x.get("slug") for x in (ara.get("products") or ara.get("items") or [])])
    feed = c.get(f"/api/shop/{st.slug}/feed/meta.xml")
    es("Meta katalog akışında YOK", False, p.slug in feed.text)

    print("\n── Sepet: her ürün gibi ──")
    vid = str(next(v.id for v in p.variants if v.model_display == "iPhone 15"))
    q1 = c.post(f"/api/shop/{st.slug}/checkout/quote", json={"items": [{"variant_id": vid, "quantity": 1}]}).json()
    es("teklif geçerli, kargo ücretli (sınır altı)", (True, "449.90", 60.0),
       (q1.get("valid", True), q1.get("items_total") or q1.get("subtotal"), float(q1.get("shipping") or -1)))
    q2 = c.post(f"/api/shop/{st.slug}/checkout/quote", json={"items": [{"variant_id": vid, "quantity": 2}]}).json()
    es("2 adet: ücretsiz kargo sınırı aşıldı", 0.0, float(q2.get("shipping") or -1))

    print("\n── Bildirim: e-posta + WhatsApp ──")
    gonderilen.clear()
    b = c.patch(f"/api/design-requests/{rid}", headers=H,
                json={"admin_note": "Kalıp onaylandı", "notify_customer": True}).json()
    es("e-posta gitti", (True, 1, eposta), (b["notified"], len(gonderilen), gonderilen[0][0] if gonderilen else None))
    html = gonderilen[0][2] if gonderilen else ""
    es("e-postada link ve fiyat", True, u["url"] in html and "449,90 TL" in html)
    wa = b.get("whatsapp_url") or ""
    es("WhatsApp bağlantısı ülke kodlu numarayla", True, wa.startswith("https://wa.me/905321112233?text="))
    metin = unquote(wa.split("text=", 1)[-1])
    es("WhatsApp mesajında link, fiyat ve not", True,
       u["url"] in metin and "449,90 TL" in metin and "Kalıp onaylandı" in metin)
    db.expire_all()
    es("bildirim zamanı kaydedildi", True, db.get(DesignRequest, uuid.UUID(rid)).bildirildi_at is not None)

    print("\n── Güncelleme, kaldırma, geri açma ──")
    g = c.post(f"/api/design-requests/{rid}/urun", headers=H, data={"fiyat": "399"}).json()
    db.expire_all()
    es("dosyasız güncelleme: fiyat değişti, görseller kaldı", (399.0, 2),
       (g["urun"]["price"], len(db.scalars(select(CatalogImage).where(CatalogImage.product_id == p.id)).all())))
    es("aynı ürün (link değişmedi)", u["slug"], g["urun"]["slug"])
    k = c.delete(f"/api/design-requests/{rid}/urun", headers=H).json()
    es("satıştan kaldırıldı", False, k["urun"]["satista"])
    es("kaldırılan ürünün linki açılmaz", 404, c.get(f"/api/shop/{st.slug}/products/{p.slug}").status_code)
    q3 = c.post(f"/api/shop/{st.slug}/checkout/quote", json={"items": [{"variant_id": vid, "quantity": 1}]}).json()
    es("kaldırılan ürün sepetten satın alınamaz", False, q3.get("valid", True))
    c.post(f"/api/design-requests/{rid}/urun", headers=H, data={"fiyat": "399"})
    es("yeniden kaydedince link tekrar açılır", 200, c.get(f"/api/shop/{st.slug}/products/{p.slug}").status_code)
finally:
    db.rollback()
    if urun_id:
        for im in db.scalars(select(CatalogImage).where(CatalogImage.product_id == uuid.UUID(urun_id))).all():
            storage_svc.delete_catalog_image(im.file_path)
    rr = db.get(DesignRequest, uuid.UUID(rid))
    if rr:
        db.delete(rr)
    if urun_id:
        pp = db.get(CatalogProduct, uuid.UUID(urun_id))
        if pp:
            dd = db.get(Design, pp.design_id) if pp.design_id else None
            db.delete(pp)
            if dd:
                storage_svc.delete_design_file(dd.file_path)
                db.delete(dd)
    for m in db.scalars(select(Customer).where(Customer.email == eposta)).all():
        db.delete(m)
    db.flush()
    db.delete(db.get(Store, st.id))
    db.commit()
    kyol.unlink(missing_ok=True)
    db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
