"""Yeni vitrin mağazası kurulumu — yalnız görünen ad, slug ve alan adı.

Sınananlar:
  • form tanımı (_meta/platforms) vitrinde YALNIZ alan adını sorar
  • ad + slug + alan adıyla kurulum yeter; sorulmayan ayarlar güvenli
    varsayılanla gelir (iyzico SANDBOX, kargo sözü 3 gün) ve ödeme adaptörü
    kurulur ("Bilinmeyen ödeme sağlayıcı" patlaması yok)
  • alan adı temizlenir (https://, büyük harf, yol, port) — vitrin Host'u
    birebir karşılaştırıyor, temizlenmezse mağaza hiç bulunmaz
  • boş / geçersiz alan adı reddedilir; başka mağazanın alan adı 409
  • sonradan düzeltme: Studio (PATCH /api/stores) ve mağaza paneli ayarları
    aynı kurallarla; kendi alan adını yeniden kaydetmek çakışma sayılmaz
  • Shopify kurulumu etkilenmez
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
from app.models import Store, Tenant, User  # noqa: E402
from app.payments import get_payment_provider  # noqa: E402
from app.services import alan_adi  # noqa: E402

GECTI = KALDI = 0
IZ = f"vktest{uuid.uuid4().hex[:6]}"


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
A1, A2 = f"{IZ}-a.example.com", f"{IZ}-b.example.com"


def kur(slug, **config):
    return c.post("/api/stores", headers=H, json={"name": f"Test {slug}", "slug": f"{IZ}-{slug}",
                                                   "platform": "storefront", "config": config})


try:
    print("\n── Form tanımı ──")
    meta = {p["id"]: p for p in c.get("/api/stores/_meta/platforms", headers=H).json()}
    es("vitrin yalnız alan adını sorar", ["shop_domain"], [f["key"] for f in meta["storefront"]["fields"]])
    es("alan adı zorunlu", True, meta["storefront"]["fields"][0]["required"])
    es("ayarların nerede olduğu notu var", True, "Ayarlar" in (meta["storefront"].get("not") or ""))
    es("shopify formu değişmedi", True, len(meta["shopify"]["fields"]) >= 2)

    print("\n── Kurulum ──")
    r = kur("a", shop_domain=f"  HTTPS://{A1.upper()}:443/urunler?x=1  ")
    es("ad + slug + alan adı yeter → 201", 201, r.status_code)
    cfg = r.json().get("config", {})
    es("alan adı temizlendi", A1, cfg.get("shop_domain"))
    es("ödeme sağlayıcı varsayılanı iyzico", "iyzico", cfg.get("payment_provider"))
    es("ödeme ortamı SANDBOX", True, "sandbox" in (cfg.get("iyzico_base_url") or ""))
    es("kargo sözü 3 gün", "3", cfg.get("sla_days"))
    st_a = db.get(Store, uuid.UUID(r.json()["id"]))
    es("ödeme adaptörü kurulabiliyor", "IyzicoProvider", type(get_payment_provider(st_a)).__name__)
    es("vitrin Host çözümlemesi bulur", f"{IZ}-a",
       c.get(f"/api/shop/_resolve?host={A1}").json().get("slug"))

    es("alan adı yok → 422", 422, kur("b").status_code)
    es("geçersiz alan adı → 422", 422, kur("b", shop_domain="magaza bizim").status_code)
    es("uzantısız alan adı → 422", 422, kur("b", shop_domain="localhost").status_code)
    r = kur("b", shop_domain=A1.upper())
    es("başka mağazanın alan adı → 409", 409, r.status_code)
    es("409 mesajı okunur", True, "başka bir mağazaya bağlı" in (r.json().get("detail") or ""))
    r = kur("b", shop_domain=A2)
    es("farklı alan adıyla ikinci mağaza → 201", 201, r.status_code)
    st_b_id = r.json()["id"]

    print("\n── Sonradan düzeltme (Studio) ──")
    r = c.patch(f"/api/stores/{st_a.id}", headers=H, json={"config": {"shop_domain": f"https://{A1}/"}})
    es("kendi alan adını yeniden kaydetmek çakışma değil", (200, A1), (r.status_code, r.json().get("config", {}).get("shop_domain")))
    es("diğer mağazanın alan adına geçilemez → 409", 409,
       c.patch(f"/api/stores/{st_a.id}", headers=H, json={"config": {"shop_domain": A2}}).status_code)
    es("boşaltılamaz → 422", 422,
       c.patch(f"/api/stores/{st_a.id}", headers=H, json={"config": {"shop_domain": ""}}).status_code)
    yeni = f"{IZ}-c.example.com"
    es("düzeltme kaydolur", yeni,
       c.patch(f"/api/stores/{st_a.id}", headers=H, json={"config": {"shop_domain": yeni.upper()}}).json()["config"]["shop_domain"])

    print("\n── Mağaza paneli ayarları ──")
    r = c.patch(f"/api/store-settings/{st_b_id}", headers=H, json={"config": {"custom_domain": yeni}})
    es("kendi alan adı başkasında → 409", 409, r.status_code)
    r = c.patch(f"/api/store-settings/{st_b_id}", headers=H, json={"config": {"custom_domain": "WWW.Ornek-" + IZ + ".com/"}})
    es("kendi alan adı temizlenir", (200, f"www.ornek-{IZ}.com"),
       (r.status_code, db.execute(text("select config->>'custom_domain' from stores where id=:i"),
                                  {"i": st_b_id}).scalar()))
    r = c.patch(f"/api/store-settings/{st_b_id}", headers=H, json={"config": {"custom_domain": None}})
    es("kendi alan adı kaldırılabilir", 200, r.status_code)

    print("\n── Yardımcı ──")
    es("normalize", "a.b.com", alan_adi.normalize(" http://A.B.com./x "))
    es("tireli etiket geçerli", True, alan_adi.gecerli_mi("benim-magazam.com.tr"))
    es("tireyle başlayan geçersiz", False, alan_adi.gecerli_mi("-x.com"))

    print("\n── Shopify etkilenmez ──")
    r = c.post("/api/stores", headers=H, json={"name": "S", "slug": f"{IZ}-s", "platform": "shopify",
                                                "config": {"store_url": "x.myshopify.com", "access_token": "t"}})
    es("shopify kurulumu → 201", 201, r.status_code)
    es("shopify'a vitrin varsayılanı eklenmez", None, r.json().get("config", {}).get("payment_provider"))
finally:
    db.rollback()
    db.execute(text("delete from stores where slug like :s"), {"s": f"{IZ}-%"})
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
