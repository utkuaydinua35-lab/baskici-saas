"""Bayi portali ucdan uca testi — GERCEK HTTP istekleri, gercek veritabani.

Sinananlar:
  • yetkisiz erisim (izinsiz kullanici / baska bayinin verisi)
  • kanal kurallari (trendyol: ad yeter; shopier/instagram: tam adres)
  • duzenleme kurallari (kaliba girdi / barkod olustu)
  • onay akisi: borc ONAYDA yazilir, iki kez onay borcu ikilemez
  • onay bekleyen siparis kalip planina GIRMEZ
Test verisi sonunda temizlenir.
"""
from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Dealer, DealerTransaction, Design, LineItem, MoldItem,  # noqa: E402
                        Order, Store, Tenant, User)

ISTEMCI = TestClient(app)
GECTI, KALDI = 0, 0
IZ = f"bptest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


def jpg(renk=(120, 40, 200)) -> bytes:
    """Gecerli, kucuk bir JPEG. Renk degisince ICERIK de degisir.

    Onemli: ayni baytlar yuklenirse sunucu mukerrer dosya yazmaz ve MEVCUT
    tasarimi dondurur (bkz. tasarim_dedup_test). Farkli tasarim bekleyen
    testler farkli renk vermeli."""
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (64, 64), renk).save(b, "JPEG")
    return b.getvalue()


