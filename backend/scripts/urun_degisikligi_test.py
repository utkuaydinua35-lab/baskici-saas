"""Müşterinin değişiklik bağlantısından ÜRÜN değiştirmesi — #11701 senaryosu.

Kişiye özel fotoğraflı kılıf; müşteri bağlantıdan başka bir tasarım seçiyor.
Sınananlar:
  • tasarımı sistemde OLMAYAN ürün → kalem "tasarım bekliyor", KALIBA GİRMEZ
  • operatör tasarım kodu bağlar → yeni tasarımla planlanır, kişiye özel sayılmaz
  • tasarımı TEK olan ürün → otomatik bağlanır
  • birden fazla aday → bekler (tahmin yok); "tekrar ara" 409; "yok say" → eski tasarım
  • Shopify senkronu kaydı SİLMEZ (raw/title/product_id ezilse de)
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Design, KisiyeOzelProduct, LineItem, Order, Store, Tenant, User  # noqa: E402
from app.routers import orders as orders_router  # noqa: E402
from app.services import mold_planner, model_degisim as md, urun_katalog  # noqa: E402

GECTI = KALDI = 0
IZ = f"udtest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yon = db.scalar(select(User).where(User.tenant_id == tenant.id, User.role.in_(["owner", "yonetici"])).limit(1))
if yon is None:
    print("yönetici yok — atlandı\nGECTI: 0   KALDI: 0"); sys.exit(0)
H = {"Authorization": "Bearer " + create_access_token(
    user_id=str(yon.id), tenant_id=str(tenant.id), email=yon.email, expires_minutes=30)}
c = TestClient(app)

# Sahte Shopify kataloğu — gerçek API'ye gidilmesin
KATALOG = [{"id": "P-YOK", "baslik": "Cosmic Evil Eye", "gorsel": "https://x/cosmic.jpg"},
           {"id": "P-OK", "baslik": "Blueberry Black Cats", "gorsel": "https://x/blue.jpg"},
           {"id": "P-IKI", "baslik": "İki Tasarımlı", "gorsel": None}]
urun_katalog.ham_urunler = lambda db, tid, store=None: KATALOG

st = Store(tenant_id=tenant.id, slug=f"{IZ}-s", name="UD Shopify", platform="shopify", is_active=True, config={})
db.add(st); db.flush()
db.add(KisiyeOzelProduct(tenant_id=tenant.id, store_id=st.id, product_id="P-KO", product_title="Kişiye Özel Çerçeveli"))


def tasarim(kod, pid, kalip):
    d = Design(tenant_id=tenant.id, store_id=st.id, code=f"{IZ[-4:]}{kod}", name=kod, file_path=f"x/{kod}.png",
               file_format="png", product_id=pid, kalip_tipi=kalip)
    db.add(d); db.flush(); return d


d_ko = tasarim("ko", None, "seffaf")          # müşterinin fotoğrafı
d_ok = tasarim("ok", "P-OK", "seffaf")
d_iki1 = tasarim("i1", "P-IKI", "siyah")
d_iki2 = tasarim("i2", "P-IKI", "beyaz")
d_elle = tasarim("el", None, "parlak")

o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-o", order_number=f"{IZ}1",
          customer_name="Ayşe Yılmaz", current_stage=2,
          raw={"id": f"{IZ}-o", "shipping_address": {"name": "Ayşe", "phone": "05321602442"}})
db.add(o); db.flush()
li = LineItem(tenant_id=tenant.id, order_id=o.id, external_id=f"{IZ}-li", product_id="P-KO",
              title="Kişiye Özel Çerçeveli", quantity=1, device_model_override="iPhone 15",
              assigned_design_id=d_ko.id, kilif_varyasyon="ŞEFFAF", properties=[])
db.add(li); db.commit()


def musteri_secer(urun_id):
    t = md.talep_olustur(db, o, li, urun_adi="x", model="iPhone 15", mold_variation="ŞEFFAF")
    db.commit()
    return c.post(f"/api/public/model-degisim/{t.token}", json={"urun_id": urun_id})


def plan_kalem():
    db.expire_all()
    p = mold_planner.plan_molds(db, tenant_id=tenant.id, store_id=st.id)
    benim = [u for m in p["molds"] for u in m["items"] if u.get("line_item_id") == str(li.id)]
    eksik = [e["reason"] for e in p["eksikler"] if e.get("order_number") == o.order_number]
    return benim, eksik


def kalem():
    db.expire_all(); return db.get(LineItem, li.id)


try:
    print("\n── Tasarımı olmayan ürün ──")
    es("müşteri seçimi 200", 200, musteri_secer("P-YOK").status_code)
    k = kalem()
    es("bekliyor", "bekliyor", (k.urun_degisikligi or {}).get("durum"))
    es("seçilen başlık kayıtlı", "Cosmic Evil Eye", k.urun_degisikligi.get("baslik"))
    es("önceki hal kayıtlı", str(d_ko.id), k.urun_degisikligi["onceki"]["assigned_design_id"])
    es("eski tasarım DEĞİŞMEDİ (henüz)", d_ko.id, k.assigned_design_id)
    birim, eksik = plan_kalem()
    es("KALIBA GİRMEZ", [], birim)
    es("eksik sebebi görünür", True, "urun_degisikligi_bekliyor" in eksik)
    det = c.get(f"/api/orders/{o.id}/detail", headers=H).json()
    es("sipariş detayında görünür", "bekliyor", det["line_items"][0]["urun_degisikligi"]["durum"])

    print("\n── Senkron kaydı silmez ──")
    orders_router._upsert_order(db, tenant_id=tenant.id, store_id=st.id, raw={
        "id": f"{IZ}-o", "order_number": f"{IZ}1", "name": "#x", "created_at": "2026-09-14T10:00:00Z",
        "line_items": [{"id": f"{IZ}-li", "product_id": "P-KO", "title": "Kişiye Özel Çerçeveli", "quantity": 1}]})
    db.commit()
    es("senkron sonrası hâlâ bekliyor", "bekliyor", (kalem().urun_degisikligi or {}).get("durum"))

    print("\n── Operatör tasarım kodu bağlar ──")
    es("olmayan kod 404", 404, c.post(f"/api/orders/{o.id}/line-items/{li.id}/urun-degisikligi", headers=H,
                                      json={"islem": "kod", "tasarim_kodu": "yokboyle"}).status_code)
    r = c.post(f"/api/orders/{o.id}/line-items/{li.id}/urun-degisikligi", headers=H,
               json={"islem": "kod", "tasarim_kodu": d_elle.code})
    es("bağla 200", 200, r.status_code)
    k = kalem()
    es("uygulandı + yeni tasarım", ("uygulandi", d_elle.id), (k.urun_degisikligi["durum"], k.assigned_design_id))
    es("kılıf türü yeni tasarımdan", "PARLAK", k.kilif_varyasyon)
    birim, _ = plan_kalem()
    es("yeni tasarımla planlandı", [str(d_elle.id)], [u["design_id"] for u in birim])
    es("artık kişiye özel sayılmaz", [False], [u["is_kisiye_ozel"] for u in birim])

    print("\n── Tek tasarımlı ürün → otomatik ──")
    musteri_secer("P-OK")
    k = kalem()
    es("otomatik bağlandı", ("uygulandi", d_ok.id), (k.urun_degisikligi["durum"], k.assigned_design_id))
    es("ilk (orijinal) hal korunur", str(d_ko.id), k.urun_degisikligi["onceki"]["assigned_design_id"])

    print("\n── Belirsiz ürün → bekler, tahmin yok ──")
    musteri_secer("P-IKI")
    k = kalem()
    es("iki aday → bekliyor", "bekliyor", k.urun_degisikligi["durum"])
    es("tekrar ara 409 (hâlâ belirsiz)", 409, c.post(f"/api/orders/{o.id}/line-items/{li.id}/urun-degisikligi",
                                                     headers=H, json={"islem": "tekrar"}).status_code)
    r = c.post(f"/api/orders/{o.id}/line-items/{li.id}/urun-degisikligi", headers=H, json={"islem": "yoksay"})
    es("yok say 200", 200, r.status_code)
    es("yok sayıldı", "yoksayildi", kalem().urun_degisikligi["durum"])
    birim, _ = plan_kalem()
    es("yok sayınca kalem yine planlanır", 1, len(birim))
finally:
    db.rollback()
    db.execute(text("delete from model_degisim_talepleri where order_id = :o").bindparams(o=o.id))
    db.execute(text("delete from order_status_history where order_id = :o").bindparams(o=o.id))
    db.execute(text("delete from notifications where store_id = :s").bindparams(s=st.id))
    db.execute(text("delete from line_items where order_id = :o").bindparams(o=o.id))
    db.execute(text("delete from orders where id = :o").bindparams(o=o.id))
    db.execute(text("delete from designs where store_id = :s").bindparams(s=st.id))
    db.execute(text("delete from kisiye_ozel_products where store_id = :s").bindparams(s=st.id))
    db.execute(text("delete from stores where id = :s").bindparams(s=st.id))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
