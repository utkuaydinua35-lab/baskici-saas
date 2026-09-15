"""Bayi siparişi onay/düzeltme — baskı dosyasını YÜKLE, DEĞİŞTİR, GERİ AL.

Hata (2026-09-15): yönetici "PDF yükle" ile tasarımın KENDİ dosyasının üzerine
yazıyordu; ilk PDF'ten sonra düğme kayboluyordu (hatalı PDF değiştirilemiyordu),
bayinin aynı tasarımı kullanan DİĞER siparişlerinin dosyası da değişiyordu ve
bayinin orijinali siliniyordu. Sınananlar:
  • yüklenen dosya AYRI tasarım olur, yalnız bu kaleme bağlanır; diğer sipariş etkilenmez
  • tekrar yükleme aynı tasarımı DEĞİŞTİRİR, önizleme adresi yenilenir (önbellek)
  • geri al → bayinin orijinali; kullanılmayan yönetici dosyası silinir
  • bozuk PDF 400, kalıptaki kalem 409
  • yönetici Hepsiburada kargo kodunu düzeltir; bayi önizlemeyi sonradan ekler/kaldırır
"""
from __future__ import annotations

import io
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Dealer, Design, LineItem, Mold, MoldItem, Order, Store, Tenant, User  # noqa: E402
from app.services.storage import STORAGE_ROOT  # noqa: E402

c = TestClient(app)
GECTI = KALDI = 0
IZ = f"bbdtest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


def jpg(renk):
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (64, 64), renk).save(b, "JPEG"); return b.getvalue()


def pdf(renk):
    d = fitz.open(); p = d.new_page(width=200, height=400)
    p.draw_rect(p.rect, fill=renk, color=None); return d.tobytes()


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
d = Dealer(tenant_id=tenant.id, name=f"{IZ}-bayi", unit_price=100, shipping_fee=0, currency="TRY",
           is_active=True, balance=0, balance_usd=0)
db.add(d); db.flush()
st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="Bayii BBD", platform="bayii", is_active=True)
db.add(st); db.flush(); d.store_id = st.id
kul = User(tenant_id=tenant.id, email=f"{IZ}.b@test.example.com", password_hash=hash_password("Portal12345!"),
           full_name="BBD", role="bayii_portal", permissions=["bayii_portal"], dealer_id=d.id, is_active=True)
yon = User(tenant_id=tenant.id, email=f"{IZ}.y@test.example.com", password_hash=hash_password("Portal12345!"),
           full_name="Yön", role="yonetici", permissions=[], is_active=True)
