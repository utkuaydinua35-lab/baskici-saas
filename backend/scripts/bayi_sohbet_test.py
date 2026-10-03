"""Bayi ↔ atölye sohbeti — iki uç, tek kural.

Sınananlar:
  • bayi yazar; mesaj yönetim tarafında görünür, okunmamış sayacı artar
  • görsel ve SİPARİŞ EKİ taşınır; başka bayinin siparişi eklenemez
  • ACİLİYET kaydedilir, listede acil olan bayi en üste çıkar, yöneticiye
    bildirim düşer
  • atölye yazar; bayinin okunmamışı artar, bayi okuyunca sıfırlanır
  • okundu işareti yalnız KARŞI tarafın mesajlarını kapatır
  • boş mesaj reddedilir
  • bayi BAŞKA bayinin sohbetini göremez; yönetim ucu bayiye kapalı
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token, hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (BayiSohbet, Dealer, LineItem, Notification, Order,  # noqa: E402
                        OrderStatusHistory, Store, Tenant, User)

GECTI = KALDI = 0
IZ = f"bstest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
admin = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                     User.role.in_(["owner", "yonetici"])).limit(1))
c = TestClient(app)


def basl(u):
    return {"Authorization": "Bearer " + create_access_token(
        user_id=str(u.id), tenant_id=str(u.tenant_id), email=u.email, expires_minutes=30)}


def bayi_kur(ad):
    st = Store(tenant_id=tenant.id, slug=f"{IZ}-{ad}", name=f"Bayi {ad}",
               platform="bayii", is_active=True)
    db.add(st); db.flush()
    d = Dealer(tenant_id=tenant.id, name=f"{IZ}-{ad}", store_id=st.id, unit_price=100,
               shipping_fee=0, currency="TRY", is_active=True, balance=0, balance_usd=0)
    db.add(d); db.flush()
    u = User(tenant_id=tenant.id, email=f"{IZ}.{ad}@ornek.test",
             password_hash=hash_password("Portal12345!"), full_name=f"Bayi {ad}",
             role="bayii_portal", permissions=["bayii_portal"], dealer_id=d.id, is_active=True)
    db.add(u); db.flush()
    return d, u


def siparis(d, no):
    o = Order(tenant_id=tenant.id, store_id=d.store_id, external_id=f"{IZ}-{no}",
              order_number=f"{IZ}{no}", customer_name="Ayşe", current_stage=2,
              created_at_platform=datetime.now(UTC), raw={"dealer_id": str(d.id)})
    db.add(o); db.flush()
    db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="Kılıf", quantity=1,
                    product_id=f"{IZ}-p", properties=[]))
    db.flush()
    return o


try:
    bayi_a, kul_a = bayi_kur("a")
    bayi_b, kul_b = bayi_kur("b")
    sip_a = siparis(bayi_a, 1)
    sip_b = siparis(bayi_b, 2)
    db.commit()
    HA, HB, HY = basl(kul_a), basl(kul_b), basl(admin)

    print("\n── Bayi yazıyor ──")
    r = c.post("/api/bayii/sohbet", headers=HA, json={"body": "Merhaba, bir sorum var"})
    es("mesaj kaydedildi", (200, "bayi"), (r.status_code, r.json().get("gonderen")))
    es("yazan kişi kayıtlı", "Bayi a", r.json().get("gonderen_ad"))
    r = c.get("/api/bayi-sohbet", headers=HY)
    satir = next(x for x in r.json()["items"] if x["dealer_id"] == str(bayi_a.id))
    es("yönetim listesinde okunmamış 1", 1, satir["okunmamis_atolye"])
    es("son mesaj özeti", "Merhaba, bir sorum var", satir["son_mesaj_ozet"])
    es("toplam okunmamış", 1, r.json()["okunmamis_toplam"])

    print("\n── Görsel + sipariş eki + aciliyet ──")
    r = c.post("/api/bayii/sohbet", headers=HA, json={
        "body": "Bu siparişte sorun var", "image_url": "https://ornek/foto.jpg",
        "order_id": str(sip_a.id), "aciliyet": "cok_acil"})
    es("ek bilgiler taşınır", (200, str(sip_a.id), f"{IZ}1", "cok_acil", "https://ornek/foto.jpg"),
       (r.status_code, r.json()["order_id"], r.json()["order_no"],
        r.json()["aciliyet"], r.json()["image_url"]))
    es("BAŞKA bayinin siparişi eklenemez", 404,
       c.post("/api/bayii/sohbet", headers=HA,
              json={"body": "x", "order_id": str(sip_b.id)}).status_code)
    es("geçersiz aciliyet normale düşer", "normal",
       c.post("/api/bayii/sohbet", headers=HA,
              json={"body": "y", "aciliyet": "felaket"}).json()["aciliyet"])
    es("boş mesaj reddedilir", 400,
       c.post("/api/bayii/sohbet", headers=HA, json={"body": "   "}).status_code)

    print("\n── Acil olan üstte + bildirim ──")
    c.post("/api/bayii/sohbet", headers=HB, json={"body": "normal mesaj"})
    liste = c.get("/api/bayi-sohbet", headers=HY).json()
    es("acil bayi listenin EN ÜSTÜNDE", str(bayi_a.id), liste["items"][0]["dealer_id"])
    es("acil işareti", True, liste["items"][0]["acil_bekliyor"])
    es("acil sayısı", 1, liste["acil_sayisi"])
    bildirimler = db.scalars(select(Notification).where(
        Notification.tenant_id == tenant.id,
        Notification.link.like(f"/bayi-sohbet?bayi={bayi_a.id}"))).all()
    es("yöneticiye bildirim düştü", True, len(bildirimler) >= 1)
    es("acil bildirimi uyarı türünde", True, any(b.kind == "warn" for b in bildirimler))

    print("\n── Yönetim okuyor ve yanıtlıyor ──")
    r = c.post(f"/api/bayi-sohbet/{bayi_a.id}/okundu", headers=HY)
    es("okundu işaretlendi (3 bayi mesajı)", 3, r.json()["okundu"])
    satir = next(x for x in c.get("/api/bayi-sohbet", headers=HY).json()["items"]
                 if x["dealer_id"] == str(bayi_a.id))
    es("okunmamış sıfırlandı", 0, satir["okunmamis_atolye"])
    es("acil işareti kalktı", False, satir["acil_bekliyor"])

    r = c.post(f"/api/bayi-sohbet/{bayi_a.id}", headers=HY,
               json={"body": "Bakıyoruz, hallediyoruz", "order_id": str(sip_a.id)})
    es("atölye yazdı", (200, "atolye"), (r.status_code, r.json()["gonderen"]))
    d = c.get("/api/bayii/sohbet", headers=HA).json()
    es("bayide okunmamış 1", 1, d["sohbet"]["okunmamis_bayi"])
    es("bayi tüm konuşmayı görüyor (3 kendi + 1 atölye)", 4, len(d["mesajlar"]))
    es("son mesaj atölyeden", "atolye", d["mesajlar"][-1]["gonderen"])
    r = c.post("/api/bayii/sohbet/okundu", headers=HA)
    es("bayi okudu", 1, r.json()["okundu"])
    es("bayi okunmamışı sıfır", 0,
       c.get("/api/bayii/sohbet", headers=HA).json()["sohbet"]["okunmamis_bayi"])
    es("yönetim tarafı etkilenmedi (kendi mesajı okunmamış sayılmaz)", 0,
       next(x for x in c.get("/api/bayi-sohbet", headers=HY).json()["items"]
            if x["dealer_id"] == str(bayi_a.id))["okunmamis_atolye"])

    print("\n── Logo, tik durumu ve sipariş arama ──")
    # Bayi logosu: yükle → sohbette avatar olarak görünür → kaldırılabilir
    import io
    from PIL import Image
    tampon = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 40, 200)).save(tampon, "PNG")
    r = c.post("/api/bayii/logo", headers=HA,
               files={"file": ("logo.png", tampon.getvalue(), "image/png")})
    es("logo yüklendi", 200, r.status_code)
    logo = r.json()["logo_url"]
    es("logo /storage altında", True, logo.startswith("/storage/"))
    d = c.get("/api/bayii/sohbet", headers=HA).json()
    es("mesajın yanında bayi logosu", logo,
       next(m["avatar"] for m in d["mesajlar"] if m["gonderen"] == "bayi"))
    es("yönetim listesinde de logo", logo,
       next(x["logo_url"] for x in c.get("/api/bayi-sohbet", headers=HY).json()["items"]
            if x["dealer_id"] == str(bayi_a.id)))
    # İletildi / görüldü
    r = c.post("/api/bayii/sohbet", headers=HA, json={"body": "tik sınaması"})
    es("yeni mesaj: iletildi", "iletildi", r.json()["durum"])
    c.post(f"/api/bayi-sohbet/{bayi_a.id}/okundu", headers=HY)
    d = c.get("/api/bayii/sohbet", headers=HA).json()
    es("yönetim okuyunca: görüldü", "goruldu",
       next(m["durum"] for m in d["mesajlar"] if m["body"] == "tik sınaması"))
    # Yönetim tarafı sipariş arama listesi
    r = c.get(f"/api/bayi-sohbet/{bayi_a.id}/siparisler", headers=HY)
    kalem = next(x for x in r.json()["items"] if x["id"] == str(sip_a.id))
    es("sipariş listesi müşteri adı ve tarih taşır", ("Ayşe", True),
       (kalem["musteri"], bool(kalem["tarih"])))
    es("aşama adı yazılı", True, bool(kalem["asama_adi"]))
    es("başka bayinin siparişi listede yok", 0,
       len([x for x in r.json()["items"] if x["id"] == str(sip_b.id)]))
    es("logo kaldırılabilir", (200, None),
       (c.delete("/api/bayii/logo", headers=HA).status_code,
        c.get("/api/bayii/sohbet", headers=HA).json()["sohbet"]["logo_url"]))

    print("\n── Masaüstü uygulamasının olay akışı ──")
    r = c.get("/api/bayii/bildirimler", headers=HA)
    es("ilk açılış: olay YOK, yalnız sunucu saati", (200, []),
       (r.status_code, r.json()["olaylar"]))
    t0 = r.json()["sunucu_saati"]
    es("sunucu saati dönüyor", True, bool(t0))
    # İmleç biraz geriden verilir: uçuştaki işlemin olayı kaçmasın
    es("imleç şimdiden GERİDE (yarış koruması)", True,
       datetime.fromisoformat(t0) < datetime.now(UTC))
    # Atölye yazınca sohbet olayı düşer
    c.post(f"/api/bayi-sohbet/{bayi_a.id}", headers=HY, json={"body": "Masaüstü testi"})
    olaylar = c.get("/api/bayii/bildirimler", headers=HA, params={"since": t0}).json()["olaylar"]
    es("sohbet olayı geldi", True, any(o["tur"] == "sohbet" for o in olaylar))
    es("olay metni mesajı taşıyor", True,
       any("Masaüstü testi" in (o["govde"] or "") for o in olaylar))
    es("olayın açacağı sayfa", "/bayii/sohbet",
       next(o["link"] for o in olaylar if o["tur"] == "sohbet"))
    # Kargoya verilen sipariş olayı
    db.add(OrderStatusHistory(tenant_id=tenant.id, order_id=sip_a.id, from_stage=7, to_stage=8,
                              action="kargoya_verildi", note="test", created_by="test"))
    sip_a.kargo_info = {"takip_no": "TEST123"}
    db.commit()
    olaylar = c.get("/api/bayii/bildirimler", headers=HA, params={"since": t0}).json()["olaylar"]
    kargo = [o for o in olaylar if o["tur"] == "kargo"]
    es("kargo olayı geldi", 1, len(kargo))
    es("takip no bildirimde", True, "TEST123" in kargo[0]["govde"])
    es("kargo olayı sipariş sayfasına gider", f"/bayii/siparis/{sip_a.id}", kargo[0]["link"])
    es("BAŞKA bayinin kargosu düşmez", 0,
       len([o for o in c.get(f"/api/bayii/bildirimler?since={t0}", headers=HB).json()["olaylar"]
            if o["tur"] == "kargo"]))
    es("bozuk zaman reddedilir", 400,
       c.get("/api/bayii/bildirimler?since=dun", headers=HA).status_code)
    es("kodlanmamış +00:00 de kabul edilir (boşluğa dönüşen offset)", 200,
       c.get(f"/api/bayii/bildirimler?since={t0}", headers=HA).status_code)
    es("olaylar eskiden yeniye sıralı", True,
       all(olaylar[i]["at"] <= olaylar[i + 1]["at"] for i in range(len(olaylar) - 1)))

    print("\n── Ayrışma ──")
    es("bayi A, B'nin sohbetini görmez", 0,
       len([m for m in c.get("/api/bayii/sohbet", headers=HA).json()["mesajlar"]
            if m["body"] == "normal mesaj"]))
    es("bayi yönetim ucuna giremez", 403,
       c.get("/api/bayi-sohbet", headers=HA).status_code)
    es("bayi başka bayinin sohbetini yönetim ucundan okuyamaz", 403,
       c.get(f"/api/bayi-sohbet/{bayi_b.id}", headers=HA).status_code)
finally:
    db.rollback()
    ids = [x for (x,) in db.execute(select(Dealer.id).where(Dealer.name.like(f"{IZ}%"))).all()]
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.external_id.like(f"{IZ}%"))).all()]
    if ids:
        db.execute(text("delete from bayi_sohbet_mesajlari where sohbet_id in "
                        "(select id from bayi_sohbetleri where dealer_id = any(:d))").bindparams(d=ids))
        db.execute(text("delete from bayi_sohbetleri where dealer_id = any(:d)").bindparams(d=ids))
    if oids:
        for q in ("delete from line_items where order_id = any(:o)",
                  "delete from order_status_history where order_id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    db.execute(text("delete from notifications where link like :l"), {"l": "/bayi-sohbet?bayi=%"})
    db.execute(text("delete from users where email like :e"), {"e": f"{IZ}.%"})
    if ids:
        db.execute(text("delete from dealers where id = any(:d)").bindparams(d=ids))
    db.execute(text("delete from stores where slug like :s"), {"s": f"{IZ}-%"})
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
