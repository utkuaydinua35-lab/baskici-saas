"""Bayi/vitrin kargosu Sürat'a doğrudan + Shopify pasifken sessizlik + eksik satırı bilgisi.

Sınananlar:
  • mağaza ayarı BOŞ olsa da (bayi/vitrin) kargo yolu Sürat'a doğrudan (Basit Kargo'ya gitmez)
  • eski mağaza ayarı 'ECONOMIC' bile olsa Sürat'a gider
  • kargo_gonder bayi siparişinde Sürat'ı çağırır, Basit Kargo'yu ÇAĞIRMAZ; takip no kaydolur
  • bayi/vitrin gönderisinde shopify_ok = None (uyarı yok, bildirim yok)
  • pasif Shopify mağazasında Shopify API'sine istek ATILMAZ ve uyarı bildirimi açılmaz
  • kalıp planı eksik satırı: bayi adı + sipariş no + tasarım kodu taşır
  • kimliği olmayan bayi kalemleri tek satıra gömülmez
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Dealer, Design, LineItem, Notification, Order, Store, Tenant, User,
)
from app.routers import packaging  # noqa: E402
from app.services import basit_kargo, mold_planner, surat  # noqa: E402

GECTI = KALDI = 0
IZ = f"ksetest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yon = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                  User.role.in_(["owner", "yonetici"]),
                                  User.dealer_id.is_(None)).limit(1))
c = TestClient(app)
H = {"Authorization": "Bearer " + create_access_token(
    user_id=str(yon.id), tenant_id=str(tenant.id), email=yon.email, expires_minutes=30)}

ADRES = {"first_name": "Ayşe", "last_name": "Yılmaz", "address1": "Test Mah. 1 Sk. No:2",
         "city": "Yenimahalle", "province": "Ankara", "phone": "05320000000", "zip": "06370"}


def siparis(st, no, stage=7, raw_ek=None):
    o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-{no}",
              order_number=f"{IZ}{no}", customer_name="Ayşe", current_stage=stage,
              raw={"shipping_address": ADRES, **(raw_ek or {})})
    db.add(o); db.flush()
    return o


try:
    bayi_st = Store(tenant_id=tenant.id, slug=f"{IZ}-bayi", name=f"{IZ} bayi",
                    platform="bayii", is_active=True, config={})
    eski_ayar = Store(tenant_id=tenant.id, slug=f"{IZ}-eski", name=f"{IZ} eski",
                      platform="storefront", is_active=True,
                      config={"kargo_handler": "ECONOMIC"})
    shop_pasif = Store(tenant_id=tenant.id, slug=f"{IZ}-shop", name=f"{IZ} shop",
                       platform="shopify", is_active=False, config={})
    db.add_all([bayi_st, eski_ayar, shop_pasif]); db.flush()
    bayi = Dealer(tenant_id=tenant.id, store_id=bayi_st.id, name=f"{IZ} KE Market")
    db.add(bayi); db.flush()
    db.commit()

    print("\n── Kargo yolu ──")
    es("ayarı boş mağaza -> Sürat doğrudan", "DIRECT_SURAT", packaging.kargo_handler_kodu({}))
    es("eski ECONOMIC ayarı -> yine Sürat doğrudan", "DIRECT_SURAT",
       packaging.kargo_handler_kodu({"kargo_handler": "ECONOMIC"}))
    es("etiket adı Sürat", "Sürat Kargo (doğrudan)", packaging.magaza_kargo_adi({}))

    sahte_surat = {"ok": True, "takip_no": "SRT123456", "barkod_no": "B1",
                   "barkod_base64": None, "message": "ok"}
    print("\n── kargo_gonder: bayi siparişi ──")
    o1 = siparis(bayi_st, 1)
    o2 = siparis(eski_ayar, 2)
    db.commit()
    with mock.patch.object(surat, "is_configured", return_value=True), \
         mock.patch.object(surat, "create_shipment", return_value=sahte_surat) as m_s, \
         mock.patch.object(basit_kargo, "create_shipment") as m_b:
        for o, ad in ((o1, "bayi"), (o2, "ECONOMIC ayarlı vitrin")):
            r = c.post(f"/api/packaging/order/{o.id}/kargo-gonder", headers=H, json={})
            es(f"{ad}: gönderi oluştu", (200, "SRT123456"), (r.status_code, r.json().get("takip_no")))
            es(f"{ad}: shopify_ok None (uyarı yok)", None, r.json().get("shopify_ok"))
        es("Sürat iki kez çağrıldı", 2, m_s.call_count)
        es("Basit Kargo HİÇ çağrılmadı", 0, m_b.call_count)
    db.expire_all()
    ki = db.get(Order, o1.id).kargo_info
    es("kargo_info: sağlayıcı surat + takip no", ("surat", "SRT123456"),
       (ki["provider"], ki["takip_no"]))
    es("kargo_info: shopify_ok None, hata yok", (None, None),
       (ki.get("shopify_ok"), ki.get("shopify_err")))

    print("\n── Pasif Shopify: istek atılmaz, bildirim açılmaz ──")
    o3 = siparis(shop_pasif, 3)
    db.commit()
    once = db.scalar(select(text("count(*)")).select_from(Notification)
                     .where(Notification.store_id == shop_pasif.id)) or 0
    with mock.patch.object(surat, "is_configured", return_value=True), \
         mock.patch.object(surat, "create_shipment", return_value=sahte_surat), \
         mock.patch.object(packaging, "get_adapter") as m_ad:
        r = c.post(f"/api/packaging/order/{o3.id}/kargo-gonder", headers=H, json={})
        es("pasif Shopify siparişi yine kargolanır", 200, r.status_code)
        es("Shopify adapter'ı HİÇ çağrılmadı", 0, m_ad.call_count)
    db.expire_all()
    sonra = db.scalar(select(text("count(*)")).select_from(Notification)
                      .where(Notification.store_id == shop_pasif.id)) or 0
    es("uyarı bildirimi açılmadı", once, sonra)

    print("\n── Kalıp planı eksik satırı ──")
    d = Design(tenant_id=tenant.id, store_id=bayi_st.id, code=f"{IZ}-D1",
               file_path="x/d.png", file_format="png", kalip_tipi=None)
    db.add(d); db.flush()
    o4 = siparis(bayi_st, 4, stage=3, raw_ek={"dealer_id": str(bayi.id)})
    o5 = siparis(bayi_st, 5, stage=3, raw_ek={"dealer_id": str(bayi.id)})
    for o in (o4, o5):   # ürün kimliği YOK, tasarım atanmış, kalıp tipi yok -> varyasyon eksik
        db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="B9f61-260902154328-PDF2",
                        variant_title="iPhone 15", quantity=1, device_model_override="iPhone 15",
                        assigned_design_id=d.id, properties=[], raw={}))
    db.commit()
    p = mold_planner.plan_molds(db, tenant_id=tenant.id, store_id=bayi_st.id)
    ek = [e for e in p["eksikler"] if e["reason"] == "varyasyon_eksik"]
    es("kimliksiz iki bayi kalemi tek satıra GÖMÜLMEDİ", 2, len(ek))
    e0 = next((e for e in ek if e["order_number"] == f"{IZ}4"), None)
    es("bayi adı satırda", f"{IZ} KE Market", (e0 or {}).get("bayi_adi"))
    es("tasarım kodu satırda", f"{IZ}-D1", (e0 or {}).get("tasarim_kodu"))
    es("sipariş etiketi bayiyi içeriyor", [f"#{IZ}4 · {IZ} KE Market"], (e0 or {}).get("siparisler"))
    es("sipariş bağlantısı için order_id", str(o4.id), (e0 or {}).get("order_id"))
finally:
    db.rollback()
    ids = [x for (x,) in db.execute(select(Store.id).where(Store.slug.like(f"{IZ}-%"))).all()]
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.external_id.like(f"{IZ}-%"))).all()]
    if oids:
        for q in ("delete from stock_movements where order_id = any(:o)",
                  "delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)",
                  "delete from orders where id = any(:o)"):
            try:
                db.execute(text(q).bindparams(o=oids))
            except Exception:  # noqa: BLE001
                db.rollback()
    if ids:
        for tbl in ("notifications", "designs", "dealers"):
            try:
                db.execute(text(f"delete from {tbl} where store_id = any(:s)").bindparams(s=ids))
            except Exception:  # noqa: BLE001
                db.rollback()
        db.execute(text("delete from stores where id = any(:s)").bindparams(s=ids))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