db.add_all([kul, yon]); db.commit()
tok = lambda e: {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": e, "password": "Portal12345!"}).json()["access_token"]}  # noqa: E731
HB, HY = tok(kul.email), tok(yon.email)
mold = None

try:
    r1 = c.post("/api/bayii/siparis", headers=HB, data={"kanal": "trendyol", "ad_soyad": "A", "model": "IPHONE-15", "adet": "1"},
                files=[("tasarim", ("a.jpg", jpg((200, 30, 30)), "image/jpeg"))]).json()
    oA = r1["id"]
    liA = c.get(f"/api/bayii/siparis/{oA}", headers=HB).json()["kalemler"][0]
    orijinal_id = liA["tasarim_id"]
    r2 = c.post("/api/bayii/siparis", headers=HB, data={"kanal": "trendyol", "ad_soyad": "B", "model": "IPHONE-15",
                                                        "adet": "1", "tasarim_id": orijinal_id}).json()
    oB = r2["id"]
    orijinal = db.get(Design, uuid.UUID(orijinal_id)); db.refresh(orijinal)
    orijinal_dosya = (STORAGE_ROOT / orijinal.file_path).read_bytes()
    URL = f"/api/dealers/portal/siparis/{oA}/kalem/{liA['id']}/baski-dosyasi"

    print("\n── Yükle ──")
    es("bozuk PDF 400", 400, c.post(URL, headers=HY, files={"file": ("x.pdf", b"%PDF-bozuk", "application/pdf")}).status_code)
    r = c.post(URL, headers=HY, files={"file": ("yanlis.pdf", pdf((0, 0, 1)), "application/pdf")})
    es("200", 200, r.status_code)
    k = r.json()["kalem"]
    es("AYRI tasarım bağlandı", True, k["tasarim_id"] != orijinal_id)
    es("yönetici dosyası işaretli + orijinal kodu", (True, orijinal.code), (k["yonetici_dosyasi"], k["orijinal_kodu"]))
    es("format pdf", "pdf", k["format"])
    es("bayinin önizlemesi korunur (alan var)", True, "onizleme" in k)
    db.expire_all()
    es("B siparişi ETKİLENMEDİ", uuid.UUID(orijinal_id),
       db.scalar(select(LineItem.assigned_design_id).where(LineItem.order_id == uuid.UUID(oB))))
    es("bayinin orijinal dosyası SİLİNMEDİ/değişmedi", orijinal_dosya, (STORAGE_ROOT / orijinal.file_path).read_bytes())
    ilk_id, ilk_gorsel = k["tasarim_id"], k["gorsel"]
    es("PDF önizlemesi üretildi", True, bool(ilk_gorsel))

    print("\n── Hatalı dosyayı DEĞİŞTİR ──")
    time.sleep(1.1)
    r = c.post(URL, headers=HY, files={"file": ("dogru.png", jpg((10, 200, 10)), "image/png")})
    k = r.json()["kalem"]
    es("aynı tasarım yerinde değişti", (True, ilk_id), (r.json()["degistirildi"], k["tasarim_id"]))
    es("önizleme adresi yenilendi (önbellek)", True, bool(k["gorsel"]) and k["gorsel"] != ilk_gorsel)
    yeni = db.get(Design, uuid.UUID(ilk_id)); db.refresh(yeni)
    renk = fitz.open(STORAGE_ROOT / yeni.file_path)[0].get_pixmap(clip=fitz.Rect(0, 0, 4, 4)).pixel(1, 1)
    es("dosya gerçekten yeni içerik (yeşil)", True, renk[1] > renk[2])

    print("\n── Geri al ──")
    yol = yeni.file_path
    r = c.delete(URL, headers=HY)
    es("200 + silindi", (200, True), (r.status_code, r.json().get("silindi")))
    es("bayinin orijinaline döndü", (orijinal_id, False), (r.json()["kalem"]["tasarim_id"], r.json()["kalem"]["yonetici_dosyasi"]))
    db.expire_all()
    es("yönetici tasarımı DB'den silindi", None, db.get(Design, uuid.UUID(ilk_id)))
    es("yönetici dosyası diskten silindi", False, (STORAGE_ROOT / yol).exists())
    es("tekrar geri al 409", 409, c.delete(URL, headers=HY).status_code)

    print("\n── Kalıptaki kalem ──")
    mold = Mold(tenant_id=tenant.id, store_id=st.id, kod=f"{IZ}K", variation="SİYAH")
    db.add(mold); db.flush()
    db.add(MoldItem(tenant_id=tenant.id, mold_id=mold.id, line_item_id=uuid.UUID(liA["id"]), slot_index=0,
                    kalip_kodu="X", model="iPhone 15", order_number="x"))
    db.commit()
    es("kalıptaki kaleme yükleme 409", 409, c.post(URL, headers=HY, files={"file": ("a.pdf", pdf((1, 0, 0)), "application/pdf")}).status_code)

    print("\n── Yönetici Hepsiburada kodu düzeltir ──")
    es("Hepsiburada olmayan sipariş 409", 409, c.patch(f"/api/dealers/portal/siparis/{oB}/kargo-kodu", headers=HY,
                                                       json={"kargo_kodu": "1234567890"}).status_code)
    rh = c.post("/api/bayii/siparis", headers=HB, data={"kanal": "hepsiburada", "ad_soyad": "Ayşe Y", "model": "IPHONE-15",
                                                        "adet": "1", "tasarim_id": orijinal_id, "kargo_kodu": "1111222233"}).json()
    U = f"/api/dealers/portal/siparis/{rh['id']}/kargo-kodu"
    es("geçersiz kod 400", 400, c.patch(U, headers=HY, json={"kargo_kodu": "12"}).status_code)
    r = c.patch(U, headers=HY, json={"kargo_kodu": "4010 5913 4531"})
    es("düzeltildi (boşluksuz)", (200, "401059134531"), (r.status_code, r.json().get("kargo_kodu")))
    es("bayi de yeni kodu görür", "401059134531", c.get(f"/api/bayii/siparis/{rh['id']}", headers=HB).json()["kargo_kodu"])
    es("bayi bu uca giremez", 403, c.patch(U, headers=HB, json={"kargo_kodu": "9999999999"}).status_code)

    print("\n── Bayi önizlemeyi sonradan ekler / kaldırır ──")
    kB = c.get(f"/api/bayii/siparis/{oB}", headers=HB).json()["kalemler"][0]
    OU = f"/api/bayii/siparis/{oB}/kalem/{kB['id']}/onizleme"
    r = c.post(OU, headers=HB, files={"onizleme": ("o.jpg", jpg((1, 2, 3)), "image/jpeg")})
    es("önizleme eklendi", (200, True), (r.status_code, bool(r.json().get("onizleme"))))
    es("detayda görünür", True, bool(c.get(f"/api/bayii/siparis/{oB}", headers=HB).json()["kalemler"][0].get("onizleme")))
    es("kaldır 200", 200, c.delete(OU, headers=HB).status_code)
    es("kaldırıldı", None, c.get(f"/api/bayii/siparis/{oB}", headers=HB).json()["kalemler"][0].get("onizleme"))
    es("tekrar kaldır 409", 409, c.delete(OU, headers=HB).status_code)
finally:
    db.rollback()
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.store_id == st.id).execution_options(include_deleted=True)).all()]
    if mold is not None:
        db.execute(text("delete from mold_items where mold_id = :m").bindparams(m=mold.id))
        db.execute(text("delete from molds where id = :m").bindparams(m=mold.id))
    if oids:
        for q in ("delete from order_status_history where order_id = any(:o)",
                  "delete from notifications where store_id = :s",
                  "delete from line_items where order_id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(s=st.id) if ":s" in q else text(q).bindparams(o=oids))
    for ds in db.scalars(select(Design).where(Design.store_id == st.id)).all():
        from app.services import storage
        storage.delete_design_file(ds.file_path)
    db.execute(text("delete from designs where store_id = :s").bindparams(s=st.id))
    db.execute(text("delete from users where email like :p").bindparams(p=f"{IZ}%"))
    db.execute(text("delete from dealers where id = :d").bindparams(d=d.id))
    db.execute(text("delete from stores where id = :s").bindparams(s=st.id))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
