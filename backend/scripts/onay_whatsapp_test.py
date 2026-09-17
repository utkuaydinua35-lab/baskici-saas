"""Kişiye özel tasarım onayı (numune) — WhatsApp'ı hazır mesajla açan bağlantı.

Sınananlar:
  • Kişiye Özel paneli ve sipariş detayı onay uçları wa.me adresi döner
  • adres mesajın KENDİSİNİ ve onay linkini taşır
  • sabit hat önce gelse de CEP numarası seçilir; cep yoksa wa_url yok
  • onay listesi (sipariş detayı) her versiyon için wa_url döner
  • bayi/telafi siparişindeki customer_phone da bulunur
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Design, KisiyeOzelProduct, LineItem, Order, Store, Tenant, User  # noqa: E402
from app.services import approvals as ap_svc, mockup, model_degisim as md  # noqa: E402

mockup.generate_mockup_url = lambda *a, **k: None   # mockup üretimi bu testin konusu değil
GECTI = KALDI = 0
IZ = f"owtest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yon = db.scalar(select(User).where(User.tenant_id == tenant.id, User.role.in_(["owner", "yonetici"])).limit(1))
H = {"Authorization": "Bearer " + create_access_token(user_id=str(yon.id), tenant_id=str(tenant.id),
                                                       email=yon.email, expires_minutes=30)}
c = TestClient(app)
st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="OW", platform="storefront", is_active=True)
db.add(st); db.flush()
db.add(KisiyeOzelProduct(tenant_id=tenant.id, store_id=st.id, product_id="KO-1", product_title="Kişiye Özel"))
d = Design(tenant_id=tenant.id, store_id=st.id, code=f"{IZ}d", file_path="x/y.png", file_format="png")
db.add(d); db.flush()


def siparis(raw):
    o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-{uuid.uuid4().hex[:5]}",
              order_number=f"{IZ}{uuid.uuid4().hex[:3]}", customer_name="Ayşe Yılmaz", current_stage=2, raw=raw)
    db.add(o); db.flush()
    db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="Kişiye Özel Kılıf", quantity=1, product_id="KO-1",
                    device_model_override="iPhone 15", assigned_design_id=d.id, properties=[]))
    return o


try:
    o1 = siparis({"customer": {"phone": "0212 555 44 33"}, "shipping_address": {"phone": "0532 160 24 42"}})
    o2 = siparis({"shipping_address": {"phone": "0212 555 44 33"}})
    o3 = siparis({"customer_phone": "05551112233"})
    db.commit()

    print("\n── Kişiye Özel paneli ──")
    r = c.post(f"/api/kisiye-ozel/orders/{o1.id}/approval", headers=H, json={})
    es("200", 200, r.status_code)
    j = r.json()
    es("wa.me + CEP numarası (sabit hat atlandı)", True, (j.get("wa_url") or "").startswith("https://wa.me/905321602442?text="))
    metin = unquote((j.get("wa_url") or "").split("?text=", 1)[-1])
    es("adres mesajın kendisini taşır", j.get("message"), metin)
    es("onay linki mesajda", True, j["link"] in metin)

    print("\n── Sipariş detayı ──")
    r = c.post(f"/api/orders/{o1.id}/approval", headers=H, json={})
    es("200 + wa_url", (200, True), (r.status_code, bool(r.json().get("wa_url"))))
    liste = c.get(f"/api/orders/{o1.id}/approvals", headers=H).json()["items"]
    es("listede her versiyonda wa_url", [True, True], [bool(x.get("wa_url")) for x in liste])
    es("revizyon (v2) mesajı adreste", True, "tekrar hazırladık" in unquote(liste[0]["wa_url"]))

    print("\n── Müşterinin gördüğü numune (önizleme) ──")
    es("oluşturma yanıtında önizleme adresi", f"{j['link']}?onizleme=1", j.get("preview_url"))
    es("listede önizleme adresi", True, all(x.get("preview_url", "").endswith("?onizleme=1") for x in liste))
    ko = c.get(f"/api/kisiye-ozel/orders?store_id={st.id}", headers=H)
    if ko.status_code == 200:
        kayit = next((x for x in (ko.json().get("items") or ko.json().get("orders") or []) if x.get("id") == str(o1.id)), None)
        es("Kişiye Özel listesinde en güncel versiyonun önizlemesi", (True, 2),
           (bool(kayit and (kayit.get("approval_preview_url") or "").endswith("?onizleme=1")), kayit and kayit.get("approval_version")))
    sayfa = c.get(f"/onay/{liste[0]['link'].rsplit('/', 1)[1]}?onizleme=1")
    es("sayfa açılır + önizleme modu kodda", (200, True), (sayfa.status_code, "ONIZLEME" in sayfa.text))
    es("önizleme sayfayı AÇMAK kararı değiştirmez", "bekliyor",
       c.get(f"/approval/{liste[0]['link'].rsplit('/', 1)[1]}").json().get("status"))

    print("\n── Telefon durumları ──")
    es("yalnız sabit hat → wa_url yok", None, c.post(f"/api/kisiye-ozel/orders/{o2.id}/approval", headers=H, json={}).json().get("wa_url"))
    es("customer_phone bulunur", True, (c.post(f"/api/kisiye-ozel/orders/{o3.id}/approval", headers=H, json={}).json().get("wa_url") or "").startswith("https://wa.me/905551112233"))
    es("model değişim linki de cep numarasını seçer", "905321602442", md.siparis_telefonu(db.get(Order, o1.id)))
    es("resolve_phone eski davranış (ilk aday)", "0212 555 44 33", ap_svc.resolve_phone(db.get(Order, o1.id)))
finally:
    db.rollback()
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.store_id == st.id)).all()]
    if oids:
        for q in ("delete from design_approvals where order_id = any(:o)",
                  "delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)", "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    for q in ("delete from designs where store_id = :s", "delete from kisiye_ozel_products where store_id = :s",
              "delete from stores where id = :s"):
        db.execute(text(q).bindparams(s=st.id))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
