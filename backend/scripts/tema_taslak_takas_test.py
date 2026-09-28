"""Tema taslakları — adıyla tutulur, yayında takas edilir.

Sınananlar:
  • taslağı yayınlamak YENİ kopya açmaz: eski yayın kendi adıyla taslağın
    boşalan yerine döner, taslak sayısı sabit kalır ("Önceki yayın — tarih" yok)
  • yayındaki tema, yayınlanan taslağın adını taşır
  • eski yayının adında taslak zaten varsa onun ÜZERİNE yazılır
  • üç temayı sırayla yayınlamak listeyi büyütmez
  • aynı adda ikinci taslak açılamaz (409); kendi adıyla yeniden kaydetmek serbest
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
from app.models import Tenant, User  # noqa: E402

GECTI = KALDI = 0
IZ = f"tttest{uuid.uuid4().hex[:6]}"


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


def tema(renk):
    return {"colors": {"primary": renk, "accent": "#f59e0b", "bg": "#ffffff"}, "sections": []}


try:
    r = c.post("/api/stores", headers=H, json={"name": "Tema testi", "slug": f"{IZ}-v",
                                                "platform": "storefront",
                                                "config": {"shop_domain": f"{IZ}.example.com"}})
    sid = r.json()["id"]
    T = f"/api/store-settings/{sid}/theme/drafts"

    def taslaklar():
        return {d["name"]: d for d in c.get(T, headers=H).json()["drafts"]}

    def yayin():
        return c.get(f"/api/store-settings/{sid}/theme", headers=H).json()

    print("\n── Takas ──")
    es("Füzyon taslağı", 200, c.put(f"{T}/t1", headers=H, json={"name": "Füzyon", "theme": tema("#111111")}).status_code)
    es("Manzara taslağı", 200, c.put(f"{T}/t2", headers=H, json={"name": "Manzara", "theme": tema("#222222")}).status_code)
    c.post(f"{T}/t1/publish", headers=H)
    es("yayın Füzyon adını taşır", ("Füzyon", "#111111"), (yayin()["name"], yayin()["colors"]["primary"]))
    es("eski yayın kendi adıyla döndü, kopya yok", {"Manzara", "Mağaza Teması"}, set(taslaklar()))

    c.post(f"{T}/t2/publish", headers=H)
    es("Manzara yayında", "Manzara", yayin()["name"])
    es("Füzyon kendi adıyla taslakta", ("Füzyon", "#111111"),
       ("Füzyon", taslaklar().get("Füzyon", {}).get("theme", {}).get("colors", {}).get("primary")))
    es("taslak sayısı sabit (2)", 2, len(taslaklar()))

    # Füzyon'u tekrar yayına al, düzenle, Manzara'ya geç: Füzyon'un taslağı GÜNCELLENİR
    fz = taslaklar()["Füzyon"]["key"]
    c.post(f"{T}/{fz}/publish", headers=H)
    c.put(f"/api/store-settings/{sid}/theme", headers=H, json={**tema("#999999"), "name": "Füzyon"})
    mz = taslaklar()["Manzara"]["key"]
    c.post(f"{T}/{mz}/publish", headers=H)
    d = taslaklar()
    es("yayındayken yapılan değişiklik Füzyon'un üzerine yazıldı", "#999999",
       d["Füzyon"]["theme"]["colors"]["primary"])
    es("üç geçişten sonra liste büyümedi", 2, len(d))
    es("'Önceki yayın' kaydı yok", False, any(n.startswith("Önceki yayın") for n in d))

    print("\n── Ad çakışması ──")
    es("aynı adda yeni taslak → 409", 409,
       c.put(f"{T}/t9", headers=H, json={"name": "Füzyon", "theme": tema("#333333")}).status_code)
    es("kendi adıyla yeniden kayıt serbest", 200,
       c.put(f"{T}/{d['Füzyon']['key']}", headers=H, json={"name": "Füzyon", "theme": tema("#444444")}).status_code)
finally:
    db.rollback()
    db.execute(text("delete from stores where slug like :s"), {"s": f"{IZ}-%"})
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
