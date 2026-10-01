"""Meta Conversions API — Meta'ya GİDECEK gövde (gönderilmeden yakalanır).

Reklam verimliliği için: olay adı, değer/para, event_id (tarayıcıyla aynı →
tekilleştirme), eşleşme sinyalleri (IP, UA, fbp, fbc, external_id, e-posta)
eksiksiz ve doğru olmalı. Test kodu unutulursa olaylar reklama gitmez → süreli.
"""
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Store  # noqa: E402
from app.services import meta_capi  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


giden: list[dict] = []
meta_capi._gonder_async = lambda pixel_id, token, body, etiket: giden.append(body)  # Meta'ya gitmez

db = SessionLocal()
IZ = f"capi{uuid.uuid4().hex[:6]}"
simdi = datetime.now(timezone.utc)
try:
    tenant_store = db.scalar(select(Store).limit(1))
    st = Store(tenant_id=tenant_store.tenant_id, name="CAPI test", slug=f"{IZ}-v", platform="storefront",
               config={"meta_pixel_id": "123456789", "meta_capi_token": "EAAtest",
                       "shop_domain": f"{IZ}.example.com"})
    db.add(st); db.commit()
    c = TestClient(app)
    H = {"X-Forwarded-For": "88.1.2.3", "User-Agent": "TestUA/1.0"}

    print("\n── Beacon olayları ──")
    for olay in ("PageView", "ViewContent", "AddToCart", "InitiateCheckout", "AddPaymentInfo"):
        giden.clear()
        r = c.post(f"/api/shop/{st.slug}/piksel", headers=H, json={
            "olay": olay, "event_id": f"{olay}_abc123", "url": "https://x/urun/a",
            "deger": None if olay == "PageView" else 199.9, "para": "TRY",
            "icerik": [] if olay == "PageView" else ["urun-a"], "adet": None if olay == "PageView" else 2,
            "fbp": "fb.1.1700000000000.123", "fbc": "fb.1.1700000000000.ABCfbclid", "vid": "abc123vid"})
        e = giden[0]["data"][0] if giden else {}
        es(f"{olay}: gönderildi + eventID", (200, olay, f"{olay}_abc123"),
           (r.status_code, e.get("event_name"), e.get("event_id")))
        u = e.get("user_data", {})
        es(f"{olay}: eşleşme sinyalleri", ("88.1.2.3", "TestUA/1.0", "fb.1.1700000000000.123",
                                          "fb.1.1700000000000.ABCfbclid", [meta_capi._h("abc123vid")]),
           (u.get("client_ip_address"), u.get("client_user_agent"), u.get("fbp"), u.get("fbc"), u.get("external_id")))
        if olay != "PageView":
            cd = e.get("custom_data", {})
            es(f"{olay}: değer/para/içerik", (199.9, "TRY", ["urun-a"]), (cd.get("value"), cd.get("currency"), cd.get("content_ids")))
        es(f"{olay}: test kodu yok (canlı)", None, giden[0].get("test_event_code") if giden else "?")
    giden.clear()
    r = c.post(f"/api/shop/{st.slug}/piksel", headers=H, json={"olay": "Purchase", "event_id": "purchase_x123"})
    es("Purchase beacon'dan KABUL EDİLMEZ (yalnız sunucu, ödeme doğrulanınca)", (False, 0), (r.json()["ok"], len(giden)))

    print("\n── Test kodu süreli ──")
    cfg = {"meta_test_event_code": "TEST1"}
    es("zamanı bilinmeyen eski kod → yok sayılır", None, meta_capi.gecerli_test_kodu(cfg))
    es("yeni girilen kod → geçerli", "TEST1", meta_capi.gecerli_test_kodu(
        {**cfg, "meta_test_event_code_at": (simdi - timedelta(minutes=30)).isoformat()}))
    es("3 saati geçen kod → yok sayılır", None, meta_capi.gecerli_test_kodu(
        {**cfg, "meta_test_event_code_at": (simdi - timedelta(hours=4)).isoformat()}))

    print("\n── Purchase (ödeme doğrulanınca) ──")
    sess = SimpleNamespace(
        token="tok123", currency="TRY", amount=Decimal("598.80"), paid_at=simdi,
        customer={"email": " Ali@Ornek.com ", "phone": "05321234567", "first_name": "Ali", "last_name": "Yılmaz",
                  "_meta": {"ip": "88.1.2.3", "ua": "TestUA/1.0", "fbp": "fb.1.1.2", "fbc": "fb.1.1.3", "vid": "abc123vid"}},
        cart_snapshot=[{"product_slug": "urun-a", "quantity": 2, "unit_price": "299.40"}])
    p = meta_capi.build_purchase_payload(st, sess)
    e = p["body"]["data"][0]
    es("event_id tarayıcıyla aynı", "purchase_tok123", e["event_id"])
    es("değer + para + içerik", (598.8, "TRY", ["urun-a"], [{"id": "urun-a", "quantity": 2, "item_price": 299.4}]),
       (e["custom_data"]["value"], e["custom_data"]["currency"], e["custom_data"]["content_ids"], e["custom_data"]["contents"]))
    u = e["user_data"]
    es("e-posta normalize + hash", meta_capi._h("ali@ornek.com"), u["em"])
    es("telefon 90XXXXXXXXXX biçiminde hash", meta_capi._h("905321234567"), u["ph"])
    es("external_id: ziyaretçi + e-posta", [meta_capi._h("abc123vid"), meta_capi._h("ali@ornek.com")], u["external_id"])
    es("fbp/fbc/ip/ua", ("fb.1.1.2", "fb.1.1.3", "88.1.2.3", "TestUA/1.0"),
       (u["fbp"], u["fbc"], u["client_ip_address"], u["client_user_agent"]))
    es("olay zamanı = ödeme zamanı", int(simdi.timestamp()), e["event_time"])
    es("telefon biçimleri", ["905321234567"] * 5,
       [meta_capi.tr_telefon(x) for x in ("05321234567", "5321234567", "+90 532 123 45 67", "905321234567", "0090 532 123 4567")])
finally:
    db.rollback()
    db.execute(text("delete from stores where slug like :s"), {"s": f"{IZ}-%"})
    db.commit()
    db.close()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
