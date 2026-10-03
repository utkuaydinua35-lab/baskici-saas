"""Bayi masaüstü uygulaması — indirme sayfasının beslediği uç.

Kurulum dosyaları veritabanında DEĞİL, klasörde duruyor: yeni sürümü
uploads/uygulama/ içine kopyalamak yayınlamaya yeter. Bu testin işi o
sözleşmeyi sabitlemek.

Sınananlar:
  • dosya adından platform, mimari ve sürüm çözülür (mac arm64/x64, windows)
  • boyut ve indirme adresi döner; mac/windows ayrı listelenir
  • kurala uymayan dosya LİSTELENMEZ (klasöre düşen rastgele dosya bayiye
    "kurulum" diye gösterilmesin)
  • son sürüm doğru hesaplanır (10.0.0 > 9.0.0 — metin sıralaması yanıltmasın)
  • uç bayiye açık, yetkisiz kullanıcıya kapalı
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token, hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Dealer, Store, Tenant, User  # noqa: E402
from app.services import bayi_uygulama as bu  # noqa: E402

GECTI = KALDI = 0
IZ = f"butest{uuid.uuid4().hex[:6]}"
DOSYALAR = [
    "BERNZ-Bayi-9.9.9-arm64.dmg",
    "BERNZ-Bayi-9.9.9-x64.dmg",
    "BERNZ-Bayi-Kurulum-9.9.9.exe",
    "BERNZ-Bayi-10.0.0-arm64.dmg",
    "BERNZ-Studyo-9.9.9-arm64.dmg",  # yönetim kurulumu — bayiye GÖRÜNMEMELİ
    "BERNZ-Studyo-Kurulum-9.9.9.exe",
    "okuma-notu.txt",               # kurala uymayan — listelenmemeli
]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yazilan = []
try:
    print("\n── Klasördeki dosyalar ──")
    bu.UYGULAMA_DIR.mkdir(parents=True, exist_ok=True)
    for ad in DOSYALAR:
        p = bu.UYGULAMA_DIR / ad
        p.write_bytes(b"x" * 1024)
        yazilan.append(p)

    kayitlar = [k for k in bu.kurulumlar() if k["surum"] in ("9.9.9", "10.0.0")]
    es("yalnız kurala uyan dosyalar listelenir", 4, len(kayitlar))
    es("txt dosyası listede yok", 0, len([k for k in kayitlar if k["dosya"].endswith(".txt")]))
    mac = sorted([k for k in kayitlar if k["platform"] == "mac"], key=lambda k: (k["surum"], k["mimari"]))
    es("mac mimarileri çözüldü", ["arm64", "x64"], sorted({k["mimari"] for k in mac}))
    es("mimari etiketi okunur", "Apple Silicon (M1/M2/M3/M4)",
       next(k["mimari_etiket"] for k in mac if k["mimari"] == "arm64"))
    win = [k for k in kayitlar if k["platform"] == "windows"]
    es("windows kurulumu çözüldü", ("9.9.9", "x64"), (win[0]["surum"], win[0]["mimari"]))
    es("indirme adresi /uploads/uygulama altında", True,
       win[0]["url"].endswith("/uploads/uygulama/BERNZ-Bayi-Kurulum-9.9.9.exe"))
    es("boyut yazılı", True, bool(win[0]["boyut"]))
    es("son sürüm sayısal karşılaştırmayla (10 > 9)", "10.0.0", bu.son_surum(kayitlar))

    print("\n── Uç ──")
    st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="BU", platform="bayii", is_active=True)
    db.add(st); db.flush()
    d = Dealer(tenant_id=tenant.id, name=f"{IZ}-bayi", store_id=st.id, unit_price=100,
               shipping_fee=0, currency="TRY", is_active=True, balance=0, balance_usd=0)
    db.add(d); db.flush()
    kul = User(tenant_id=tenant.id, email=f"{IZ}@ornek.test", password_hash=hash_password("Portal12345!"),
               full_name="Bayi", role="bayii_portal", permissions=["bayii_portal"],
               dealer_id=d.id, is_active=True)
    yabanci = User(tenant_id=tenant.id, email=f"{IZ}.y@ornek.test", password_hash=hash_password("Portal12345!"),
                   full_name="Yabancı", role="operator", permissions=["paketleme"], is_active=True)
    db.add_all([kul, yabanci]); db.commit()

    c = TestClient(app)
    H = {"Authorization": "Bearer " + create_access_token(
        user_id=str(kul.id), tenant_id=str(tenant.id), email=kul.email, expires_minutes=30)}
    HY = {"Authorization": "Bearer " + create_access_token(
        user_id=str(yabanci.id), tenant_id=str(tenant.id), email=yabanci.email, expires_minutes=30)}
    r = c.get("/api/bayii/uygulama", headers=H)
    es("bayi listeyi görür", 200, r.status_code)
    es("mac ve windows ayrı listelenir", True,
       len(r.json()["mac"]) >= 3 and len(r.json()["windows"]) >= 1)
    es("yetkisiz kullanıcı göremez", 403, c.get("/api/bayii/uygulama", headers=HY).status_code)
    es("bayi listesinde YÖNETİM kurulumu yok", 0,
       len([k for k in r.json()["kurulumlar"] if "Studyo" in k["dosya"]]))

    print("\n── Yönetim profili ──")
    yonetici = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                           User.role.in_(["owner", "yonetici"]),
                                           User.dealer_id.is_(None)).limit(1))
    HA = {"Authorization": "Bearer " + create_access_token(
        user_id=str(yonetici.id), tenant_id=str(tenant.id), email=yonetici.email, expires_minutes=30)}
    r = c.get("/api/masaustu/kurulumlar?profil=studio", headers=HA)
    es("yönetim kurulumları listelenir", 200, r.status_code)
    adlar = {k["dosya"] for k in r.json()["kurulumlar"]}
    es("yalnız Studyo dosyaları", True,
       "BERNZ-Studyo-9.9.9-arm64.dmg" in adlar and not any("Bayi" in a for a in adlar))
    es("geçersiz profil → 400", 400,
       c.get("/api/masaustu/kurulumlar?profil=xx", headers=HA).status_code)
    es("bayi yönetim ucuna giremez", 403,
       c.get("/api/masaustu/kurulumlar?profil=studio", headers=H).status_code)
finally:
    for p in yazilan:
        try: p.unlink()
        except OSError: pass
    db.rollback()
    db.execute(text("delete from users where email like :e"), {"e": f"{IZ}%"})
    db.execute(text("delete from dealers where name like :d"), {"d": f"{IZ}%"})
    db.execute(text("delete from stores where slug like :s"), {"s": f"{IZ}-%"})
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
