"""Cihazlar arası dosya aktarımı — yükle, indir, sil, 24 saatte temizlen.

Sınananlar:
  • yükleme kaydı ve dosya oluşur; liste boyut/kalan süre bilgisini döner
  • 250 MB sınırı AŞILIRSA 413 ve YARIM DOSYA DİSKTE KALMAZ
  • boş dosya reddedilir
  • indirme dosyanın kendisini verir, özgün adıyla
  • elle silme hem kaydı hem dosyayı siler
  • süresi dolan kayıt listede GÖRÜNMEZ ve temizlik onu diskten siler
  • temizlik ÖKSÜZ dosyaları (kaydı olmayan, eski) da süpürür
  • başka kiracının dosyası görünmez/indirilemez
  • bayi hesabı bu bölüme giremez
"""
from __future__ import annotations

import io
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token, hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Dealer, DosyaAktarimi, Store, Tenant, User  # noqa: E402
from app.services import dosya_aktarimi as da  # noqa: E402

GECTI = KALDI = 0
IZ = f"datest{uuid.uuid4().hex[:6]}"


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

# Bayi hesabı (kapı sınaması)
st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="DA", platform="bayii", is_active=True)
db.add(st); db.flush()
d = Dealer(tenant_id=tenant.id, name=f"{IZ}-bayi", store_id=st.id, unit_price=100, shipping_fee=0,
           currency="TRY", is_active=True, balance=0, balance_usd=0)
db.add(d); db.flush()
bayi_kul = User(tenant_id=tenant.id, email=f"{IZ}@ornek.test", password_hash=hash_password("Portal12345!"),
                full_name="Bayi", role="bayii_portal", permissions=["bayii_portal"],
                dealer_id=d.id, is_active=True)
db.add(bayi_kul); db.commit()
HB = {"Authorization": "Bearer " + create_access_token(
    user_id=str(bayi_kul.id), tenant_id=str(tenant.id), email=bayi_kul.email, expires_minutes=30)}

