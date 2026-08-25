"""Toplu kalıp silme — basılmış/basılmamış ayrımı doğru mu.

molds._delete_mold_inner iki farklı davranış uygular:
  • basılmamış kalıp → kalemler plana GERİ DÖNER (is_kaliba_eklendi=False)
  • basılmış kalıp   → kalemler ÜRETİLMİŞ sayılır, plana DÖNMEZ
Toplu silme bu ayrımı korumalı; yoksa basılmış ürünler ikinci kez basılır.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Design, LineItem, Mold, MoldItem, Order, Store,  # noqa: E402
                        Tenant, User)

C = TestClient(app)
GECTI = KALDI = 0
IZ = f"tksil{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")



def _yonetici_girisi(C, db, email: str, sifre: str) -> dict:
    """Yönetici token'ı. Hız sınırına takılırsa temizleyip bir kez daha dener.

    Giriş, IP başına 5 dakikada 10 başarısız denemeyle sınırlı. Test paketleri
    arka arkaya koşunca bu sayaç doluyor ve giriş 401 dönüyordu; testler de
    sessizce ATLANIYORDU (7 güvenlik sınaması hiç çalışmadan "geçti" görünüyordu).
    Sessizce atlayan test, olmayan testten kötüdür — burada ya giriliyor ya da
    yüksek sesle patlıyor.
    """
    from sqlalchemy import text as _t

    r = C.post("/api/auth/login", json={"email": email, "password": sifre})
    if r.status_code != 200:
        # Testin kendi gürültüsünü temizle (yalnız testclient IP'si)
        db.execute(_t("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
        db.commit()
        r = C.post("/api/auth/login", json={"email": email, "password": sifre})
    if r.status_code != 200:
        raise SystemExit(
            f"YONETICI GIRISI BASARISIZ ({r.status_code}): {str(r.text)[:200]}\n"
            f"Bu testler yonetici olmadan CALISAMAZ — atlanmiyor, durduruluyor.")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
admin = db.scalar(select(User).where(User.role.in_(("yonetici", "owner"))).limit(1))
H = _yonetici_girisi(C, db, admin.email, "DevAdmin12345!")

store = Store(tenant_id=tenant.id, slug=f"{IZ}-s", name="Toplu Sil",
              platform="bayii", is_active=True)
db.add(store); db.flush()
ds = Design(tenant_id=tenant.id, store_id=store.id, code=f"{IZ}-D", name="d",
            file_path="", file_format="", file_size_bytes=0)
db.add(ds); db.flush()


def kalip_kur(asama: int, print_status: str):
    """Bir siparis + kalem + o kalemi iceren kalip. (mold_id, line_item_id)."""
    o = Order(tenant_id=tenant.id, store_id=store.id,
              external_id=f"{IZ}-{uuid.uuid4().hex[:6]}",
              order_number=f"{IZ}{uuid.uuid4().hex[:4]}", customer_name="T",
              current_stage=2)
    db.add(o); db.flush()
    li = LineItem(tenant_id=tenant.id, order_id=o.id, title="k", quantity=1,
                  assigned_design_id=ds.id, device_model_override="IPHONE-15",
                  is_kaliba_eklendi=True, properties=[], raw={})
    db.add(li); db.flush()
    m = Mold(tenant_id=tenant.id, store_id=store.id, kod=f"{IZ}-{asama}",
             variation="SİYAH", kilif_sayisi=1, rows_used=1,
             current_stage=asama, print_status=print_status)
    db.add(m); db.flush()
    db.add(MoldItem(tenant_id=tenant.id, mold_id=m.id, store_id=store.id,
                    line_item_id=li.id, design_id=ds.id, slot_index=0,
                    kalip_kodu="A1", model="IPHONE-15",
                    order_number=str(o.order_number)))
    db.commit()
    return m.id, li.id


m_bek, li_bek = kalip_kur(2, "bekliyor")     # basılmamış
m_bas, li_bas = kalip_kur(5, "basildi")      # basılmış

print("\n── Toplu silme: basılmış/basılmamış ayrımı ──")
r = C.post("/api/molds/print/bulk-delete", headers=H,
           json={"ids": [str(m_bek), str(m_bas)]})
es("istek 200", 200, r.status_code)
es("2 kalip silindi", 2, r.json().get("deleted_count"))

db.expire_all()
es("basilmamis kalip gitti", None, db.scalar(select(Mold).where(Mold.id == m_bek)))
es("basilmis kalip gitti", None, db.scalar(select(Mold).where(Mold.id == m_bas)))
es("BASILMAMIS kalem plana DONDU", False,
   db.scalar(select(LineItem.is_kaliba_eklendi).where(LineItem.id == li_bek)))
# Çift baskı koruması: basılmış kalemin plana dönmemesi için ya bayrağı kalır
# ya da 'hazır' işaretlenir — ikisi de "tekrar basılmaz" demek.
_bas_kaliba = db.scalar(select(LineItem.is_kaliba_eklendi).where(LineItem.id == li_bas))
_bas_hazir = db.scalar(select(LineItem.is_hazir).where(LineItem.id == li_bas))
es("BASILMIS kalem plana DONMEDI", True, bool(_bas_kaliba) or bool(_bas_hazir))

print("\n── MoldItem'lar da temizlendi ──")
es("silinen kaliplarin kalemleri yok", 0, db.scalar(text(
    "select count(*) from mold_items where mold_id = any(:m)"
).bindparams(m=[m_bek, m_bas])))

print("\n── Yetki + geçersiz girdi ──")
es("kimliksiz istek reddedilir", 401,
   C.post("/api/molds/print/bulk-delete", json={"ids": []}).status_code)
es("ids ve only_printed yoksa 400", 400,
   C.post("/api/molds/print/bulk-delete", headers=H, json={}).status_code)
es("olmayan id sessiz gecer", 200,
   C.post("/api/molds/print/bulk-delete", headers=H,
          json={"ids": [str(uuid.uuid4())]}).status_code)

# Temizlik
db.execute(text("delete from mold_items where tenant_id=:t and model='IPHONE-15' "
                "and order_number like :p"), {"t": tenant.id, "p": f"{IZ}%"})
db.execute(text("delete from molds where kod like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from line_items where order_id in "
                "(select id from orders where external_id like :p)"), {"p": f"{IZ}%"})
db.execute(text("delete from orders where external_id like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from designs where code like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from stores where slug like :p"), {"p": f"{IZ}%"})
db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
