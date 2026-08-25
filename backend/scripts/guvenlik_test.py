"""Güvenlik regresyon testleri — kapatılan açıklar geri gelmesin.

1) support/order-status: e-posta TEK BAŞINA sipariş verisi ya da lookup_token
   vermemeli; yanlış sipariş numarası hiçbir şey açmamalı.
2) Shopify OAuth `state`: client_secret taşımamalı, tek kullanımlık olmalı.
"""
from __future__ import annotations

import base64
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (CheckoutSession, Order, ShopifyOAuthPending,  # noqa: E402
                        Store, Tenant, User)

C = TestClient(app)
GECTI = KALDI = 0
IZ = f"guvtest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
admin = db.scalar(select(User).where(User.role.in_(("yonetici", "owner"))).limit(1))

# ─── Kurulum: vitrin mağazası + ödenmiş sipariş ──────────────
store = Store(tenant_id=tenant.id, slug=f"{IZ}-shop", name="Guvenlik Test",
              platform="storefront", is_active=True, config={})
db.add(store); db.flush()
KURBAN = f"{IZ}@ornek.com"
o = Order(tenant_id=tenant.id, store_id=store.id, external_id=f"{IZ}-1",
          order_number=f"{IZ}9", name=f"#{IZ}9", customer_name="Kurban",
          customer_email=KURBAN, current_stage=3)
db.add(o); db.flush()
sess = CheckoutSession(tenant_id=tenant.id, store_id=store.id, order_id=o.id,
                       status="paid", amount=100, currency="TRY",
                       provider="paytr", token=f"{IZ}-tok", lookup_token=f"{IZ}-lookup")
db.add(sess); db.commit()

print("\n── 1. support/order-status: e-posta tek basina veri VERMEMELI ──")
r = C.post(f"/api/shop/{store.slug}/support/order-status", json={"email": KURBAN})
es("istek 200", 200, r.status_code)
govde = r.text
es("yanitta lookup_token YOK", False, "lookup_token" in govde)
es("yanitta takip no YOK", False, "takip_no" in govde)
es("yanitta siparis listesi YOK", False, '"orders"' in govde)
es("gercek token govdede gecmiyor", False, f"{IZ}-lookup" in govde)
es("yanit 'gonderildi' diyor", True, bool(r.json().get("sent")))

# Kayitsiz e-posta AYNI yaniti vermeli (hesap sayimi yapilamasin)
r2 = C.post(f"/api/shop/{store.slug}/support/order-status",
            json={"email": f"yok-{IZ}@ornek.com"})
es("kayitsiz e-posta ayni durum kodu", r.status_code, r2.status_code)
es("kayitsiz e-posta ayni govde", r.json(), r2.json())

print("\n── 2. Yanlis siparis numarasi hicbir sey acmamali ──")
# Eskiden `matched or orders` yuzunden yanlis numara TUM siparislere dusuyordu.
from app.routers import public_shop as ps  # noqa: E402

yakalanan = []
_orj = ps._takip_postasi_gonder
ps._takip_postasi_gonder = lambda sid, tid, em, bag: yakalanan.append((em, list(bag)))
try:
    C.post(f"/api/shop/{store.slug}/support/order-status",
           json={"email": KURBAN, "order_no": "999999"})
    es("yanlis numara -> hic baglanti yok", [], yakalanan[-1][1] if yakalanan else None)
    C.post(f"/api/shop/{store.slug}/support/order-status",
           json={"email": KURBAN, "order_no": f"{IZ}9"})
    es("dogru numara -> 1 baglanti", 1, len(yakalanan[-1][1]))
    C.post(f"/api/shop/{store.slug}/support/order-status", json={"email": KURBAN})
    es("numarasiz -> baglanti var", 1, len(yakalanan[-1][1]))
    es("baglanti KAYITLI adrese gidiyor", KURBAN, yakalanan[-1][0])
finally:
    ps._takip_postasi_gonder = _orj

print("\n── 3. lookup_token hala calisiyor (islevsellik bozulmadi) ──")
es("token ile siparis goruluyor", 200,
   C.get(f"/api/shop/orders/{IZ}-lookup").status_code)