def token(email, sifre="Portal12345!"):
    r = ISTEMCI.post("/api/auth/login", json={"email": email, "password": sifre})
    if r.status_code != 200:
        raise SystemExit(f"login basarisiz {email}: {r.status_code} {r.text[:300]}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ─── Kurulum ────────────────────────────────────────────────
db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
if not tenant:
    raise SystemExit("Tenant yok — once uygulamayi bir kez calistir.")


def _eski_test_verisini_temizle() -> None:
    """Yarida kalmis onceki kosulardan artan kayitlari sil (hepsi 'bptest' onekli)."""
    db.execute(text("""
        delete from order_status_history where order_id in
          (select id from orders where store_id in
             (select id from stores where slug like 'bptest%'))"""))
    db.execute(text("""
        delete from mold_items where line_item_id in
          (select id from line_items where order_id in
             (select id from orders where store_id in
                (select id from stores where slug like 'bptest%')))"""))
    db.execute(text("""
        delete from line_items where order_id in
          (select id from orders where store_id in
             (select id from stores where slug like 'bptest%'))"""))
    db.execute(text("delete from orders where store_id in "
                    "(select id from stores where slug like 'bptest%')"))
    db.execute(text("delete from mold_items where mold_id in "
                    "(select id from molds where kod like 'bptest%')"))
    db.execute(text("delete from molds where kod like 'bptest%'"))
    db.execute(text("delete from dealer_transactions where dealer_id in "
                    "(select id from dealers where name like 'bptest%')"))
    db.execute(text("delete from designs where store_id in "
                    "(select id from stores where slug like 'bptest%')"))
    db.execute(text("delete from users where email like 'bptest%'"))
    db.execute(text("delete from dealers where name like 'bptest%'"))
    db.execute(text("delete from stores where slug like 'bptest%'"))
    db.commit()


_eski_test_verisini_temizle()


def bayi_kur(ad, birim, kargo, para="TRY"):
    d = Dealer(tenant_id=tenant.id, name=f"{IZ}-{ad}", unit_price=birim,
               shipping_fee=kargo, currency=para, is_active=True, balance=0, balance_usd=0)
    db.add(d); db.flush()
    st = Store(tenant_id=tenant.id, slug=f"{IZ}-{ad}", name=f"Bayii {ad}",
               platform="bayii", is_active=True)
    db.add(st); db.flush()
    d.store_id = st.id
    u = User(tenant_id=tenant.id, email=f"{IZ}.{ad}@bayitest.example.com",
             password_hash=hash_password("Portal12345!"), full_name=f"Bayi {ad}",
             role="bayii_portal", permissions=["bayii_portal"], dealer_id=d.id,
             is_active=True)
    db.add(u); db.flush()
    return d, u


bayi_a, kul_a = bayi_kur("a", 100, 50)
bayi_b, kul_b = bayi_kur("b", 200, 0)
# Yetkisiz kullanici: bayi degil, izni de yok
yabanci = User(tenant_id=tenant.id, email=f"{IZ}.yabanci@bayitest.example.com",
               password_hash=hash_password("Portal12345!"), full_name="Yabanci",
               role="operator", permissions=["paketleme"], is_active=True)
# Bayi izni var ama dealer_id YOK
kopuk = User(tenant_id=tenant.id, email=f"{IZ}.kopuk@bayitest.example.com",
             password_hash=hash_password("Portal12345!"), full_name="Kopuk",
             role="operator", permissions=["bayii_portal"], is_active=True)
# Yonetici (onay icin)
admin = User(tenant_id=tenant.id, email=f"{IZ}.admin@bayitest.example.com",
             password_hash=hash_password("Portal12345!"), full_name="Admin",
             role="yonetici", permissions=[], is_active=True)
db.add_all([yabanci, kopuk, admin])
db.commit()

H_A, H_B = token(kul_a.email), token(kul_b.email)
H_YABANCI, H_KOPUK, H_ADMIN = token(yabanci.email), token(kopuk.email), token(admin.email)


def siparis_ac(h, urunler=None, **alan):
    """urunler: [(model, adet), ...] — coklu urun. Verilmezse tek urun."""
    urunler = urunler or [("IPHONE-15", 1)]
    veri = {"kanal": "trendyol", "ad_soyad": "Ali Veli"}
    veri |= {k: str(v) for k, v in alan.items()}
    veri["model"] = [m for m, _ in urunler]
    veri["adet"] = [str(a) for _, a in urunler]
    # Her kalem FARKLI icerik: ayni baytlar yuklenirse sunucu mukerrer dosya
    # yazmaz ve tek tasarim doner (dedup) — burada ayrisma sinaniyor.
    dosyalar = [("tasarim", (f"{i}.jpg", jpg((10 + i * 60, 40, 200)), "image/jpeg"))
                for i in range(len(urunler))]
    return ISTEMCI.post("/api/bayii/siparis", headers=h, data=veri, files=dosyalar)


print("\n── 1. Yetki ──")
es("izinsiz kullanici 403", 403, ISTEMCI.get("/api/bayii/ozet", headers=H_YABANCI).status_code)
es("token yok 401", 401, ISTEMCI.get("/api/bayii/ozet").status_code)
es("bayiye bagli olmayan hesap 403", 403,
   ISTEMCI.get("/api/bayii/ozet", headers=H_KOPUK).status_code)
es("bayi kendi ozetini gorur", 200, ISTEMCI.get("/api/bayii/ozet", headers=H_A).status_code)
es("bayi yonetim ucuna giremez", 403,
   ISTEMCI.get("/api/dealers", headers=H_A).status_code)
es("bayi siparis paneline giremez", 403,
   ISTEMCI.get("/api/orders", headers=H_A).status_code)

print("\n── 2. Kanal kurallari ──")
es("gecersiz kanal 400", 400, siparis_ac(H_A, kanal="ciceksepeti").status_code)
es("ad soyad bos 400", 400, siparis_ac(H_A, ad_soyad="  ").status_code)
es("shopier: adres eksik 400", 400, siparis_ac(H_A, kanal="shopier").status_code)
r = siparis_ac(H_A, kanal="shopier", telefon="5551112233", adres="Test sk 1",
               il="Istanbul", ilce="Kadikoy")
es("shopier: tam adres 201", 201, r.status_code)
shopier_id = r.json().get("id")
r = siparis_ac(H_A, kanal="trendyol", ad_soyad="Ayse Yilmaz")
es("trendyol: sadece ad 201", 201, r.status_code)
tr_id = r.json().get("id")
es("adet 0 reddedilir", 400, siparis_ac(H_A, urunler=[("IPHONE-15", 0)]).status_code)
es("model bos reddedilir", 400, siparis_ac(H_A, urunler=[(" ", 1)]).status_code)
rb = ISTEMCI.post("/api/bayii/siparis", headers=H_A,
                  data={"model": "IPHONE-15", "adet": "1", "kanal": "trendyol",
                        "ad_soyad": "X"},
                  files=[("tasarim", ("t.exe", b"MZ", "application/octet-stream"))])
es("izinsiz uzanti 400", 400, rb.status_code)

print("\n── 3. Izolasyon ──")
es("B bayisi A'nin siparisini goremez", 404,
   ISTEMCI.get(f"/api/bayii/siparis/{tr_id}", headers=H_B).status_code)
_kid = lambda oid, h=None, i=0: ISTEMCI.get(
    f"/api/bayii/siparis/{oid}", headers=h or H_A).json()["kalemler"][i]["id"]
es("B, A'nin siparisini duzenleyemez", 404,
   ISTEMCI.patch(f"/api/bayii/siparis/{tr_id}/kalem/{uuid.uuid4()}", headers=H_B,
                 json={"model": "IPHONE-14"}).status_code)
es("B, A'nin siparisini silemez", 404,
   ISTEMCI.delete(f"/api/bayii/siparis/{tr_id}", headers=H_B).status_code)
es("B'nin listesi bos", 0,
   len(ISTEMCI.get("/api/bayii/siparisler", headers=H_B).json()["items"]))
es("A'nin listesi 2", 2,
   len(ISTEMCI.get("/api/bayii/siparisler", headers=H_A).json()["items"]))

print("\n── 4. Onay oncesi: borc YOK, kalip YOK ──")
db.expire_all()
db.refresh(bayi_a)
es("onay oncesi bakiye 0", 0.0, float(bayi_a.balance or 0))
es("onay oncesi cari hareket yok", 0, db.scalar(
    text("select count(*) from dealer_transactions where dealer_id=:d")
    .bindparams(d=bayi_a.id)))
es("ozet: onay bekleyen 2", 2,
   ISTEMCI.get("/api/bayii/ozet", headers=H_A).json()["sayilar"]["onay_bekleyen"])

print("\n── 5. Duzenleme kurallari ──")
d0 = ISTEMCI.get(f"/api/bayii/siparis/{tr_id}", headers=H_A).json()
es("yeni siparis duzenlenebilir", True, d0["yetkiler"]["urun_degistir"])
es("yeni siparis adresi degisebilir", True, d0["yetkiler"]["adres_degistir"])
tr_kalem = _kid(tr_id)
es("model degisir", 200, ISTEMCI.patch(
    f"/api/bayii/siparis/{tr_id}/kalem/{tr_kalem}",
    headers=H_A, json={"model": "IPHONE-14 PRO"}).status_code)
d1 = ISTEMCI.get(f"/api/bayii/siparis/{tr_id}", headers=H_A).json()
# Model adı OKUNUR biçimde kaydedilir (phone_models.gorunen_ad) — ölçü aynı kalır.
es("model yazildi", "iPhone 14 Pro", d1["kalemler"][0]["model"])
es("degisiklik gecmise dustu", True,
   any("iPhone 14 Pro" in (h["not"] or "") for h in d1["gecmis"]))
es("tasarim degisir", 200, ISTEMCI.post(
    f"/api/bayii/siparis/{tr_id}/kalem/{tr_kalem}/tasarim", headers=H_A,
    files={"tasarim": ("y.jpg", jpg(), "image/jpeg")}).status_code)
es("adres degisir", 200, ISTEMCI.patch(f"/api/bayii/siparis/{tr_id}/adres",
   headers=H_A, json={"ad_soyad": "Yeni Alici"}).status_code)
es("adres yazildi", "Yeni Alici",
   ISTEMCI.get(f"/api/bayii/siparis/{tr_id}", headers=H_A).json()["adres"]["ad"])
es("shopier adresi eksik girilemez", 400,
   ISTEMCI.patch(f"/api/bayii/siparis/{shopier_id}/adres", headers=H_A,
                 json={"ad_soyad": "Bos Adres"}).status_code)

print("\n── 6. Barkod olustu -> adres kilitli ──")
o_tr = db.scalar(select(Order).where(Order.id == uuid.UUID(tr_id)))
o_tr.barkod_kodu = "TESTBARKOD1"
db.commit()
d2 = ISTEMCI.get(f"/api/bayii/siparis/{tr_id}", headers=H_A).json()
es("barkod_var true", True, d2["yetkiler"]["barkod_var"])
es("adres_degistir false", False, d2["yetkiler"]["adres_degistir"])
es("adres degisimi 409", 409, ISTEMCI.patch(f"/api/bayii/siparis/{tr_id}/adres",
   headers=H_A, json={"ad_soyad": "Olmaz"}).status_code)
es("model hala degisebilir (kaliba girmedi)", 200,
   ISTEMCI.patch(f"/api/bayii/siparis/{tr_id}/kalem/{tr_kalem}", headers=H_A,
                 json={"model": "IPHONE-13"}).status_code)

print("\n── 7. Kaliba girdi -> her sey kilitli ──")
li = db.scalar(select(LineItem).where(LineItem.order_id == o_tr.id))
li.is_kaliba_eklendi = True
db.commit()
d3 = ISTEMCI.get(f"/api/bayii/siparis/{tr_id}", headers=H_A).json()
es("uretimde true", True, d3["yetkiler"]["uretimde"])
es("urun_degistir false", False, d3["yetkiler"]["urun_degistir"])
es("model degisimi 409", 409, ISTEMCI.patch(
    f"/api/bayii/siparis/{tr_id}/kalem/{tr_kalem}", headers=H_A,
    json={"model": "X"}).status_code)
es("tasarim degisimi 409", 409, ISTEMCI.post(
    f"/api/bayii/siparis/{tr_id}/kalem/{tr_kalem}/tasarim", headers=H_A,
    files={"tasarim": ("z.jpg", jpg(), "image/jpeg")}).status_code)
es("silme 409", 409, ISTEMCI.delete(f"/api/bayii/siparis/{tr_id}", headers=H_A).status_code)

print("\n── 8. Onay: borc ONAYDA yazilir ──")
bekleyen = ISTEMCI.get("/api/dealers/portal/onay-bekleyen", headers=H_ADMIN).json()
benim = [x for x in bekleyen if x["id"] in (tr_id, shopier_id)]
es("onay kuyrugunda 2 siparis", 2, len(benim))
kalem_id = [x for x in benim if x["id"] == shopier_id][0]["kalemler"][0]["id"]
r = ISTEMCI.post(f"/api/dealers/portal/onay-bekleyen/{shopier_id}", headers=H_ADMIN,
                 json={"varyasyonlar": {kalem_id: "siyah"}, "apply_shipping": True})
es("onay 200", 200, r.status_code)
j = r.json()
es("urun borcu 100", 100.0, j["urun"])
es("kargo borcu 50", 50.0, j["kargo"])
db.expire_all(); db.refresh(bayi_a)
es("bakiye 150", 150.0, float(bayi_a.balance or 0))
r2 = ISTEMCI.post(f"/api/dealers/portal/onay-bekleyen/{shopier_id}", headers=H_ADMIN,
                  json={"varyasyonlar": {}})
es("ikinci onay 409", 409, r2.status_code)
db.expire_all(); db.refresh(bayi_a)
es("bakiye ikilenmedi", 150.0, float(bayi_a.balance or 0))
o_sh = db.scalar(select(Order).where(Order.id == uuid.UUID(shopier_id)))
es("onay bayragi dustu", False, bool(o_sh.bayii_onay_bekliyor))
# normalize_variation Turkce buyuk harf uretir: "siyah" -> "SIYAH" degil "SİYAH"
es("varyasyon yazildi", "SİYAH",
   db.scalar(select(LineItem).where(LineItem.order_id == o_sh.id)).kilif_varyasyon)
# Onaylanmis ama KALIBA GIRMEMIS siparis: bayi geri cekebilir, borc iade edilir.
_gc = siparis_ac(H_A, urunler=[("IPHONE-15", 1)], kanal="trendyol", ad_soyad="Geri Cekilecek")
_gc_id = _gc.json()["id"]
_gck = ISTEMCI.get(f"/api/bayii/siparis/{_gc_id}", headers=H_A).json()["kalemler"][0]["id"]
ISTEMCI.post(f"/api/dealers/portal/onay-bekleyen/{_gc_id}", headers=H_ADMIN,
             json={"varyasyonlar": {_gck: "siyah"}, "apply_shipping": False})
db.expire_all(); db.refresh(bayi_a)
_gc_bakiye = float(bayi_a.balance or 0)
es("onay sonrasi bakiye artti", 250.0, _gc_bakiye)
es("kaliba girmemis onayli siparis geri cekilir", 200,
   ISTEMCI.delete(f"/api/bayii/siparis/{_gc_id}", headers=H_A).status_code)
db.expire_all(); db.refresh(bayi_a)
es("geri cekmede borc IADE edildi", 150.0, float(bayi_a.balance or 0))
_gcd = ISTEMCI.get(f"/api/bayii/siparis/{_gc_id}", headers=H_A).json()
es("iptal edildi olarak isaretli", True, _gcd["iptal"])
es("iptal sonrasi duzenleme kapali", False, _gcd["yetkiler"]["urun_degistir"])

print("\n── 9. Cari ekrani ──")
c = ISTEMCI.get("/api/bayii/cari", headers=H_A).json()
es("cari bakiye 150", 150.0, c["bakiye"])
es("hareket sayisi", 4, len(c["items"]))  # 2 borc (siparis+kargo) + 1 borc + 1 ters
es("B bayisinin carisi bos", 0, len(ISTEMCI.get("/api/bayii/cari", headers=H_B).json()["items"]))

print("\n── 10. Kalip plani: onay bekleyen GIRMEZ, onaylanan GIRER ──")
from app.services.mold_planner import plan_molds  # noqa: E402


def _planda_var(order_no: str) -> bool:
    """Siparis kalip planinda bir slot aldi mi."""
    p = plan_molds(db, tenant_id=tenant.id, store_id=bayi_a.store_id)
    for kalip in p.get("molds", []) or []:
        for it in (kalip.get("items") or []):
            if str(it.get("order_number") or "") == order_no:
                return True
    return False


o_tr_no = db.scalar(select(Order.order_number).where(Order.id == uuid.UUID(tr_id)))
o_sh_no = db.scalar(select(Order.order_number).where(Order.id == uuid.UUID(shopier_id)))
es("onay BEKLEYEN plana girmedi", False, _planda_var(o_tr_no))
es("ONAYLANAN plana girdi", True, _planda_var(o_sh_no))

print("\n── 11. Onay beklerken geri cekme ──")
r = siparis_ac(H_B, kanal="instagram", telefon="5559998877", adres="B sk 2",
               il="Ankara", ilce="Cankaya")
b_id = r.json()["id"]
es("B siparis acti", 201, r.status_code)
es("B geri cekebilir", 200, ISTEMCI.delete(f"/api/bayii/siparis/{b_id}", headers=H_B).status_code)
_bl = ISTEMCI.get("/api/bayii/siparisler", headers=H_B).json()["items"]
es("geri cekilen listede KALIR", 1, len(_bl))
es("iptal olarak isaretli", True, _bl[0]["iptal"])
db.expire_all(); db.refresh(bayi_b)
es("geri cekmede borc yok", 0.0, float(bayi_b.balance or 0))

print("\n── 13. Coklu urun ──")
r = siparis_ac(H_A, urunler=[("IPHONE-15", 2), ("IPHONE-14 PRO", 1), ("SAMSUNG-S23", 3)],
               kanal="trendyol", ad_soyad="Coklu Musteri")
es("3 urunlu siparis 201", 201, r.status_code)
cok_id = r.json().get("id")
es("kalem sayisi 3", 3, r.json().get("kalem_sayisi"))
es("toplam adet 6", 6, r.json().get("toplam_adet"))

dc = ISTEMCI.get(f"/api/bayii/siparis/{cok_id}", headers=H_A).json()
es("detayda 3 kalem", 3, len(dc["kalemler"]))
es("modeller sirasiyla", ["iPhone 15", "iPhone 14 Pro", "Samsung S23"],
   [k["model"] for k in dc["kalemler"]])
es("adetler sirasiyla", [2, 1, 3], [k["adet"] for k in dc["kalemler"]])
# Her kalemin KENDI tasarimi olmali — hepsi ayni tasarima baglanirsa
# baski yanlis cikar
_kodlar = [db.scalar(select(LineItem.assigned_design_id).where(
    LineItem.id == uuid.UUID(k["id"]))) for k in dc["kalemler"]]
es("her kalemin ayri tasarimi", 3, len(set(_kodlar)))
es("listede toplam adet 6", 6,
   [x for x in ISTEMCI.get("/api/bayii/siparisler", headers=H_A).json()["items"]
    if x["id"] == cok_id][0]["adet"])

# Duzenleme SADECE hedeflenen kalemi degistirmeli
k2 = dc["kalemler"][1]["id"]
es("2. kalemin modeli degisir", 200, ISTEMCI.patch(
    f"/api/bayii/siparis/{cok_id}/kalem/{k2}", headers=H_A,
    json={"model": "IPHONE-16"}).status_code)
dc2 = ISTEMCI.get(f"/api/bayii/siparis/{cok_id}", headers=H_A).json()
es("sadece 2. kalem degisti", ["iPhone 15", "iPhone 16", "Samsung S23"],
   [k["model"] for k in dc2["kalemler"]])
es("adet degisir", 200, ISTEMCI.patch(
    f"/api/bayii/siparis/{cok_id}/kalem/{k2}", headers=H_A, json={"adet": 5}).status_code)
es("yeni adet yazildi", [2, 5, 3],
   [k["adet"] for k in ISTEMCI.get(f"/api/bayii/siparis/{cok_id}",
                                   headers=H_A).json()["kalemler"]])
es("baska siparisin kalemi reddedilir", 404, ISTEMCI.patch(
    f"/api/bayii/siparis/{cok_id}/kalem/{tr_kalem}", headers=H_A,
    json={"model": "X"}).status_code)

# 2. kalemin tasarimi degisince 1. ve 3. kalem ETKILENMEMELI
_onceki = [db.scalar(select(LineItem.assigned_design_id).where(
    LineItem.id == uuid.UUID(k["id"]))) for k in dc2["kalemler"]]
es("2. kalemin tasarimi degisir", 200, ISTEMCI.post(
    f"/api/bayii/siparis/{cok_id}/kalem/{k2}/tasarim", headers=H_A,
    files={"tasarim": ("yeni.jpg", jpg((5, 200, 90)), "image/jpeg")}).status_code)
db.expire_all()
_sonraki = [db.scalar(select(LineItem.assigned_design_id).where(
    LineItem.id == uuid.UUID(k["id"]))) for k in dc2["kalemler"]]
es("1. kalemin tasarimi ayni", _onceki[0], _sonraki[0])
es("2. kalemin tasarimi degisti", True, _onceki[1] != _sonraki[1])
es("3. kalemin tasarimi ayni", _onceki[2], _sonraki[2])

# AYNI dosya tekrar yuklenirse YENI kayit acilmamali (mukerrer dosya onlemi).
# Ayrintili sinama: scripts/tasarim_dedup_test.py
_ayni = jpg((5, 200, 90))
es("ayni gorsel tekrar yuklenir", 200, ISTEMCI.post(
    f"/api/bayii/siparis/{cok_id}/kalem/{k2}/tasarim", headers=H_A,
    files={"tasarim": ("tekrar.jpg", _ayni, "image/jpeg")}).status_code)
db.expire_all()
es("YENI tasarim kaydi ACILMADI", _sonraki[1], db.scalar(
    select(LineItem.assigned_design_id).where(LineItem.id == uuid.UUID(dc2["kalemler"][1]["id"]))))

# Sinirlar
es("kalem sayisi ustu 400", 400,
   siparis_ac(H_A, urunler=[("IPHONE-15", 1)] * 21).status_code)
es("bir kalemde adet 0 -> 400", 400,
   siparis_ac(H_A, urunler=[("IPHONE-15", 1), ("IPHONE-14", 0)]).status_code)
# Listeler kayarsa tasarim yanlis modele baglanir; sunucu reddetmeli
_kayik = ISTEMCI.post("/api/bayii/siparis", headers=H_A,
                      data={"kanal": "trendyol", "ad_soyad": "Kayik",
                            "model": ["IPHONE-15", "IPHONE-14"], "adet": ["1", "1"]},
                      files=[("tasarim", ("a.jpg", jpg(), "image/jpeg"))])
es("tasarim/model sayisi uyusmazsa 400", 400, _kayik.status_code)

# Onayda borc TOPLAM adet uzerinden
_kalemler = ISTEMCI.get(f"/api/bayii/siparis/{cok_id}", headers=H_A).json()["kalemler"]
db.expire_all(); db.refresh(bayi_a)
_onceki_bakiye = float(bayi_a.balance or 0)
ro = ISTEMCI.post(f"/api/dealers/portal/onay-bekleyen/{cok_id}", headers=H_ADMIN,
                  json={"varyasyonlar": {k["id"]: "beyaz" for k in _kalemler},
                        "apply_shipping": False})
es("coklu siparis onaylandi", 200, ro.status_code)
# 2 + 5 + 3 = 10 adet x 100 birim fiyat
es("borc 10 adet uzerinden", 1000.0, ro.json()["urun"])
es("kargo yansitilmadi", 0.0, ro.json()["kargo"])
db.expire_all(); db.refresh(bayi_a)
es("bakiye dogru arttı", _onceki_bakiye + 1000.0, float(bayi_a.balance or 0))

print("\n── 12. Yonetim uclari bayiye KAPALI ──")
# Bayi yonetimle AYNI tenant icinde. Izin adini ayirmak yetmiyordu: izin
# ISTEMEYEN uclar (get_current_user'a takilan her sey) bayiye aciktı.
# Kapi get_current_user'in icinde (_bayi_kapisi) — yarin eklenen uc de kapali.
SIZAN = [
    "/api/notifications",     # tum yonetim bildirimleri
    "/api/search",            # tum siparis/tasarim/musteri aramasi
    "/api/stores",            # diger bayilerin magazalari + entegrasyon
    "/api/dashboard/summary", # ciro/siparis istatistikleri
    "/api/dashboard/worklist",
    "/api/orders",
    "/api/dealers",
    "/api/designs",
]
for yol in SIZAN:
    es(f"kapali: {yol}", 403, ISTEMCI.get(yol, headers=H_A).status_code)

# Kapi portali ve oturum uclarini ENGELLEMEMELI
es("portal acik", 200, ISTEMCI.get("/api/bayii/ozet", headers=H_A).status_code)
es("kendi profili acik", 200, ISTEMCI.get("/api/auth/me", headers=H_A).status_code)

# ── /api/auth/ VARSAYILAN RED ──
# Eskiden "/api/auth/" önekle bayiye tümüyle açıktı; yalnız iki uç yasaklıydı.
# /api/auth altına yarın eklenen herhangi bir personel ucu bayiye OTOMATİK
# açılacaktı. Artık bayinin kullandığı uçlar tek tek açık, gerisi kapalı.
#
# Bu tablo BİLEREK elle yazılı: token isteyen yeni bir /api/auth ucu eklenince
# aşağıdaki sınama "sınıflandırılmamış" diye DÜŞER — kimse karar vermeden
# bayiye açık mı kapalı mı olduğu belirsiz kalamaz.
_AUTH_SINIF = {
    ("GET", "/api/auth/me"): "acik",
    ("PATCH", "/api/auth/me"): "acik",
    ("POST", "/api/auth/verify-password"): "acik",
    ("POST", "/api/auth/change-password"): "acik",
    ("POST", "/api/auth/refresh"): "acik",
    ("POST", "/api/auth/2fa/setup"): "kapali",
    ("POST", "/api/auth/2fa/enable"): "kapali",
    ("POST", "/api/auth/2fa/disable"): "kapali",
    ("GET", "/api/auth/profiles"): "kapali",
    ("POST", "/api/auth/select-profile"): "kapali",
    ("GET", "/api/auth/passkey"): "acik",    # kendi anahtarlarini listeler
    ("GET", "/api/auth/passkey/only"): "kapali",
    ("POST", "/api/auth/passkey/only"): "kapali",   # cihaz kaybinda kilitlenme riski
    ("POST", "/api/auth/passkey/register/begin"): "acik",   # kendi gecis anahtarini kaydeder
    ("POST", "/api/auth/passkey/register/finish"): "acik",
    ("DELETE", "/api/auth/passkey/{cred_id}"): "acik",   # kendi anahtarini siler
}
from app.auth.dependencies import get_current_user as _gcu  # noqa: E402
from app.main import app as _app  # noqa: E402


def _bagimliliklar(d, acc):
    for x in d.dependencies:
        acc.add(x.call)
        _bagimliliklar(x, acc)
    return acc


_token_uclari = []
for _r in _app.routes:
    _p = getattr(_r, "path", "")
    if _p.startswith("/api/auth") and _gcu in _bagimliliklar(_r.dependant, set()):
        for _m in sorted(_r.methods or []):
            _token_uclari.append((_m, _p))
_sinifsiz = [u for u in _token_uclari if u not in _AUTH_SINIF]
es("token isteyen HER /api/auth ucu sınıflandırılmış", [], _sinifsiz)
for (_m, _p), _sinif in _AUTH_SINIF.items():
    _yol = _p.replace("{cred_id}", "00000000-0000-0000-0000-000000000000")
    _kod = ISTEMCI.request(_m, _yol, headers=H_A, json={}).status_code
    if _sinif == "kapali":
        es(f"bayiye kapali: {_m} {_p}", 403, _kod)
    else:
        # Açık uçta boş gövde 422 ya da iş hatası dönebilir; önemli olan KAPIYA takılmaması.
        es(f"bayiye acik: {_m} {_p}", True, _kod != 403)
# Yonetici ayni uclarda serbest kalmali
es("yonetici /api/dealers 200", 200, ISTEMCI.get("/api/dealers", headers=H_ADMIN).status_code)
es("yonetici /api/notifications 200", 200,
   ISTEMCI.get("/api/notifications", headers=H_ADMIN).status_code)

# PROFIL DEGISTIRME: bayi buradan personel token'i alamamali.
# (PIN'siz personel profili ayni tenant'taki her token'la secilebiliyordu.)
es("bayi profil listesini goremez", 403,
   ISTEMCI.get("/api/auth/profiles", headers=H_A).status_code)
es("bayi profil degistiremez", 403,
   ISTEMCI.post("/api/auth/select-profile", headers=H_A,
                json={"user_id": str(admin.id)}).status_code)
es("yonetici profil listesini gorur", 200,
   ISTEMCI.get("/api/auth/profiles", headers=H_ADMIN).status_code)
es("profil listesinde bayi YOK", [],
   [p for p in ISTEMCI.get("/api/auth/profiles", headers=H_ADMIN).json()
    if p["full_name"].startswith("Bayi ")])
es("yonetici bayi profiline gecemez", 404,
   ISTEMCI.post("/api/auth/select-profile", headers=H_ADMIN,
                json={"user_id": str(kul_a.id)}).status_code)

# Bayiye giden push, yonetim bildirimlerini ALMAMALI
from app.services import push as _push  # noqa: E402
from app.models import PushSubscription as _PS  # noqa: E402
db.add(_PS(tenant_id=tenant.id, user_id=kul_a.id, endpoint=f"https://ornek/{IZ}",
           p256dh="x", auth="y"))
db.commit()
_secilen = db.scalars(select(_PS).where(
    _PS.tenant_id == tenant.id,
    _PS.user_id.notin_(select(User.id).where(User.dealer_id.isnot(None))))).all()
es("tenant push'unda bayi cihazi yok", False,
   any(x.user_id == kul_a.id for x in _secilen))
db.execute(text("delete from push_subscriptions where endpoint like :p")
           .bindparams(p=f"https://ornek/{IZ}"))
db.commit()

print("\n── 13b. Model dogrulama ──")
# "Model taninmadi": bayi listeden secse bile marka oneki dusen bir ad
# (or. "A57") kalip planlayicisi tarafindan cozulemiyor ve siparis sessizce
# kalip disinda kaliyordu. Artik hem liste hem de kapi suzuyor.
_ml = ISTEMCI.get("/api/bayii/modeller", headers=H_A).json()["items"]
es("modeller {deger, etiket} doner", True,
   bool(_ml) and set(_ml[0]) == {"deger", "etiket"})
from app.services import phone_models as _pm  # noqa: E402
es("listedeki her model COZULEBILIR", True,
   all(_pm.has_spec(db, tenant.id, m["deger"]) for m in _ml))
es("taninmayan model reddedilir", 400,
   siparis_ac(H_A, urunler=[("A57", 1)]).status_code)
_taze = siparis_ac(H_A, urunler=[(_ml[0]["deger"], 1)]).json()["id"]
_taze_k = ISTEMCI.get(f"/api/bayii/siparis/{_taze}", headers=H_A).json()["kalemler"][0]["id"]
es("taninmayan modele guncelleme reddedilir", 400,
   ISTEMCI.patch(f"/api/bayii/siparis/{_taze}/kalem/{_taze_k}", headers=H_A,
                 json={"model": "ZZZ-YOK-99"}).status_code)
es("taninan modele guncelleme gecer", 200,
   ISTEMCI.patch(f"/api/bayii/siparis/{_taze}/kalem/{_taze_k}", headers=H_A,
                 json={"model": _ml[1]["deger"]}).status_code)
es("taninan model kabul edilir", 201,
   siparis_ac(H_A, urunler=[(_ml[0]["deger"], 1)]).status_code)

print("\n── 14. Iptal talebi: kalip asamasina gore ──")
from app.models import Mold, MoldItem  # noqa: E402


def _kalipli_siparis(kalip_asamasi):
    """Onaylanmis siparis + verilen asamada bir kalip. (order_id, mold_id)."""
    r = siparis_ac(H_A, urunler=[("IPHONE-15", 1)], kanal="trendyol",
                   ad_soyad=f"Kalip {kalip_asamasi}")
    oid = r.json()["id"]
    kid = ISTEMCI.get(f"/api/bayii/siparis/{oid}", headers=H_A).json()["kalemler"][0]["id"]
    ISTEMCI.post(f"/api/dealers/portal/onay-bekleyen/{oid}", headers=H_ADMIN,
                 json={"varyasyonlar": {kid: "siyah"}, "apply_shipping": False})
    o = db.scalar(select(Order).where(Order.id == uuid.UUID(oid)))
    li = db.scalar(select(LineItem).where(LineItem.order_id == o.id))
    li.is_kaliba_eklendi = True
    m = Mold(tenant_id=tenant.id, store_id=bayi_a.store_id,
             kod=f"{IZ}-K{kalip_asamasi}", variation="SİYAH",
             kilif_sayisi=1, rows_used=1, current_stage=kalip_asamasi)
    db.add(m); db.flush()
    db.add(MoldItem(tenant_id=tenant.id, mold_id=m.id, store_id=bayi_a.store_id,
                    line_item_id=li.id, design_id=li.assigned_design_id,
                    slot_index=0, kalip_kodu="A1", model="IPHONE-15",
                    order_number=str(o.order_number)))
    db.commit()
    return oid, m.id


def _bakiye():
    db.expire_all(); db.refresh(bayi_a)
    return float(bayi_a.balance or 0)


# --- B) Kalip "hazir" (asama 2): talep acilir, kalip silinir, IADE edilir ---
oid, mid = _kalipli_siparis(2)
d = ISTEMCI.get(f"/api/bayii/siparis/{oid}", headers=H_A).json()["yetkiler"]
es("hazir kalip: dogrudan geri cekilemez", False, d["silinebilir"])
es("hazir kalip: talep acilabilir", True, d["iptal_talebi_acilir"])
es("dogrudan silme 409", 409,
   ISTEMCI.delete(f"/api/bayii/siparis/{oid}", headers=H_A).status_code)
es("talep acilir", 200, ISTEMCI.post(f"/api/bayii/siparis/{oid}/iptal-talebi",
   headers=H_A, json={"sebep": "musteri vazgecti"}).status_code)
es("ayni talep tekrar acilamaz", 409,
   ISTEMCI.post(f"/api/bayii/siparis/{oid}/iptal-talebi", headers=H_A, json={}).status_code)
_kuyruk = ISTEMCI.get("/api/dealers/portal/iptal-talepleri", headers=H_ADMIN).json()
_bu = [x for x in _kuyruk if x["id"] == oid][0]
es("kuyrukta sebep gorunur", "musteri vazgecti", _bu["sebep"])
es("onizleme: iade edilir", True, _bu["sonuc"]["iade_edilir"])
es("onizleme: kalip silinir", True, _bu["sonuc"]["kaliplar_silinir"])
_once = _bakiye()
_r = ISTEMCI.post(f"/api/dealers/portal/iptal-talepleri/{oid}", headers=H_ADMIN)
es("onay 200", 200, _r.status_code)
es("iade edildi", True, _r.json()["iade_edildi"])
es("bakiye 100 dustu", _once - 100.0, _bakiye())
es("kalip SILINDI", None, db.scalar(select(Mold).where(Mold.id == mid)))
_od = ISTEMCI.get(f"/api/bayii/siparis/{oid}", headers=H_A).json()
es("siparis iptal edildi", True, _od["iptal"])
es("kalip bayragi sifirlandi", False,
   db.scalar(select(LineItem.is_kaliba_eklendi).where(
       LineItem.order_id == uuid.UUID(oid))))

# --- AYNI KALIPTA BASKA SIPARIS: iptalde o da plana GERI DONMELI ---
# Ham db.delete(mold) kullanilirsa digerlerinin is_kaliba_eklendi bayragi True
# kalir, MoldItem'lari gider ve mold_planner onlari bir daha ALMAZ — sessizce
# uretim disinda kalirlar.
r_a = siparis_ac(H_A, urunler=[("IPHONE-15", 1)], kanal="trendyol", ad_soyad="Kurban A")
r_b = siparis_ac(H_A, urunler=[("IPHONE-15", 1)], kanal="trendyol", ad_soyad="Kurban B")
oid_a, oid_b = r_a.json()["id"], r_b.json()["id"]
for _o in (oid_a, oid_b):
    _k = ISTEMCI.get(f"/api/bayii/siparis/{_o}", headers=H_A).json()["kalemler"][0]["id"]
    ISTEMCI.post(f"/api/dealers/portal/onay-bekleyen/{_o}", headers=H_ADMIN,
                 json={"varyasyonlar": {_k: "siyah"}, "apply_shipping": False})
_ort = Mold(tenant_id=tenant.id, store_id=bayi_a.store_id, kod=f"{IZ}-ORTAK",
            variation="SİYAH", kilif_sayisi=2, rows_used=1, current_stage=2)
db.add(_ort); db.flush()
_ort_id = _ort.id   # silindikten sonra _ort.id okunamaz (ObjectDeletedError)
_liler = {}
for _i, _o in enumerate((oid_a, oid_b)):
    _oo = db.scalar(select(Order).where(Order.id == uuid.UUID(_o)))
    _li = db.scalar(select(LineItem).where(LineItem.order_id == _oo.id))
    _li.is_kaliba_eklendi = True
    _liler[_o] = _li.id
    db.add(MoldItem(tenant_id=tenant.id, mold_id=_ort_id, store_id=bayi_a.store_id,
                    line_item_id=_li.id, design_id=_li.assigned_design_id,
                    slot_index=_i, kalip_kodu="A1", model="IPHONE-15",
                    order_number=str(_oo.order_number)))
db.commit()

ISTEMCI.post(f"/api/bayii/siparis/{oid_a}/iptal-talebi", headers=H_A, json={})
es("ortak kalip: iptal onaylandi", 200,
   ISTEMCI.post(f"/api/dealers/portal/iptal-talepleri/{oid_a}", headers=H_ADMIN).status_code)
db.expire_all()
es("ortak kalip silindi", None, db.scalar(select(Mold).where(Mold.id == _ort_id)))
es("iptal edilenin bayragi dustu", False,
   db.scalar(select(LineItem.is_kaliba_eklendi).where(LineItem.id == _liler[oid_a])))
# ASIL SINAMA: masum siparis plana geri donmeli
es("DIGER siparisin bayragi da dustu", False,
   db.scalar(select(LineItem.is_kaliba_eklendi).where(LineItem.id == _liler[oid_b])))
es("diger siparis iptal EDILMEDI", False,
   ISTEMCI.get(f"/api/bayii/siparis/{oid_b}", headers=H_A).json()["iptal"])
es("diger siparis kalip planinda", True, _planda_var(
    db.scalar(select(Order.order_number).where(Order.id == uuid.UUID(oid_b)))))

# --- Ayni akis "baskiya gonderildi" (3) ve "baskida" (4) icin de ---
for _as in (3, 4):
    oid2, mid2 = _kalipli_siparis(_as)
    es(f"asama {_as}: talep acilabilir", True,
       ISTEMCI.get(f"/api/bayii/siparis/{oid2}", headers=H_A)
       .json()["yetkiler"]["iptal_talebi_acilir"])
    ISTEMCI.post(f"/api/bayii/siparis/{oid2}/iptal-talebi", headers=H_A, json={})
    _o = _bakiye()
    _rr = ISTEMCI.post(f"/api/dealers/portal/iptal-talepleri/{oid2}", headers=H_ADMIN)
    es(f"asama {_as}: iade edildi", True, _rr.json()["iade_edildi"])
    es(f"asama {_as}: bakiye dustu", _o - 100.0, _bakiye())
    es(f"asama {_as}: kalip silindi", None, db.scalar(select(Mold).where(Mold.id == mid2)))

# --- C) Kalip TAMAMLANDI (5): talep ACILAMAZ ---
oid3, mid3 = _kalipli_siparis(5)
d3 = ISTEMCI.get(f"/api/bayii/siparis/{oid3}", headers=H_A).json()["yetkiler"]
es("tamamlanmis kalip: talep ACILAMAZ", False, d3["iptal_talebi_acilir"])
es("tamamlanmis kalip: kalip_basildi", True, d3["kalip_basildi"])
es("talep denemesi 409", 409,
   ISTEMCI.post(f"/api/bayii/siparis/{oid3}/iptal-talebi", headers=H_A, json={}).status_code)

# --- Yaris: talep acikken kalip tamamlandi -> IADE YOK, kalip SILINMEZ ---
oid4, mid4 = _kalipli_siparis(3)
ISTEMCI.post(f"/api/bayii/siparis/{oid4}/iptal-talebi", headers=H_A, json={})
db.scalar(select(Mold).where(Mold.id == mid4)).current_stage = 5   # arada tamamlandi
db.commit()
_o4 = _bakiye()
_r4 = ISTEMCI.post(f"/api/dealers/portal/iptal-talepleri/{oid4}", headers=H_ADMIN)
es("yaris: iade EDILMEDI", False, _r4.json()["iade_edildi"])
es("yaris: bakiye degismedi", _o4, _bakiye())
es("yaris: kalip SILINMEDI", True,
   db.scalar(select(Mold).where(Mold.id == mid4)) is not None)
es("yaris: siparis yine iptal", True,
   ISTEMCI.get(f"/api/bayii/siparis/{oid4}", headers=H_A).json()["iptal"])

# --- Talep reddi ---
oid5, mid5 = _kalipli_siparis(2)
ISTEMCI.post(f"/api/bayii/siparis/{oid5}/iptal-talebi", headers=H_A, json={})
_o5 = _bakiye()
es("talep reddedilir", 200,
   ISTEMCI.delete(f"/api/dealers/portal/iptal-talepleri/{oid5}", headers=H_ADMIN).status_code)
es("red: bakiye degismedi", _o5, _bakiye())
es("red: kalip duruyor", True, db.scalar(select(Mold).where(Mold.id == mid5)) is not None)
es("red: siparis iptal DEGIL", False,
   ISTEMCI.get(f"/api/bayii/siparis/{oid5}", headers=H_A).json()["iptal"])
es("red sonrasi yeniden talep acilir", 200,
   ISTEMCI.post(f"/api/bayii/siparis/{oid5}/iptal-talebi", headers=H_A, json={}).status_code)
es("bayi kendi talebini geri alir", 200,
   ISTEMCI.delete(f"/api/bayii/siparis/{oid5}/iptal-talebi", headers=H_A).status_code)

# --- Iptal edilen siparis kalip planina ve paketlemeye GIRMEZ ---
from app.services.order_scope import acik_siparis_filtresi  # noqa: E402
_acik = {str(x) for x in db.scalars(
    select(Order.id).where(acik_siparis_filtresi(tenant.id))).all()}
es("iptal edilen ACIK siparis degil", False, oid in _acik)
es("iptal edilen plana girmez", False, _planda_var(
    db.scalar(select(Order.order_number).where(Order.id == uuid.UUID(oid)))))

print("\n── 15. Tasarim katalogu ──")
_kat = ISTEMCI.get("/api/bayii/tasarimlar", headers=H_A).json()["items"]
es("bayinin tasarimlari listelenir", True, len(_kat) > 0)
es("hepsi bayinin magazasindan", True, all(
    db.scalar(select(Design.store_id).where(Design.id == uuid.UUID(x["id"])))
    == bayi_a.store_id for x in _kat[:5]))
es("B bayisi A'nin tasarimlarini goremez", True,
   all(x["id"] not in {y["id"] for y in _kat}
       for x in ISTEMCI.get("/api/bayii/tasarimlar", headers=H_B).json()["items"]))
# Katalogdan siparis: dosya YUKLEMEDEN
_secilen = _kat[0]["id"]
_rk = ISTEMCI.post("/api/bayii/siparis", headers=H_A,
                   data={"kanal": "trendyol", "ad_soyad": "Katalogdan",
                         "model": "IPHONE-15", "adet": "1", "tasarim_id": _secilen})
es("katalogdan siparis 201", 201, _rk.status_code)
_kd = ISTEMCI.get(f"/api/bayii/siparis/{_rk.json()['id']}", headers=H_A).json()
es("secilen tasarim baglandi", _secilen, str(db.scalar(
    select(LineItem.assigned_design_id).where(
        LineItem.id == uuid.UUID(_kd["kalemler"][0]["id"])))))
# Karisik: biri katalogdan, biri yeni dosya
_rm = ISTEMCI.post("/api/bayii/siparis", headers=H_A,
                   data={"kanal": "trendyol", "ad_soyad": "Karisik",
                         "model": ["IPHONE-15", "IPHONE-14"], "adet": ["1", "1"],
                         "tasarim_id": [_secilen, ""]},
                   files=[("tasarim", ("yeni.jpg", jpg(), "image/jpeg"))])
es("karisik siparis 201", 201, _rm.status_code)
es("karisik: 2 kalem", 2, _rm.json().get("kalem_sayisi"))
# B bayisi A'nin tasarimini SECEMEZ
_rx = ISTEMCI.post("/api/bayii/siparis", headers=H_B,
                   data={"kanal": "trendyol", "ad_soyad": "Hirsiz",
                         "model": "IPHONE-15", "adet": "1", "tasarim_id": _secilen})
es("baska bayinin tasarimi secilemez", 404, _rx.status_code)

print("\n── Güncelleme notları ──")
_d0 = ISTEMCI.get("/api/bayii/guncellemeler/durum", headers=H_A)
es("durum: yeni hesap hiç görmedi (null)", (200, None), (_d0.status_code, _d0.json().get("goruldu")))
es("görüldü 6", 6, ISTEMCI.post("/api/bayii/guncellemeler/goruldu", headers=H_A,
                               json={"surum": 6}).json().get("goruldu"))
es("geri sürüm gönderilirse GERİLEMEZ", 6, ISTEMCI.post(
    "/api/bayii/guncellemeler/goruldu", headers=H_A, json={"surum": 2}).json().get("goruldu"))
es("B bayisini etkilemez", None,
   ISTEMCI.get("/api/bayii/guncellemeler/durum", headers=H_B).json().get("goruldu"))
es("bayi olmayan 403", 403,
   ISTEMCI.get("/api/bayii/guncellemeler/durum", headers=H_YABANCI).status_code)
es("negatif sürüm 422", 422, ISTEMCI.post("/api/bayii/guncellemeler/goruldu", headers=H_A,
                                         json={"surum": -1}).status_code)

# ─── Temizlik ───────────────────────────────────────────────
print("\n── Temizlik ──")
ids = [d.id for d in db.scalars(select(Dealer).where(Dealer.name.like(f"{IZ}%"))).all()]
oids = [o.id for o in db.scalars(select(Order).where(
    Order.store_id.in_(select(Store.id).where(Store.slug.like(f"{IZ}%"))))).all()]
for t in ("order_status_history", "mold_items", "line_items"):
    if oids:
        db.execute(text(f"delete from {t} where order_id = any(:o)"
                        if t != "mold_items" else
                        "delete from mold_items where line_item_id in "
                        "(select id from line_items where order_id = any(:o))")
                   .bindparams(o=oids))
if oids:
    db.execute(text("delete from line_items where order_id = any(:o)").bindparams(o=oids))
    db.execute(text("delete from orders where id = any(:o)").bindparams(o=oids))
db.execute(text("delete from mold_items where mold_id in "
                "(select id from molds where kod like :p)").bindparams(p=f"{IZ}%"))
db.execute(text("delete from molds where kod like :p").bindparams(p=f"{IZ}%"))
db.execute(text("delete from dealer_transactions where dealer_id = any(:d)").bindparams(d=ids))
db.execute(text("delete from designs where store_id in "
                "(select id from stores where slug like :p)").bindparams(p=f"{IZ}%"))
db.execute(text("delete from users where email like :p").bindparams(p=f"{IZ}%"))
db.execute(text("delete from dealers where id = any(:d)").bindparams(d=ids))
db.execute(text("delete from stores where slug like :p").bindparams(p=f"{IZ}%"))
db.commit()
print("  temizlendi")

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
