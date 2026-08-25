"""'Gerekli Modeller'de MagSafe neden görünmüyor — zinciri adım adım göster.

Liste iki kaynaktan besleniyor:
  A) KALIP tarafı — panel kalıplarındaki kalemler (basılmış olanlar hariç)
  B) AKSESUAR tarafı — kalıba GİRMEYEN ürünler (magsafe düz kılıf, ekran
     koruyucu…). Bunun için ürünün ŞU ÜÇÜ birden sağlaması gerekir:
       1. AccessoryProduct olarak kayıtlı (product_id dolu)
       2. Bir StockGroup'a linked_products ile BAĞLI
       3. Satırdan telefon modeli çözülebiliyor
  Üçünden biri eksikse ürün listede HİÇ görünmez.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (AccessoryProduct, Mold, Order, StockGroup,  # noqa: E402
                        Tenant)
from app.services import stock as stock_svc  # noqa: E402
from app.services.order_scope import acik_siparis_filtresi  # noqa: E402

db = SessionLocal()
MAGSAFE = ("magsafe", "mag safe", "magsafe")


def magsafe_mi(metin: str | None) -> bool:
    t = (metin or "").lower().replace("ı", "i")
    return any(x in t for x in MAGSAFE)


for tenant in db.scalars(select(Tenant)).all():
    siparisler = db.scalars(select(Order).where(acik_siparis_filtresi(tenant.id))).all()
    if not siparisler:
        continue
    print(f"\n{'='*70}\nTENANT: {tenant.name}   (açık sipariş: {len(siparisler)})\n{'='*70}")

    # ─── Açık siparişlerde MagSafe geçen kalemler ───
    magsafe_kalemler = []
    for o in siparisler:
        for li in (o.line_items or []):
            if magsafe_mi(li.title) or magsafe_mi(li.variant_title) \
                    or magsafe_mi(getattr(li, "kilif_varyasyon", None)):
                magsafe_kalemler.append((o, li))
    print(f"\nAçık siparişlerde MagSafe geçen kalem: {len(magsafe_kalemler)}")
    if not magsafe_kalemler:
        print("  → Zaten talep yok; liste boş olması doğru.")
        continue

    # ─── A) Kalıp tarafında görünenler ───
    kalipta = set()
    for mo in db.scalars(select(Mold).where(Mold.tenant_id == tenant.id)).all():
        if mo.print_status == "basildi":
            continue
        st = mo.current_stage
        if not (st is None or (1 < st < 5)):
            continue
        for it in mo.items:
            if magsafe_mi(mo.variation) or magsafe_mi(it.kalip_kodu):
                kalipta.add((it.order_number, it.model))
    print(f"KALIP tarafında görünen MagSafe kalemi: {len(kalipta)}")

    # ─── B) Aksesuar tarafı — üç koşul ───
    aksesuar_pids = {
        str(p) for (p,) in db.execute(
            select(AccessoryProduct.product_id).where(
                AccessoryProduct.tenant_id == tenant.id,
                AccessoryProduct.product_id.isnot(None))).all()}
    gruplar = db.scalars(select(StockGroup).where(
        StockGroup.tenant_id == tenant.id, StockGroup.is_active.is_(True))).all()
    bagli_pids = set()
    for g in gruplar:
        for lp in (g.linked_products or []):
            if isinstance(lp, dict) and lp.get("product_id"):
                bagli_pids.add(str(lp["product_id"]))

    sebepler: dict[str, list] = defaultdict(list)
    for o, li in magsafe_kalemler:
        pid = str(li.product_id) if li.product_id else None
        etiket = f"{o.order_number} · {(li.title or '')[:46]}"
        if (str(o.order_number), li.device_model_override) in kalipta:
            sebepler["✓ kalıpta görünüyor"].append(etiket)
        elif not pid:
            sebepler["✗ satırda product_id YOK"].append(etiket)
        elif pid not in aksesuar_pids:
            sebepler["✗ AKSESUAR olarak kayıtlı değil"].append(f"{etiket}  [pid {pid}]")
        elif pid not in bagli_pids:
            sebepler["✗ stok grubuna BAĞLI değil"].append(f"{etiket}  [pid {pid}]")
        elif not stock_svc._extract_model_for_shipment(li):
            sebepler["✗ telefon MODELİ çözülemedi"].append(etiket)
        else:
            sebepler["✓ aksesuar listesinde çıkmalı"].append(etiket)

    print("\nHER KALEM NEDEN GÖRÜNÜYOR / GÖRÜNMÜYOR:")
    for sebep, liste in sorted(sebepler.items()):
        print(f"\n  {sebep}  ({len(liste)})")
        for x in liste[:8]:
            print(f"      {x}")
        if len(liste) > 8:
            print(f"      … {len(liste)-8} tane daha")

    # ─── Ucun gercek ciktisi ───
    cikti = stock_svc.aksesuar_ihtiyaci(db, tenant.id)
    ms = [x for x in cikti if magsafe_mi(x["grup"]) or magsafe_mi(x["model"])]
    print(f"\nUCUN DONDURDUGU aksesuar satiri: {len(cikti)}  ·  MagSafe olan: {len(ms)}")
    for x in ms[:10]:
        print(f"      {x['grup']} · {x['model']} × {x['count']}")

    # ─── Kayitli aksesuarlar ───
    print("\n" + "-"*70)
    if not aksesuar_pids:
        print("SONUÇ: Bu tenant'ta HİÇ aksesuar ürünü kayıtlı değil.")
        print("  → MagSafe kılıflar 'Aksesuarlar' sayfasından eklenmeli.")
        print("    Sistem bir ürünün kalıba girmeyeceğini ancak böyle bilir.")
    elif not ms:
        eksik_kayit = len(sebepler.get("✗ AKSESUAR olarak kayıtlı değil", []))
        eksik_bag = len(sebepler.get("✗ stok grubuna BAĞLI değil", []))
        if eksik_kayit:
            print(f"SONUÇ: {eksik_kayit} MagSafe kalemi AKSESUAR olarak kayıtlı değil.")
            print("  → 'Aksesuarlar' sayfasından bu ürünleri ekle.")
        elif eksik_bag:
            print(f"SONUÇ: {eksik_bag} MagSafe kalemi stok grubuna bağlı değil.")
            print("  → Bu ARTIK sorun değil (ihtiyaç listesi bağlantı aramıyor).")
            print("    Panelde 'stok takibi yok' etiketiyle görünecekler.")
        else:
            print("SONUÇ: Kalemler görünmeli — panel önbelleği olabilir, yenile.")
    else:
        print(f"SONUÇ: {len(ms)} MagSafe satırı listede ÇIKIYOR. ✓")
    print("-"*70)

    print(f"\nKAYITLI AKSESUAR ÜRÜNLERİ ({len(aksesuar_pids)}):")
    for ap in db.scalars(select(AccessoryProduct).where(
            AccessoryProduct.tenant_id == tenant.id)).all():
        bag = "BAĞLI" if str(ap.product_id) in bagli_pids else "bağlı DEĞİL"
        isaret = "🧲" if magsafe_mi(ap.product_title) else "  "
        print(f"   {isaret} {(ap.product_title or '?')[:52]:52} {bag}")
