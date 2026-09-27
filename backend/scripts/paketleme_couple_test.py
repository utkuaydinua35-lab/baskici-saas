"""Paketleme kuyruğu — çift kılıf, müşteri değişikliği ve kişiye özel numune.

Sınananlar:
  • ÇİFT KILIF paketlemede İKİ ÜRÜN olarak listelenir (kutuya iki kılıf girer):
    ayrı satır, ayrı model, ayrı görsel, ayrı "kenara ayrıldı" işareti
  • bir yarısı hazır olan çift kılıf siparişi "eksiği olanlar"a GİRER
    (eskiden couple tek birim sayıldığı için hiç görünmüyordu)
  • "paketlemeye uygun" yalnız İKİ yarı da hazırsa
  • adet sayımı çift kılıfı 2 sayar
  • KİŞİYE ÖZEL ürün müşteriye gönderilen NUMUNE görseliyle listelenir
  • müşteri ürün/model değiştirince paketleme satırı güncellenir: yeni ad,
    uyarı satırı ve "hazır/kenara ayrıldı" işaretlerinin kalkması
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (CoupleProduct, Design, DesignApproval, KisiyeOzelProduct,  # noqa: E402
                        LineItem, Mold, MoldItem, ModelDegisimTalebi, Order, Store, Tenant)
from app.routers import packaging as pk  # noqa: E402

GECTI = KALDI = 0
IZ = f"pctest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="PC", platform="storefront", is_active=True)
db.add(st); db.flush()

d1 = Design(tenant_id=tenant.id, store_id=st.id, code=f"{IZ}d1", file_path="x/a.png", file_format="png")
d2 = Design(tenant_id=tenant.id, store_id=st.id, code=f"{IZ}d2", file_path="x/b.png", file_format="png")
db.add_all([d1, d2]); db.flush()

CP_PID, KO_PID, NORMAL_PID = f"{IZ}-cp", f"{IZ}-ko", f"{IZ}-n"
db.add(CoupleProduct(tenant_id=tenant.id, store_id=st.id, product_id=CP_PID,
                     product_title="Çift Kılıf", design_id_1=d1.id, design_id_2=d2.id))
db.add(KisiyeOzelProduct(tenant_id=tenant.id, store_id=st.id, product_id=KO_PID,
                         product_title="Kişiye Özel Kılıf"))
db.flush()


def siparis(no):
    o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-{no}",
              order_number=f"{IZ}{no}", customer_name="Ayşe Yılmaz", current_stage=2,
              created_at_platform=datetime.now(UTC), raw={})
    db.add(o); db.flush()
    return o


def kalem(o, pid, **kw):
    kw.setdefault("properties", [])
    li = LineItem(tenant_id=tenant.id, order_id=o.id, quantity=1, product_id=pid, **kw)
    db.add(li); db.flush()
    return li


def basili_kalip(o, li, design_id, model):
    mo = Mold(tenant_id=tenant.id, kod=f"{IZ}{uuid.uuid4().hex[:3]}", variation="SİYAH",
              kalip_kodlari=[], kilif_sayisi=1, current_stage=3, print_status="basildi")
    db.add(mo); db.flush()
    db.add(MoldItem(tenant_id=tenant.id, mold_id=mo.id, store_id=st.id, line_item_id=li.id,
                    design_id=design_id, slot_index=0, kalip_kodu="A1", model=model,
                    order_number=str(o.order_number)))
    db.flush()
    return mo


try:
    # ── Çift kılıf: iki satır ──
    o1 = siparis(1)
    li1 = kalem(o1, CP_PID, title="Çift Kılıf", device_model_override="iPhone 15",
                device_model_override_2="iPhone 14")
    db.flush(); db.refresh(o1)
    p = pk._order_payload(db, o1)
    print("\n── Çift kılıf iki ürün olarak listelenir ──")
    es("iki satır", 2, len(p["items"]))
    es("slotlar", [1, 2], [i["slot"] for i in p["items"]])
    es("modeller ayrı", ["iPhone 15", "iPhone 14"], [i["model"] for i in p["items"]])
    es("her yarı işaretlenebilir (ayrı key)", 2, len({i["key"] for i in p["items"]}))
    es("yarı etiketi yazılı", ["1. kılıf", "2. kılıf"], [i["couple_slot"] for i in p["items"]])
    es("görseller ayrı tasarımdan", 2, len({i["thumbnail_url"] for i in p["items"]}))
    es("adet 2 sayılır", 2, p["total_units"])

    # kenara ayırma: yarılar birbirini etkilemez
    li1.paketleme_ayrildi = True
    db.flush()
    p = pk._order_payload(db, o1)
    es("1. yarı ayrıldı", [True, False], [i["ayrildi"] for i in p["items"]])

    # ── Eksiği olanlar: bir yarı hazır ──
    print("\n── Bir yarısı hazır çift kılıf ──")
    by_li, by_om, by_slot = pk._printed_maps(db, tenant.id)
    acc, cids = pk._accessory_ids(db, tenant.id), pk._couple_ids(db, tenant.id)
    cdes = pk._couple_tasarimlari(db, tenant.id)
    es("hiçbiri hazır değil → eksiği yok", False,
       pk._eksigi_var(o1, by_li, by_om, acc, cids, by_slot, cdes))
    basili_kalip(o1, li1, d1.id, "iPhone 15")
    db.flush()
    by_li, by_om, by_slot = pk._printed_maps(db, tenant.id)
    es("1. yarı basıldı → EKSİĞİ OLANLAR listesinde", True,
       pk._eksigi_var(o1, by_li, by_om, acc, cids, by_slot, cdes))
    es("paketlemeye uygun DEĞİL", False,
       pk._order_ready(o1, by_li, by_om, acc, cids, by_slot, cdes))
    p = pk._order_payload(db, o1)
    es("satırlarda hazır durumu", [True, False], [i["hazir"] for i in p["items"]])
    basili_kalip(o1, li1, d2.id, "iPhone 14")
    db.flush()
    by_li, by_om, by_slot = pk._printed_maps(db, tenant.id)
    es("iki yarı da basılı → paketlemeye uygun", True,
       pk._order_ready(o1, by_li, by_om, acc, cids, by_slot, cdes))
    es("artık 'eksiği olanlar' değil", False,
       pk._eksigi_var(o1, by_li, by_om, acc, cids, by_slot, cdes))

    # ── Kişiye özel: numune görseli ──
    print("\n── Kişiye özel ürün numune görseliyle ──")
    o2 = siparis(2)
    li2 = kalem(o2, KO_PID, title="Kişiye Özel Kılıf", assigned_design_id=d1.id,
                device_model_override="iPhone 15",
                properties=[{"name": "Fotoğraf", "value": "https://ornek/musteri-foto.jpg"}])
    db.flush(); db.refresh(o2)
    p = pk._order_payload(db, o2)
    es("numune yoksa müşterinin fotoğrafı", "https://ornek/musteri-foto.jpg",
       p["items"][0]["thumbnail_url"])
    db.add(DesignApproval(tenant_id=tenant.id, order_id=o2.id, token=f"{IZ}tok", status="bekliyor",
                          version=1, items=[{"line_item_id": str(li2.id), "slot": 1,
                                             "image_url": "https://ornek/numune-v1.png",
                                             "title": "Kişiye Özel Kılıf"}]))
    db.flush(); db.refresh(o2)
    p = pk._order_payload(db, o2)
    es("gönderilen numune gösterilir", "https://ornek/numune-v1.png", p["items"][0]["thumbnail_url"])
    db.add(DesignApproval(tenant_id=tenant.id, order_id=o2.id, token=f"{IZ}tok2", status="bekliyor",
                          version=2, items=[{"line_item_id": str(li2.id), "slot": 1,
                                             "image_url": "https://ornek/numune-v2.png",
                                             "title": "Kişiye Özel Kılıf"}]))
    db.flush(); db.refresh(o2)
    es("EN YENİ versiyon gösterilir", "https://ornek/numune-v2.png",
       pk._order_payload(db, o2)["items"][0]["thumbnail_url"])
    # eski kayıtlar (line_item_id'siz) başlıkla eşleşir
    db.execute(text("update design_approvals set items = :i where token = :t"),
               {"i": '[{"image_url": "https://ornek/eski.png", "title": "Kişiye Özel Kılıf"}]',
                "t": f"{IZ}tok2"})
    db.flush(); db.expire_all()
    o2 = db.get(Order, o2.id)
    es("eski kayıt başlıkla eşleşir", "https://ornek/eski.png",
       pk._order_payload(db, o2)["items"][0]["thumbnail_url"])

    # ── Müşteri değişikliği paketlemeye yansır ──
    print("\n── Müşteri değişikliği ──")
    o3 = siparis(3)
    li3 = kalem(o3, NORMAL_PID, title="Eski Ürün", device_model_override="iPhone 13",
                is_hazir=True, is_kaliba_eklendi=True)
    li3.paketleme_ayrildi = True
    db.flush(); db.refresh(o3)
    es("önce hazır görünür", True, pk._order_payload(db, o3)["items"][0]["hazir"])

    from app.services import urun_degisikligi as uds
    uds.kaydet(db, li3, st, urun_id="9999", baslik="Yeni Ürün", gorsel=None)
    db.flush(); db.refresh(o3)
    p = pk._order_payload(db, o3)
    it = p["items"][0]
    es("başlık YENİ ürün adı", "Yeni Ürün", it["title"])
    es("uyarı satırı var", True, any("Ürün değişti" in x for x in (it["degisiklik"] or [])))
    es("tasarım bekliyor uyarısı", True, any("TASARIM BEKLİYOR" in x for x in (it["degisiklik"] or [])))
    es("hazır işareti KALKTI", False, bool(li3.is_hazir))
    es("kenara ayrıldı işareti KALKTI", False, bool(li3.paketleme_ayrildi))
    es("artık hazır görünmüyor", False, it["hazir"])

    # model değişikliği: kalıptan çekme yardımcısı işaretleri temizler
    o4 = siparis(4)
    li4 = kalem(o4, NORMAL_PID, title="Ürün", device_model_override="iPhone 13",
                is_hazir=True, is_kaliba_eklendi=True)
    li4.paketleme_ayrildi = True
    db.flush()
    from app.routers.public_model_degisim import _kaliptan_cek
    _kaliptan_cek(db, li4)
    li4.device_model_override = "iPhone 15"
    t = ModelDegisimTalebi(tenant_id=tenant.id, order_id=o4.id, line_item_id=li4.id,
                           token=f"{IZ}md", kalip_turu="seffaf", urun_adi="Ürün",
                           mevcut_model="iPhone 13", durum="uygulandi",
                           secilen_model="iPhone 15",
                           expires_at=datetime.now(UTC) + timedelta(days=1),
                           uygulandi_at=datetime.now(UTC))
    db.add(t); db.flush(); db.refresh(o4)
    it4 = pk._order_payload(db, o4)["items"][0]
    es("model değişikliği hazırlığı sıfırlar", (False, False),
       (bool(li4.is_hazir), bool(li4.paketleme_ayrildi)))
    es("yeni model gösterilir", "iPhone 15", it4["model"])
    es("model uyarısı yazılı", True,
       any("Model değişti" in x for x in (it4["degisiklik"] or [])))
finally:
    db.rollback()
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.store_id == st.id)).all()]
    if oids:
        for q in ("delete from mold_items where line_item_id in (select id from line_items where order_id = any(:o))",
                  "delete from design_approvals where order_id = any(:o)",
                  "delete from model_degisim_talepleri where order_id = any(:o)",
                  "delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    db.execute(text("delete from mold_items where tenant_id = :t and kalip_kodu = 'A1' and order_number like :iz"),
               {"t": tenant.id, "iz": f"{IZ}%"})
    db.execute(text("delete from molds where kod like :iz"), {"iz": f"{IZ}%"})
    for q in ("delete from couple_products where store_id = :s",
              "delete from kisiye_ozel_products where store_id = :s",
              "delete from designs where store_id = :s",
              "delete from stores where id = :s"):
        db.execute(text(q).bindparams(s=st.id))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
