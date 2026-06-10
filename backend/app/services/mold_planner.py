"""
Kalıp planlayıcı — bekleyen sipariş kalemlerini otomatik kalıplara böler.

Multi-store (Paket 20): store_id None ise tenant'taki TÜM aktif mağazaların
siparişlerini birleştirir. Bir kalıp satırında (örn A1) birden çok mağazadan
kalem karışabilir; baskı üretiminde mağaza farkı yok, kargo etiketi aşamasında
her slot'un kendi store_id'si üzerinden ayrılır.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AccessoryProduct, CoupleProduct, Design, KisiyeOzelProduct, LineItem, Order, Store
from app.services import placement_rules as pr, storage


def extract_phone_model(line_item: LineItem) -> str | None:
    """properties içinde adı ' Model' ile biten kaydın değeri = telefon modeli.
    device_model_override öncelikli."""
    if getattr(line_item, "device_model_override", None):
        return line_item.device_model_override
    for p in (line_item.properties or []):
        if isinstance(p, dict):
            name = (p.get("name") or "")
            if name.endswith("Model") and not name.startswith("_"):
                val = (p.get("value") or "").strip()
                if val:
                    return val
    # properties'te yoksa variant_title'a dus (orn. Lunera: variant_title = "iPhone 16 Pro")
    vt = (getattr(line_item, "variant_title", None) or "").strip()
    if vt:
        return vt
    # son care: raw.variant_title
    raw = getattr(line_item, "raw", None)
    if isinstance(raw, dict):
        rvt = (raw.get("variant_title") or "").strip()
        if rvt:
            return rvt
    return None


def plan_molds(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID | None = None,
    kodlari: pr.KalipKodlari | None = None,
) -> dict:
    """Kalıp planını hesapla.

    store_id verilirse o mağaza; None ise tenant'ın TÜM aktif mağazaları birleşik.
    """
    k = kodlari or pr.DEFAULT_KODLARI

    # Kişiye özel ürün id'leri (store_id, pid) ikilisi olarak
    kop_q = (
        select(KisiyeOzelProduct.store_id, KisiyeOzelProduct.product_id)
        .join(Store, Store.id == KisiyeOzelProduct.store_id)
        .where(
            Store.tenant_id == tenant_id,
            KisiyeOzelProduct.product_id.isnot(None),
        )
    )
    if store_id:
        kop_q = kop_q.where(KisiyeOzelProduct.store_id == store_id)
    kop_keys: set[tuple[uuid.UUID, str]] = {
        (s_id, str(pid)) for (s_id, pid) in db.execute(kop_q).all()
    }

    # Aksesuar (store_id, product_id) — kalip planina dahil edilmez
    acc_q = (
        select(AccessoryProduct.store_id, AccessoryProduct.product_id)
        .join(Store, Store.id == AccessoryProduct.store_id)
        .where(Store.tenant_id == tenant_id, AccessoryProduct.product_id.isnot(None))
    )
    if store_id:
        acc_q = acc_q.where(AccessoryProduct.store_id == store_id)
    acc_keys: set[tuple] = {(s_id, str(pid)) for (s_id, pid) in db.execute(acc_q).all()}

    # (store_id, product_id) -> Design
    design_q = (
        select(Design)
        .join(Store, Store.id == Design.store_id)
        .where(
            Store.tenant_id == tenant_id,
            Design.product_id.isnot(None),
        )
    )
    if store_id:
        design_q = design_q.where(Design.store_id == store_id)
    designs = db.scalars(design_q).all()
    design_by_key: dict[tuple[uuid.UUID, str], Design] = {
        (d.store_id, str(d.product_id)): d for d in designs
    }

    # Couple (cift kilif) urunleri: (store_id, product_id) -> CoupleProduct
    couple_q = (
        select(CoupleProduct)
        .join(Store, Store.id == CoupleProduct.store_id)
        .where(Store.tenant_id == tenant_id, CoupleProduct.product_id.isnot(None))
    )
    if store_id:
        couple_q = couple_q.where(CoupleProduct.store_id == store_id)
    couple_rows = db.scalars(couple_q).all()
    couple_map: dict[tuple, CoupleProduct] = {
        (c.store_id, str(c.product_id)): c for c in couple_rows
    }
    # Couple tasarimlarini id'den bulmak icin (product_id'siz de olabilirler)
    _couple_design_ids = set()
    for c in couple_rows:
        if c.design_id_1: _couple_design_ids.add(c.design_id_1)
        if c.design_id_2: _couple_design_ids.add(c.design_id_2)
    design_by_id: dict[uuid.UUID, Design] = {}
    if _couple_design_ids:
        for d in db.scalars(select(Design).where(Design.id.in_(_couple_design_ids))).all():
            design_by_id[d.id] = d

    # Bekleyen siparişler
    orders_q = (
        select(Order)
        .where(
            Order.tenant_id == tenant_id,
            Order.is_iptal == False,  # noqa: E712
            # Sadece ACIK siparisler: kargoya verilmis (fulfilled) olanlar plana girmez
            (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
            # Iptal/iade edilenler plana girmez
            Order.cancelled_at.is_(None),
            (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
        )
        .options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
    )
    if store_id:
        orders_q = orders_q.where(Order.store_id == store_id)
    orders = db.scalars(orders_q).all()

    units: list[dict] = []
    eksikler: list[dict] = []
    eksik_keys: set = set()

    def add_eksik(reason, li, order, model):
        key = (str(li.product_id), reason)
        if key in eksik_keys:
            for e in eksikler:
                if e["product_id"] == str(li.product_id) and e["reason"] == reason:
                    e["count"] += li.quantity or 1
                    return
        eksik_keys.add(key)
        eksikler.append({
            "reason": reason,
            "product_id": str(li.product_id) if li.product_id else None,
            "title": li.title,
            "model": model,
            "order_number": order.order_number,
            "store_id": str(order.store_id),
            "count": li.quantity or 1,
        })

    for order in orders:
        order_store_id = order.store_id
        for li in (order.line_items or []):
            if li.is_kaliba_eklendi:
                continue
            pid = str(li.product_id) if li.product_id else None
            model = extract_phone_model(li)
            if pid and (order_store_id, pid) in acc_keys:
                continue  # aksesuar — kalipa da eksik listesine de girmez

            # Couple (cift kilif): 2 ayri tasarim, ayni model, 2 birim
            couple = couple_map.get((order_store_id, pid)) if pid else None
            if couple is not None:
                d1 = design_by_id.get(couple.design_id_1) if couple.design_id_1 else None
                d2 = design_by_id.get(couple.design_id_2) if couple.design_id_2 else None
                if not d1 or not d2:
                    add_eksik("couple_tasarim_eksik", li, order, model)
                    continue
                if not model:
                    add_eksik("model_belirsiz", li, order, model)
                    continue
                qty = li.quantity or 1
                _ok = True
                _pending = []
                for _cd in (d1, d2):
                    _var = pr.normalize_variation(_cd.kalip_tipi)
                    _var = pr.effective_variation(pr.get_model_group(model), _var)
                    _kod = pr.resolve_kalip_kodu(model, _var, k)
                    if not _kod:
                        add_eksik("model_taninmadi", li, order, model)
                        _ok = False
                        break
                    _pending.append((_cd, _var, _kod))
                if not _ok:
                    continue
                for _ in range(qty):
                    for (_cd, _var, _kod) in _pending:
                        units.append({
                            "line_item_id": str(li.id),
                            "order_id": str(order.id),
                            "order_number": order.order_number,
                            "store_id": str(order_store_id),
                            "model": model,
                            "product_id": pid,
                            "design_id": str(_cd.id),
                            "design_code": _cd.code,
                            "variation": _var,
                            "kod": _kod,
                            "kilif_rengi": pr.kod_to_renk(_kod, _var),
                            "is_kisiye_ozel": False,
                            "title": li.title,
                            "thumbnail_url": (
                                storage.get_thumbnail_url(_cd.file_path, _cd.file_format)
                                if _cd else None
                            ),
                            "birincil_renk": getattr(_cd, "birincil_renk", None),
                            "kalip_tipi": getattr(_cd, "kalip_tipi", None),
                            "is_couple": True,
                        })
                continue

            is_ko = (order_store_id, pid) in kop_keys if pid else False

            design = None
            if is_ko:
                if li.assigned_design_id and li.assigned_design:
                    design = li.assigned_design
                else:
                    add_eksik("kisiye_ozel_tasarim_eksik", li, order, model)
                    continue
            else:
                design = design_by_key.get((order_store_id, pid)) if pid else None
                if design is None:
                    add_eksik("urun_tasarima_baglanmamis", li, order, model)
                    continue

            if not model:
                add_eksik("model_belirsiz", li, order, model)
                continue

            variation = pr.normalize_variation(design.kalip_tipi)
            variation = pr.effective_variation(pr.get_model_group(model), variation)
            kod = pr.resolve_kalip_kodu(model, variation, k)
            if not kod:
                add_eksik("model_taninmadi", li, order, model)
                continue

            qty = li.quantity or 1
            for _ in range(qty):
                units.append({
                    "line_item_id": str(li.id),
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "store_id": str(order_store_id),
                    "model": model,
                    "product_id": pid,
                    "design_id": str(design.id),
                    "design_code": design.code,
                    "variation": variation,
                    "kod": kod,
                    "kilif_rengi": pr.kod_to_renk(kod, variation),
                    "is_kisiye_ozel": is_ko,
                    "title": li.title,
                    "thumbnail_url": (
                        storage.get_thumbnail_url(design.file_path, design.file_format)
                        if design else None
                    ),
                    "birincil_renk": getattr(design, "birincil_renk", None),
                    "kalip_tipi": getattr(design, "kalip_tipi", None),
                })

    # (kod, variation) grupla, 27 üstü parçala
    groups: dict[tuple, list[dict]] = {}
    for u in units:
        groups.setdefault((u["kod"], u["variation"]), []).append(u)

    queue: list[dict] = []
    for (kod, variation), items in groups.items():
        for i in range(0, len(items), pr.KALIP_MAX_BOXES):
            chunk = items[i:i + pr.KALIP_MAX_BOXES]
            queue.append({
                "items": chunk,
                "count": len(chunk),
                "variation": variation,
                "kodlar": [kod],
                "is_merged": False,
            })

    packed = pr.bin_pack_by_variation(queue)

    def sort_key(b):
        var_idx = pr.VARIATIONS.index(b["variation"]) if b["variation"] in pr.VARIATIONS else 99
        first_kod = sorted(b["kodlar"], key=lambda c: pr.kod_to_group_priority(c, k))[0]
        return (var_idx, pr.kod_to_group_priority(first_kod, k))

    packed.sort(key=sort_key)

    molds = []
    for idx, b in enumerate(packed, 1):
        kod_counts: dict[str, int] = {}
        line_item_ids: set = set()
        store_ids_in_mold: set = set()
        for it in b["items"]:
            kod_counts[it["kod"]] = kod_counts.get(it["kod"], 0) + 1
            line_item_ids.add(it["line_item_id"])
            if it.get("store_id"):
                store_ids_in_mold.add(it["store_id"])
        molds.append({
            "sira": idx,
            "variation": b["variation"],
            "kodlar": sorted(b["kodlar"], key=lambda c: pr.kod_to_group_priority(c, k)),
            "kod_counts": kod_counts,
            "count": b["count"],
            "rows_used": pr._count_rows(b["items"]),
            "is_merged": b["is_merged"],
            "is_multi_store": len(store_ids_in_mold) > 1,
            "store_ids": sorted(store_ids_in_mold),
            "line_item_ids": sorted(line_item_ids),
            "items": [
                {
                    "kod": it["kod"],
                    "design_code": it["design_code"],
                    "model": it["model"],
                    "order_number": it["order_number"],
                    "variation": it["variation"],
                    "kilif_rengi": pr.kod_to_renk(it["kod"], it["variation"]),
                    "is_kisiye_ozel": it["is_kisiye_ozel"],
                    "line_item_id": it["line_item_id"],
                    "design_id": it["design_id"],
                    "store_id": it.get("store_id"),
                    "thumbnail_url": it.get("thumbnail_url"),
                    "birincil_renk": it.get("birincil_renk"),
                    "kalip_tipi": it.get("kalip_tipi"),
                }
                for it in b["items"]
            ],
        })

    return {
        "molds": molds,
        "mold_count": len(molds),
        "total_units": len(units),
        "eksikler": eksikler,
        "eksik_count": sum(e["count"] for e in eksikler),
        "can_create": len(eksikler) == 0 and len(molds) > 0,
        "stats": {
            "kalip_sayisi": len(molds),
            "toplam_kilif": len(units),
            "eksik_kalem": sum(e["count"] for e in eksikler),
        },
    }