es("gecersiz token 404", 404, C.get(f"/api/shop/orders/{IZ}-yok").status_code)

print("\n── 4. OAuth state: client_secret TASIMAMALI ──")
tok = C.post("/api/auth/login",
             json={"email": admin.email, "password": "DevAdmin12345!"})
if tok.status_code != 200:
    print("  ⚠ yonetici girisi yapilamadi — OAuth testleri atlandi")
else:
    H = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    SIR = "shpss_COKGIZLI_ANAHTAR_123"
    r = C.post("/api/stores/oauth/start", headers=H, json={
        "store_url": f"{IZ}.myshopify.com", "client_id": "cid123",
        "client_secret": SIR, "name": "Guv Test", "slug": f"{IZ}-oauth"})
    es("oauth/start 200", 200, r.status_code)
    url = r.json()["install_url"]
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(url).query)["state"][0]

    # JWT payload'i base64 — sirri okumaya calis
    govde_b64 = state.split(".")[1]
    govde_b64 += "=" * (-len(govde_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(govde_b64))
    es("state'te client_secret YOK", False, "client_secret" in payload)
    es("sir hicbir alanda gecmiyor", False, SIR in json.dumps(payload))
    es("state yalnizca bilet tasiyor", {"pending", "shop", "exp"}, set(payload))

    # Sir sunucuda duruyor
    kayit = db.scalar(select(ShopifyOAuthPending).where(
        ShopifyOAuthPending.id == uuid.UUID(payload["pending"])))
    es("sir sunucudaki kayitta", SIR, kayit.client_secret if kayit else None)

    print("\n── 5. state TEK KULLANIMLIK ──")
    # Callback'i cagir; token takasi disariya cikacagi icin hata donecek ama
    # kayit TUKETILMIS olmali.
    C.get("/api/stores/oauth/callback",
          params={"code": "x", "shop": f"{IZ}.myshopify.com", "state": state},
          follow_redirects=False)
    db.expire_all()
    es("kayit tuketildi", None, db.scalar(select(ShopifyOAuthPending).where(
        ShopifyOAuthPending.id == uuid.UUID(payload["pending"]))))
    r2 = C.get("/api/stores/oauth/callback",
               params={"code": "x", "shop": f"{IZ}.myshopify.com", "state": state},
               follow_redirects=False)
    es("ayni state ikinci kez REDDEDILIR", True,
       "state_used_or_expired" in (r2.headers.get("location") or ""))

print("\n── 6. Webhook sirlari: sabit zamanli + coken girdi yok ──")
from app.config import get_settings  # noqa: E402

_s = get_settings()
_kargo_sir = (_s.basit_kargo_webhook_secret or "").strip()
# ASCII disi yol: compare_digest str ile TypeError atardi -> 500. 404 bekleriz.
r = C.post("/api/webhooks/basit-kargo/türkçe-sır-çğüöş", json={})
es("ASCII disi sir 500 DEGIL", True, r.status_code != 500)
es("ASCII disi sir 404", 404, r.status_code)
es("yanlis sir 404", 404,
   C.post("/api/webhooks/basit-kargo/kesinlikle-yanlis", json={}).status_code)
if _kargo_sir:
    es("dogru sir kabul edilir", True,
       C.post(f"/api/webhooks/basit-kargo/{_kargo_sir}", json={}).status_code != 404)

# Instagram dogrulama ucu
r = C.get("/api/public/instagram/webhook",
          params={"hub.mode": "subscribe", "hub.verify_token": "yanlış-çğü",
                  "hub.challenge": "123"})
es("instagram yanlis token 500 DEGIL", True, r.status_code != 500)
es("instagram yanlis token reddedilir", True, r.status_code in (403, 404))

# ─── Temizlik ────────────────────────────────────────────────
db.execute(text("delete from shopify_oauth_pending where slug like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from checkout_sessions where token like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from orders where external_id like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from stores where slug like :p"), {"p": f"{IZ}%"})
db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
