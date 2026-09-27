"""Telafi kargo barkodu — sipariş detayından oluştur / yazdır / iptal et.

Sınananlar:
  • /api/telafiler/{id}/kargo-barkod gönderi oluşturur, takip no döner,
    telafiyi "Kargoda" (aşama 8) yapar ve kargo bilgisini saklar
  • paketlemedeki akışın AYNISI çağrılır (kopya kod yok): durum geçmişine
    "kargoya_verildi" düşer
  • ikinci kez basılırsa 409 — aynı telafi iki gönderi açmaz
  • iptal barkodu siler, aşamayı geri alır (yanlış telafide oluşturulan
    barkod aynı ekrandan geri alınabilir)
  • telafi listesi/sipariş detayı kargo durumunu döner (düğme metni buna bağlı)
  • başka kiracının telafisine erişilemez
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (LineItem, Order, OrderStatusHistory, Store, Tenant, User)  # noqa: E402
from app.services import basit_kargo  # noqa: E402

GECTI = KALDI = 0
IZ = f"tktest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


# Kargo firmasına GERÇEK istek atılmaz — sahte gönderi
_cagri = {"sayi": 0}


def _sahte_shipment(order_raw, **kw):
    _cagri["sayi"] += 1
    return {"ok": True, "id": f"{IZ}-bk", "barcode": "1234567890",
            "takip_no": f"{IZ}-TAKIP", "handler_code": kw.get("handler_code") or "ECONOMIC",
            "handler_name": "Ekonomik", "status": "created",
            "label_svg": '<svg width="100mm" height="150mm"></svg>', "etiket_var": True}


basit_kargo.create_shipment = _sahte_shipment
basit_kargo.delete_barcode = lambda *a, **k: {"ok": True}
# Etiket okuma da sahte: gerçek kargo firmasına istek atılmaz
basit_kargo.get_label_svg = lambda *a, **k: (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="150mm">'
    '<rect width="100" height="150" fill="white"/></svg>')

db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yon = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                  User.role.in_(["owner", "yonetici"])).limit(1))
H = {"Authorization": "Bearer " + create_access_token(user_id=str(yon.id), tenant_id=str(tenant.id),
                                                      email=yon.email, expires_minutes=30)}
c = TestClient(app)
st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="TK", platform="storefront", is_active=True,
           config={"kargo_handler": "ECONOMIC"})
db.add(st); db.flush()

ADRES = {"shipping_address": {"name": "Ayşe Yılmaz", "address1": "Test sok 1",
                             "city": "Kadıköy", "province": "İstanbul", "phone": "05321602442"}}


def siparis(no, *, telafi=False, kaynak=None):
    o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-{no}",
              order_number=f"{IZ}{no}", customer_name="Ayşe Yılmaz", current_stage=5,
              created_at_platform=datetime.now(UTC), raw=dict(ADRES),
              is_telafi=telafi, telafi_sebep=("yanlış model" if telafi else None),
              telafi_kaynak_order_id=(kaynak.id if kaynak is not None else None))
    db.add(o); db.flush()
    db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="Kılıf", quantity=1,
                    product_id=f"{IZ}-p", properties=[], device_model_override="iPhone 15"))
    db.flush()
    return o


try:
    ana = siparis(1)
    tel = siparis(2, telafi=True, kaynak=ana)
    db.commit()

    print("\n── Sipariş detayı telafi kargo durumunu döner ──")
    d = c.get(f"/api/orders/{ana.id}/detail", headers=H).json()
    satir = next((t for t in d["telafiler"] if t["id"] == str(tel.id)), None)
    es("telafi listede", True, satir is not None)
    es("barkod yok", False, satir["kargo"]["var"])

    print("\n── Barkod oluştur ──")
    r = c.post(f"/api/telafiler/{tel.id}/kargo-barkod", headers=H, json={})
    es("200 döner", 200, r.status_code)
    es("takip no döner", f"{IZ}-TAKIP", r.json().get("takip_no"))
    es("etiket (SVG) döner", True, bool(r.json().get("label_svg")))
    db.expire_all()
    tel = db.get(Order, tel.id)
    es("aşama 8 (Kargoda)", 8, tel.current_stage)
    es("kargo bilgisi saklandı", f"{IZ}-TAKIP", (tel.kargo_info or {}).get("takip_no"))
    es("mağazanın kargo firması kullanıldı", "ECONOMIC", (tel.kargo_info or {}).get("handler_code"))
    gecmis = db.scalars(select(OrderStatusHistory).where(
        OrderStatusHistory.order_id == tel.id)).all()
    es("durum geçmişine düştü", True, any(h.action == "kargoya_verildi" for h in gecmis))
    es("kargo firmasına TEK istek", 1, _cagri["sayi"])

    print("\n── İkinci kez oluşturulamaz ──")
    r2 = c.post(f"/api/telafiler/{tel.id}/kargo-barkod", headers=H, json={})
    es("409 döner", 409, r2.status_code)
    es("ikinci gönderi AÇILMADI", 1, _cagri["sayi"])

    print("\n── Listede görünür ──")
    d = c.get(f"/api/orders/{ana.id}/detail", headers=H).json()
    satir = next(t for t in d["telafiler"] if t["id"] == str(tel.id))
    es("barkod var", True, satir["kargo"]["var"])
    es("takip no listede", f"{IZ}-TAKIP", satir["kargo"]["takip_no"])
    es("kargoda işareti", True, satir["kargo"]["kargoda"])
    tl = c.get(f"/api/telafiler/{tel.id}", headers=H).json()
    es("telafi detayı da döner", f"{IZ}-TAKIP", tl["kargo"]["takip_no"])

    print("\n── İptal (geri alma) ──")
    r = c.post(f"/api/telafiler/{tel.id}/kargo-iptal", headers=H, json={})
    es("iptal 200", 200, r.status_code)
    db.expire_all()
    tel = db.get(Order, tel.id)
    es("takip no silindi", None, (tel.kargo_info or {}).get("takip_no"))
    es("aşama geri alındı", True, (tel.current_stage or 0) < 8)
    r = c.post(f"/api/telafiler/{tel.id}/kargo-barkod", headers=H, json={})
    es("iptal sonrası yeniden oluşturulabilir", 200, r.status_code)
    es("yeni gönderi açıldı", 2, _cagri["sayi"])

    print("\n── Etiket uçları (paketleme yetkisi olmadan) ──")
    es("kargo etiketi telafi ucundan alınır", 200,
       c.get(f"/api/telafiler/{tel.id}/kargo-label", headers=H).status_code)
    zr = c.get(f"/api/telafiler/{tel.id}/zpl?tip=kargo&w_mm=100&h_mm=150", headers=H)
    es("ZPL ucu yanıt verir (yazıcıya doğrudan)", True, zr.status_code in (200, 400, 502))

    print("\n── Yetki ──")
    baska = db.scalar(select(Tenant).where(Tenant.id != tenant.id).limit(1))
    if baska is not None:
        bu = db.scalar(select(User).where(User.tenant_id == baska.id).limit(1))
        if bu is not None:
            H2 = {"Authorization": "Bearer " + create_access_token(
                user_id=str(bu.id), tenant_id=str(baska.id), email=bu.email, expires_minutes=30)}
            es("başka kiracı erişemez", True,
               c.post(f"/api/telafiler/{tel.id}/kargo-barkod", headers=H2, json={}).status_code in (403, 404))
        else:
            print("  · başka kiracıda kullanıcı yok, atlandı")
    else:
        print("  · tek kiracı, yetki sınaması atlandı")
finally:
    db.rollback()
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.store_id == st.id)).all()]
    if oids:
        for q in ("delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)",
                  "update orders set telafi_kaynak_order_id = null where id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    db.execute(text("delete from stores where id = :s").bindparams(s=st.id))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
