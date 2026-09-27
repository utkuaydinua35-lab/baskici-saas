"""Stoğu SIFIRDAN kurma: geçmişi sil, ihtiyaç duyulan modelleri 0 adetle aç.

NEDEN: eldeki stok kayıtları zamanla güvenilmez hale geldi (elle girilen
düzeltmeler, kalıp düşümleri, artık üretilmeyen modeller). "Kaç tane var?"
sorusunun cevabı ekrandaki sayı olmalı; olmuyorsa tüm eksik hesabı (Toplam
Eksik, aksesuar ihtiyacı, kalıp analizi) yanlış çıkıyor.

Akış:
  1) sifirla()  — stok kalemleri + HAREKETLERİ siler (istenirse ana kalemleri de).
     Siparişe, kalıba, tasarıma DOKUNMAZ; yalnız stok tabloları.
  2) kur()      — ihtiyaç duyulan her (model × varyasyon) için 0 adetli kayıt açar.
     Kullanıcı rafı sayıp hücrelere yazar; her yazım hareket olarak kaydedilir.

Sayım mantığı: hücreye yazılan sayı MUTLAK adettir (delta değil) — sayımda
"kaç tane var" yazılır, "kaç ekledim" değil. Stok ekranındaki hücre düzenleme
bunu zaten hedef-eksi-mevcut farkıyla yapıyor.
"""
from __future__ import annotations

import re

from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload

from app.models import Mold, Order, StockGroup, StockItem, StockMovement
from app.services import phone_models as pm, stock as stock_svc

ONAY_METNI = "STOK SIFIRLA"
VARSAYILAN_GRUP = "Boş Kılıf"


def sifirla(db, tenant_id, *, gruplari_da_sil: bool = False) -> dict:
    """Tenant'ın TÜM stok kayıtlarını sil. Geri alınamaz; çağıran onay almalı."""
    def _say(model):
        return int(db.scalar(select(func.count()).select_from(model)
                            .where(model.tenant_id == tenant_id)) or 0)

    kalem_sayisi, hareket_sayisi = _say(StockItem), _say(StockMovement)
    grup_sayisi = _say(StockGroup)

    db.execute(text("delete from stock_movements where tenant_id = :t"), {"t": tenant_id})
    db.execute(text("delete from stock_items where tenant_id = :t"), {"t": tenant_id})
    silinen_grup = 0
    if gruplari_da_sil:
        db.execute(text("delete from stock_groups where tenant_id = :t"), {"t": tenant_id})
        silinen_grup = grup_sayisi
    db.commit()
    return {"silinen_kalem": int(kalem_sayisi), "silinen_hareket": int(hareket_sayisi),
            "silinen_grup": int(silinen_grup)}


def _kalip_modelleri(db, tenant_id) -> set[str]:
    """Panelde BASILMAMIŞ kalıplarda geçen telefon modelleri."""
    out: set[str] = set()
    molds = db.scalars(
        select(Mold).where(Mold.tenant_id == tenant_id).options(selectinload(Mold.items))
    ).all()
    for mo in molds:
        if mo.print_status == "basildi":
            continue
        st = mo.current_stage
        # Baskıcı panelindeki aralık: taslak(1) ve teslim(>=5) hariç
        if not (st is None or (1 < st < 5)):
            continue
        for it in mo.items:
            if (it.model or "").strip():
                out.add(it.model.strip())
    return out


def _siparis_modelleri(db, tenant_id) -> set[str]:
    """AÇIK siparişlerin kalemlerinde geçen telefon modelleri (couple'da ikisi de)."""
    from app.services import mold_planner
    from app.services.order_scope import acik_siparis_filtresi

    out: set[str] = set()
    orders = db.scalars(
        select(Order).where(acik_siparis_filtresi(tenant_id))
        .options(selectinload(Order.line_items))
    ).all()
    for o in orders:
        for li in (o.line_items or []):
            m1, m2 = mold_planner.couple_modelleri(li)
            for m in (m1, m2):
                if (m or "").strip():
                    out.add(m.strip())
    return out


def modelleri_topla(db, tenant_id, kaynak: str = "ikisi") -> list[str]:
    """kaynak: kaliplar | siparisler | ikisi → tekilleştirilmiş model adları."""
    ms: set[str] = set()
    if kaynak in ("kaliplar", "ikisi"):
        ms |= _kalip_modelleri(db, tenant_id)
    if kaynak in ("siparisler", "ikisi"):
        ms |= _siparis_modelleri(db, tenant_id)
    # Aynı modelin farklı yazımları tek satır olsun (iPhone 15 / IPHONE-15)
    gorunen: dict[str, str] = {}
    for m in ms:
        gorunen.setdefault(pm.normalize_key(m), m)
    return sorted(gorunen.values(), key=lambda x: x.lower())


def _sku(db, tenant_id, model: str, variation: str | None) -> str:
    kok = re.sub(r"[^A-Za-z0-9]+", "-", f"{model}-{variation or 'GENEL'}").strip("-").upper()[:90]
    sku, n = kok, 1
    while db.scalar(select(StockItem).where(
            StockItem.tenant_id == tenant_id, StockItem.sku == sku)):
        n += 1
        sku = f"{kok}-{n}"[:100]
    return sku


def kur(db, tenant_id, *, modeller: list[str], varyasyonlar: list[str],
        grup_adi: str = VARSAYILAN_GRUP, esik: int = 0) -> dict:
    """Her (model × varyasyon) için 0 adetli boş kılıf kaydı aç.

    VAR OLAN kayda DOKUNMAZ (aynı model+varyasyon ikinci kez açılmaz) — kurulum
    tekrar çalıştırılabilir, sayılmış adetler bozulmaz.
    """
    varyasyonlar = [v.strip() for v in varyasyonlar if v and v.strip()]
    modeller = [m.strip() for m in modeller if m and m.strip()]
    if not modeller:
        return {"grup_id": None, "olusturulan": 0, "atlanan": 0, "modeller": [], "varyasyonlar": varyasyonlar}
    if not varyasyonlar:
        varyasyonlar = [None]

    grup = db.scalar(select(StockGroup).where(
        StockGroup.tenant_id == tenant_id, StockGroup.name == grup_adi))
    if grup is None:
        grup = StockGroup(tenant_id=tenant_id, name=grup_adi, linked_products=[],
                          low_stock_threshold=esik, is_active=True)
        db.add(grup)
        db.flush()

    mevcut = db.scalars(select(StockItem).where(
        StockItem.tenant_id == tenant_id, StockItem.category == "bos_kilif")).all()
    var_mevcut = {(stock_svc._norm_var(i.variation), pm.normalize_key(i.model or "")) for i in mevcut}

    olusturulan, atlanan = 0, 0
    for model in modeller:
        for var in varyasyonlar:
            anahtar = (stock_svc._norm_var(var), pm.normalize_key(model))
            if anahtar in var_mevcut:
                atlanan += 1
                continue
            db.add(StockItem(
                tenant_id=tenant_id, group_id=grup.id,
                sku=_sku(db, tenant_id, model, var), name=model,
                category="bos_kilif", variation=(var or None),
                model=model, models=[model], quantity=0,
                low_stock_threshold=esik, is_active=True,
            ))
            var_mevcut.add(anahtar)
            olusturulan += 1
    db.commit()
    return {"grup_id": str(grup.id), "grup_adi": grup.name,
            "olusturulan": olusturulan, "atlanan": atlanan,
            "modeller": modeller, "varyasyonlar": [v for v in varyasyonlar if v]}