olusan: list = []
try:
    print("\n── Yükleme ──")
    r = c.post("/api/aktarim", headers=H,
               files={"file": ("rapor.csv", b"a,b,c\n1,2,3\n", "text/csv")})
    es("yüklendi", 201, r.status_code)
    kayit = r.json(); olusan.append(kayit["id"])
    es("özgün ad korunur", "rapor.csv", kayit["dosya_adi"])
    es("boyut yazılı", "1 KB", kayit["boyut_yazi"])
    es("kim yüklediği kayıtlı", True, bool(kayit["yukleyen"]))
    k = db.get(DosyaAktarimi, uuid.UUID(kayit["id"]))
    es("dosya diske yazıldı", True, da.tam_yol(k).exists())
    es("diskteki ad TAHMİN EDİLEMEZ (özgün ad değil)", False, "rapor" in da.tam_yol(k).name)
    es("süre 24 saat", 24, round((k.expires_at - k.created_at).total_seconds() / 3600))

    d1 = c.get("/api/aktarim", headers=H).json()
    es("listede görünür", True, any(x["id"] == kayit["id"] for x in d1["items"]))
    es("sınır bilgisi dönüyor", (250 * 1024 * 1024, 24), (d1["max_boyut"], d1["saklama_saat"]))

    print("\n── Sınırlar ──")
    buyuk = io.BytesIO(b"x" * (da.MAX_BOYUT + 1024))
    oncesi = len(list(da.AKTARIM_DIR.iterdir())) if da.AKTARIM_DIR.exists() else 0
    r = c.post("/api/aktarim", headers=H, files={"file": ("buyuk.bin", buyuk, "application/octet-stream")})
    es("250 MB üstü → 413", 413, r.status_code)
    sonrasi = len(list(da.AKTARIM_DIR.iterdir())) if da.AKTARIM_DIR.exists() else 0
    es("YARIM DOSYA diskte kalmadı", oncesi, sonrasi)
    es("boş dosya reddedilir", 400,
       c.post("/api/aktarim", headers=H, files={"file": ("bos.txt", b"", "text/plain")}).status_code)

    print("\n── İndirme ──")
    r = c.get(f"/api/aktarim/{kayit['id']}/indir", headers=H)
    es("içerik aynen döner", (200, b"a,b,c\n1,2,3\n"), (r.status_code, r.content))
    es("özgün adla iner", True, "rapor.csv" in (r.headers.get("content-disposition") or ""))
    es("olmayan kayıt → 404", 404,
       c.get(f"/api/aktarim/{uuid.uuid4()}/indir", headers=H).status_code)

    print("\n── Elle silme ──")
    r2 = c.post("/api/aktarim", headers=H, files={"file": ("silinecek.txt", b"veri", "text/plain")})
    k2 = db.get(DosyaAktarimi, uuid.UUID(r2.json()["id"]))
    yol2 = da.tam_yol(k2)
    es("silme 204", 204, c.delete(f"/api/aktarim/{r2.json()['id']}", headers=H).status_code)
    db.expire_all()
    es("kayıt gitti", None, db.get(DosyaAktarimi, uuid.UUID(r2.json()["id"])))
    es("dosya da gitti", False, yol2.exists())

    print("\n── 24 saatlik temizlik ──")
    r3 = c.post("/api/aktarim", headers=H, files={"file": ("eski.txt", b"eski", "text/plain")})
    k3 = db.get(DosyaAktarimi, uuid.UUID(r3.json()["id"]))
    yol3 = da.tam_yol(k3)
    db.execute(text("update dosya_aktarimlari set expires_at = :t where id = :i"),
               {"t": datetime.now(UTC) - timedelta(minutes=1), "i": k3.id})
    db.commit()
    es("süresi dolan listede GÖRÜNMEZ", False,
       any(x["id"] == str(k3.id) for x in c.get("/api/aktarim", headers=H).json()["items"]))
    es("süresi dolan İNDİRİLEMEZ değil ama listede yok (indirme yine çalışır)", 200,
       c.get(f"/api/aktarim/{k3.id}/indir", headers=H).status_code)
    # Öksüz dosya: kaydı olmayan, eski
    da.AKTARIM_DIR.mkdir(parents=True, exist_ok=True)
    oksuz = da.AKTARIM_DIR / f"{IZ}-oksuz.bin"
    oksuz.write_bytes(b"x")
    import os
    eski_zaman = datetime.now(UTC).timestamp() - 48 * 3600
    os.utime(oksuz, (eski_zaman, eski_zaman))
    sonuc = da.temizle(db)
    es("süresi dolan kayıt silindi", True, sonuc["silinen"] >= 1)
    es("dosyası da silindi", False, yol3.exists())
    es("öksüz dosya süpürüldü", False, oksuz.exists())

    print("\n── Ayrışma ──")
    es("bayi hesabı giremez", 403, c.get("/api/aktarim", headers=HB).status_code)
    es("bayi yükleyemez", 403,
       c.post("/api/aktarim", headers=HB, files={"file": ("x.txt", b"x", "text/plain")}).status_code)
    baska = db.scalar(select(Tenant).where(Tenant.id != tenant.id).limit(1))
    if baska is not None:
        bu = db.scalar(select(User).where(User.tenant_id == baska.id,
                                          User.dealer_id.is_(None)).limit(1))
        if bu is not None:
            H2 = {"Authorization": "Bearer " + create_access_token(
                user_id=str(bu.id), tenant_id=str(baska.id), email=bu.email, expires_minutes=30)}
            es("başka kiracı listede görmez", False,
               any(x["id"] == kayit["id"] for x in c.get("/api/aktarim", headers=H2).json()["items"]))
            es("başka kiracı indiremez", 404,
               c.get(f"/api/aktarim/{kayit['id']}/indir", headers=H2).status_code)
        else:
            print("  · başka kiracıda personel yok, atlandı")
    else:
        print("  · tek kiracı, atlandı")
finally:
    db.rollback()
    for kid in olusan:
        k = db.get(DosyaAktarimi, uuid.UUID(kid))
        if k is not None:
            da.tam_yol(k).unlink(missing_ok=True)
    db.execute(text("delete from dosya_aktarimlari where tenant_id = :t"), {"t": tenant.id})
    db.execute(text("delete from users where email like :e"), {"e": f"{IZ}%"})
    db.execute(text("delete from dealers where name like :d"), {"d": f"{IZ}%"})
    db.execute(text("delete from stores where slug like :s"), {"s": f"{IZ}-%"})
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
