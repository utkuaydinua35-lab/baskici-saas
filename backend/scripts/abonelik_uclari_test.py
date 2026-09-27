#!/usr/bin/env python3
"""Kiralama uçları — yetki ve para güvenliği (routers/platform.py, routers/abonelik.py).

Kiracı plan listesini göremez, kendine ödeme giremez, ödemeyi geri alamaz;
önizlemedeki tutar değiştiyse ödeme reddedilir (409); geri alma bitişi eski
tarihine döndürür. Geçici yönetici + kiracı kurar, sonunda hepsini SİLER;
değiştirdiği plan fiyatını ve havale ayarını eski hâline getirir.

Koşum: cd backend && .venv/bin/python scripts/abonelik_uclari_test.py
"""
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.auth.security import create_access_token, hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AbonelikOdemesi, Plan, PlatformAyari, Tenant, User  # noqa: E402

GECTI = KALDI = 0


def kontrol(ad, kosul, bilgi=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}  → {bilgi}")


def baslik(u: User) -> dict:
    jeton = create_access_token(user_id=str(u.id), tenant_id=str(u.tenant_id), email=u.email)
    return {"Authorization": f"Bearer {jeton}"}


def main() -> int:
    db = SessionLocal()
    ek = uuid.uuid4().hex[:6]
    sahip_id = db.scalar(select(Plan.id).where(Plan.kod == "sahip"))
    adm_t = Tenant(name=f"Platform {ek}", slug=f"plat-{ek}", plan="sahip", plan_id=sahip_id)
    kir_t = Tenant(name=f"Kiracı {ek}", slug=f"kir-{ek}", plan="trial",
                   active_until=date.today() - timedelta(days=2))
    db.add_all([adm_t, kir_t])
    db.flush()
    adm = User(tenant_id=adm_t.id, email=f"adm-{ek}@test.local", password_hash=hash_password("x" * 12),
               full_name="Yönetici", role="owner", is_active=True, is_platform_admin=True)
    kir = User(tenant_id=kir_t.id, email=f"kir-{ek}@test.local", password_hash=hash_password("x" * 12),
               full_name="Kiracı", role="owner", is_active=True)
    db.add_all([adm, kir])
    db.commit()
    eski_bitis = kir_t.active_until
    havale_kayit = db.get(PlatformAyari, "havale")
    havale_eski = dict(havale_kayit.deger) if havale_kayit else None
    c = TestClient(app)
    A, K = baslik(adm), baslik(kir)
    basic = eski_basic = None

    try:
        print("── planlar ──")
        r = c.get("/api/platform/plans", headers=K)
        kontrol("kiracı plan listesine erişemez", r.status_code == 403, r.status_code)
        r = c.get("/api/platform/plans", headers=A)
        planlar = {p["kod"]: p for p in r.json()["items"]}
        kontrol("yönetici planları görür", r.status_code == 200 and "basic" in planlar, list(planlar))
        basic = planlar["basic"]
        eski_basic = {"aylik_ucret": basic["aylik_ucret"], "komisyon_orani": basic["komisyon_orani"]}
        r = c.patch(f"/api/platform/plans/{planlar['sahip']['id']}", headers=A, json={"moduller": ["magaza"]})
        kontrol("sahip planının modülleri değişmez", r.status_code == 400, r.status_code)
        r = c.patch(f"/api/platform/plans/{basic['id']}", headers=A, json={"moduller": ["uretim"]})
        kontrol("mağaza modülü her planda zorunlu", r.status_code == 400, r.status_code)
        r = c.patch(f"/api/platform/plans/{basic['id']}", headers=A,
                    json={"aylik_ucret": "750", "komisyon_orani": "3"})
        kontrol("plan fiyatı güncellenir", r.json().get("aylik_ucret") == "750.00", r.json())

        print("── plan atama ve ödeme ──")
        r = c.patch(f"/api/platform/tenants/{kir_t.id}", headers=A, json={"plan_id": basic["id"]})
        kontrol("kiracıya plan atanır", r.json().get("plan_ad") == "Basic", r.json())
        kontrol("eski metin alanı plan kodunu yansıtır", r.json().get("plan") == "basic", r.json())
        r = c.get(f"/api/platform/tenants/{kir_t.id}/abonelik", headers=A)
        kontrol("tahakkuk önizlemesi", r.json()["tahakkuk"]["toplam"] == "750.00", r.json()["tahakkuk"])
        govde = {"yontem": "havale", "ay_sayisi": 1, "beklenen_toplam": "750.00", "referans": "DEKONT-1"}
        r = c.post(f"/api/platform/tenants/{kir_t.id}/odemeler", headers=K, json=govde)
        kontrol("kiracı kendine ödeme giremez", r.status_code == 403, r.status_code)
        r = c.post(f"/api/platform/tenants/{kir_t.id}/odemeler", headers=A,
                   json={**govde, "beklenen_toplam": "700.00"})
        kontrol("önizlemeden farklı tutar reddedilir (409)", r.status_code == 409, r.status_code)
        r = c.post(f"/api/platform/tenants/{kir_t.id}/odemeler", headers=A, json=govde)
        kontrol("yönetici ödemeyi kaydeder", r.status_code == 201, r.status_code)
        odeme = r.json()

        print("── havale bilgisi ──")
        r = c.put("/api/platform/ayarlar/havale", headers=A, json={"iban": "TR12 3"})
        kontrol("geçersiz IBAN reddedilir", r.status_code == 400, r.status_code)
        r = c.put("/api/platform/ayarlar/havale", headers=K, json={"iban": "TR330006100519786457841326"})
        kontrol("kiracı havale bilgisini değiştiremez", r.status_code == 403, r.status_code)
        r = c.put("/api/platform/ayarlar/havale", headers=A,
                  json={"alici": "Test", "banka": "Banka", "iban": "tr33 0006 1005 1978 6457 8413 26"})
        kontrol("IBAN boşluksuz büyük harfe çevrilir",
                r.json().get("iban") == "TR330006100519786457841326", r.json())

        print("── kiracı görünümü ──")
        d = c.get("/api/abonelik", headers=K).json()
        kontrol("kiracı kendi planını görür", d["plan"]["ad"] == "Basic", d["plan"])
        kontrol("kiracı ödeme geçmişini görür", [o["toplam"] for o in d["odemeler"]] == ["750.00"], d["odemeler"])
        kontrol("kiracı havale bilgisi + ödeme kodunu görür",
                d["havale"]["iban"].startswith("TR33") and d["odeme_kodu"] == kir_t.slug, d["havale"])

        print("── geri alma ──")
        r = c.post(f"/api/platform/odemeler/{odeme['id']}/iptal", headers=K)
        kontrol("kiracı ödemeyi geri alamaz", r.status_code == 403, r.status_code)
        r = c.post(f"/api/platform/odemeler/{odeme['id']}/iptal", headers=A)
        kontrol("yönetici geri alır", r.json().get("durum") == "iptal", r.json())
        db.expire_all()
        kontrol("bitiş eski tarihine döner", db.get(Tenant, kir_t.id).active_until == eski_bitis,
                db.get(Tenant, kir_t.id).active_until)
        d = c.get("/api/abonelik", headers=K).json()
        kontrol("iptal edilen ödeme kiracıda görünmez", d["odemeler"] == [], d["odemeler"])
        r = c.get("/api/platform/tahakkuklar", headers=A)
        kontrol("tahsilat listesinde kiracı var",
                any(i["tenant_id"] == str(kir_t.id) for i in r.json()["items"]), r.status_code)
    finally:
        if basic and eski_basic:
            c.patch(f"/api/platform/plans/{basic['id']}", headers=A, json=eski_basic)
        db.rollback()
        ids = [adm_t.id, kir_t.id]
        db.execute(delete(AbonelikOdemesi).where(AbonelikOdemesi.tenant_id.in_(ids)))
        db.execute(delete(User).where(User.tenant_id.in_(ids)))
        db.execute(delete(Tenant).where(Tenant.id.in_(ids)))
        kayit = db.get(PlatformAyari, "havale")
        if havale_eski is None and kayit:
            db.delete(kayit)
        elif kayit:
            kayit.deger = havale_eski
        db.commit()
        db.close()

    print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
