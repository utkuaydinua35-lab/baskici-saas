"""
Sipariş detay + iş akışı yönetimi — /api/orders/{order_ref}/*  (Paket 12)

order_ref: UUID veya order_number olabilir (kullanıcı dostu URL).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.auth.dependencies import get_current_user, require_any_permission
from app.database import get_db
from app.adapters.shopify import ShopifyAdapter
from app.models import Design, KisiyeOzelProduct, LineItem, Mold, MoldItem, Order, OrderStatusHistory, User
from app.services import (activity, kargo_takip, mold_planner,
                          shipments as shipments_svc, storage)
from app.stages import all_stages_payload, is_valid_stage, progress_percent, stage_info

router = APIRouter(prefix="/api/orders", tags=["order_detail"],
    dependencies=[Depends(require_any_permission("siparisler", "stok"))],
)

VALID_LISTS = {
    "isaretlenenler", "bugun", "sonra", "kontrol", "export", "baski",
    "arsiv",   # Shopify 'archive' karşılığı — vitrin paneli kullanır
}


# ─── Helpers ────────────────────────────────────────────────

def _build_adapter(order):
    """Order'ın mağazasından Shopify adapter (yalnız platform shopify ise)."""
    try:
        store = order.store
        if store and (store.platform or "").lower() == "shopify":
            return ShopifyAdapter(store)
    except Exception:
        pass
    return None


def _address_editable(order, raw: dict | None = None) -> bool:
    """Shopify'dan senkron gerçek sipariş DIŞINDAki her sipariş (bayii, manuel,
    telafi, shopify olmayan mağaza) adresi elle güncellenebilir."""
    raw = raw if raw is not None else (order.raw or {})
    try:
        plat = ((order.store.platform if order.store else "") or "").lower()
    except Exception:  # noqa: BLE001
        plat = ""
    return (
        bool(getattr(order, "is_telafi", False))
        or raw.get("source") == "bayii"
        or bool(raw.get("manual"))
        or plat != "shopify"
    )


def _resolve_order(db: Session, order_ref: str, tenant_id, *, with_rels=True) -> Order:
    """order_ref UUID veya order_number olabilir."""
    opts = []
    if with_rels:
        opts = [
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.status_history),
            selectinload(Order.customer_requests),
            selectinload(Order.email_logs),
            selectinload(Order.shipments),
        ]

    order = None
    # Önce UUID dene
    try:
        oid = uuid.UUID(order_ref)
        q = select(Order).where(Order.id == oid, Order.tenant_id == tenant_id)
        for o in opts:
            q = q.options(o)
        order = db.scalar(q)
    except (ValueError, AttributeError):
        pass

    # UUID değilse veya bulunamadıysa order_number ile ara
    if not order:
        q = select(Order).where(
            Order.order_number == order_ref,
            Order.tenant_id == tenant_id,
        )
        for o in opts:
            q = q.options(o)
        # Birden fazla mağazada aynı numara olabilir — en yeni
        q = q.order_by(desc(Order.created_at))
        order = db.scalar(q)

    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    return order


def _log_history(db: Session, order: Order, user: User, action: str,
                 from_stage: int | None = None, to_stage: int | None = None,
                 note: str | None = None):
    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_stage=from_stage,
        to_stage=to_stage,
        action=action,
        note=note,
        created_by=user.full_name or user.email,
    ))


def _money_from_raw(raw: dict, *keys) -> float | None:
    cur = raw or {}
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    try:
        return float(cur) if cur is not None else None
    except (TypeError, ValueError):
        return None


def _mold_info(li: LineItem, db) -> dict:
    """Line item bir kalıba bağlıysa kalıp kodu + id döndür."""
    if db is None or not getattr(li, "is_kaliba_eklendi", False):
        return {"kalip_kodu": None, "mold_id": None}
    row = db.execute(
        select(Mold.kod, Mold.id).join(MoldItem, MoldItem.mold_id == Mold.id)
        .where(MoldItem.line_item_id == li.id)
        .order_by(Mold.created_at.desc()).limit(1)
    ).first()
    if row:
        return {"kalip_kodu": row[0], "mold_id": str(row[1])}
    return {"kalip_kodu": None, "mold_id": None}


def _nk_model(s: str | None) -> str:
    try:
        from app.services import phone_models as _pm
        return _pm.normalize_key(s or "")
    except Exception:  # noqa: BLE001
        return (s or "").strip().lower()


def _molds_by_line_item(db, order) -> dict:
    """{line_item_id: [{id, kod}]}. Sipariş senkronu line_item_id'yi NULL'a düşürdüğü
    için kademeli eşleşme: line_item_id > (order_number+design_code) > (order_number+model).
    MoldItem.order_number stabil olduğundan aday kayıtlar onunla çekilir."""
    if db is None:
        return {}
    from app.services.mold_planner import extract_phone_model
    line_items = order.line_items or []
    onum = str(order.order_number) if order.order_number is not None else None
    li_ids = [li.id for li in line_items]
    if onum:
        where_clause = MoldItem.order_number == onum
    elif li_ids:
        where_clause = MoldItem.line_item_id.in_(li_ids)
    else:
        return {}
    rows = db.execute(
        select(MoldItem, Mold.id, Mold.kod)
        .join(Mold, Mold.id == MoldItem.mold_id)
        .where(Mold.tenant_id == order.tenant_id, where_clause)
    ).all()
    if not rows:
        return {}
    # Her kalıp slotu YALNIZCA BİR kaleme yazılır ve kalem kapasitesi (adet) kadar
    # slot alır. (Eskiden "aynı modeldeki İLK kalem" seçiliyordu; bu yüzden aynı
    # modelden kardeş kalemlerde tüm kalıplar ilk ürüne yazılıp diğeri "kayıp" görünüyordu.)
    li_by_id = {li.id: li for li in line_items}
    cap = {li.id: max(1, int(getattr(li, "quantity", 1) or 1)) for li in line_items}
    used = {li.id: 0 for li in line_items}
    out: dict = {}

    def _assign(li, mid, kod):
        lst = out.setdefault(li.id, [])
        if not any(x["id"] == str(mid) for x in lst):
            lst.append({"id": str(mid), "kod": kod})
        used[li.id] += 1

    def _free(pred):
        for li in line_items:
            if used[li.id] < cap[li.id] and pred(li):
                return li
        return None

    def _code_of(li):
        return li.assigned_design.code if getattr(li, "assigned_design", None) else None

    # A) line_item_id ile doğrudan bağlı olanlar (en kesin)
    pending = []
    for mi, mid, kod in rows:
        if mi.line_item_id and mi.line_item_id in li_by_id:
            _assign(li_by_id[mi.line_item_id], mid, kod)
        else:
            pending.append((mi, mid, kod))

    # B) tasarım kodu eşleşmesi (kapasitesi kalan kaleme)
    rest = []
    for mi, mid, kod in pending:
        li = _free(lambda x, c=mi.design_code: c and _code_of(x) == c) if mi.design_code else None
        if li:
            _assign(li, mid, kod)
        else:
            rest.append((mi, mid, kod))

    # C) model eşleşmesi
    rest2 = []
    for mi, mid, kod in rest:
        mk = _nk_model(mi.model) if mi.model else None
        li = _free(lambda x, k=mk: k and _nk_model(extract_phone_model(x)) == k) if mk else None
        if li:
            _assign(li, mid, kod)
        else:
            rest2.append((mi, mid, kod))

    # D) kalanlar: kapasitesi olan herhangi bir kalem (kalıp bilgisi kaybolmasın)
    for mi, mid, kod in rest2:
        li = _free(lambda x: True)
        if li:
            _assign(li, mid, kod)
    return out


def _couple_pids(db, store_id) -> set:
    """Bu mağazadaki couple (çift kılıf) ürün id'leri — tek sorgu, satır başına değil."""
    if db is None or not store_id:
        return set()
    from app.models import CoupleProduct
    return {
        str(p) for (p,) in db.execute(
            select(CoupleProduct.product_id).where(CoupleProduct.store_id == store_id)
        ).all() if p
    }


def _aksesuar_pids(db, store_id) -> set:
    """Bu mağazadaki aksesuar ürün id'leri — tek sorgu, satır başına değil.

    Aksesuar ve işleme girmeyen ürünler (ekran koruyucu, magsafe düz kılıf)
    kalıba girmez. mold_planner bunları zaten atlıyor; panelin de aynı
    sınıflandırmayı kullanması gerekiyor, aksi halde bu ürünler sonsuza kadar
    "kalıp bekliyor" görünüyor ve sipariş hiç tamamlanmış sayılmıyordu.
    """
    if db is None or not store_id:
        return set()
    from app.models import AccessoryProduct
    return {
        str(p) for (p,) in db.execute(
            select(AccessoryProduct.product_id).where(AccessoryProduct.store_id == store_id)
        ).all() if p
    }


def _is_couple_li(db, li, couple_pids: set | None = None) -> bool:
    """Kalem couple ürün mü (2 telefon modeli + 2 tasarım)."""
    if not li.product_id:
        return False
    if couple_pids is None:
        store_id = getattr(getattr(li, "order", None), "store_id", None)
        couple_pids = _couple_pids(db, store_id)
    return str(li.product_id) in couple_pids


def _ser_design_min(d) -> dict | None:
    if d is None:
        return None
    return {
        "id": str(d.id),
        "code": d.code,
        "name": d.name,
        "thumbnail_url": storage.get_thumbnail_url(d.file_path, d.file_format),
        "file_url": storage.get_design_url(d.file_path),
    }


def _couple_parcalar(li: LineItem, db) -> list[dict]:
    """Çift kılıfı 2 ALT ÜRÜNE ayır: her kılıfın kendi tasarımı, telefon modeli,
    varyasyonu ve KENDİ kalıp/baskı durumu olur.

    Neden: üretim durumu (is_kaliba_eklendi / basıldı) kalem BAZINDA tutuluyordu;
    çift kılıfın biri basılıp diğeri basılmasa bile kalem 'üretildi' görünüyor ve
    sipariş EKSİK paketleniyordu. Slot bazında kalıp kaydı (MoldItem.design_id)
    zaten var — burada onu okuyup her yarıyı ayrı gösteriyoruz.
    """
    from app.services import mold_planner as _mp

    # Slot -> kalıp/baskı durumu: MoldItem'ları design_id ile eşle.
    by_design: dict = {}
    if db is not None:
        for _mi_did, _kod, _mid, _pstat, _stage in db.execute(
            select(MoldItem.design_id, Mold.kod, Mold.id, Mold.print_status, Mold.current_stage)
            .join(Mold, Mold.id == MoldItem.mold_id)
            .where(MoldItem.line_item_id == li.id)
        ).all():
            by_design.setdefault(_mi_did, []).append({
                "kalip_kodu": _kod,
                "mold_id": str(_mid),
                "basildi": (_pstat == "basildi") or (_stage == 5),
            })

    # Slot tasarımları: kişiye özel couple'da kalemin kendi atamaları, DEĞİLSE
    # CoupleProduct'taki sabit 2 tasarım. (Eskiden yalnız kalemin atamalarına
    # bakılıyordu; kişiye özel olmayan couple'da bunlar BOŞ olduğu için kalıp
    # eşleşmesi hiç tutmuyor, her iki yarı da "kalıba girmedi" görünüyordu.)
    _d1 = li.assigned_design if li.assigned_design_id else None
    _d2 = li.assigned_design_2 if li.assigned_design_id_2 else None
    if (_d1 is None or _d2 is None) and li.product_id and db is not None:
        from app.models import CoupleProduct as _CP, Design as _Dz
        _cp = db.scalar(select(_CP).where(_CP.product_id == str(li.product_id)))
        if _cp is not None:
            if _d1 is None and _cp.design_id_1:
                _d1 = db.scalar(select(_Dz).where(_Dz.id == _cp.design_id_1))
            if _d2 is None and _cp.design_id_2:
                _d2 = db.scalar(select(_Dz).where(_Dz.id == _cp.design_id_2))

    _m1, _m2 = _mp.couple_modelleri(li)

    out = []
    for _slot, _design, _model, _manual in (
        (1, _d1, _m1, bool(getattr(li, "is_hazir", False))),
        (2, _d2, _m2, bool(getattr(li, "is_hazir_2", False))),
    ):
        _var, _kaynak = _mp.resolve_line_variation_detail(li, _design, slot=_slot)
        _kaliplar = by_design.get(_design.id if _design else None, [])
        out.append({
            "slot": _slot,
            "baslik": f"{_slot}. kılıf",
            "design": _ser_design_min(_design),
            "model": _model or None,
            "varyasyon": _var,
            "varyasyon_kaynak": _kaynak,
            "kaliplar": _kaliplar,
            "kaliba_eklendi": bool(_kaliplar),
            "basildi": bool(_kaliplar) and all(x["basildi"] for x in _kaliplar),
            "elle_hazir": _manual,
            # Bu yarı üretilmiş sayılır mı (paketleme bunu arar)
            "uretildi": _manual or (bool(_kaliplar) and all(x["basildi"] for x in _kaliplar)),
        })
    return out


def _serialize_line_item(li: LineItem, db: Session | None = None, adapter=None,
                         couple_pids: set | None = None,
                         aksesuar_pids: set | None = None) -> dict:
    assigned = None
    if li.assigned_design_id and li.assigned_design:
        d = li.assigned_design
        assigned = {
            "id": str(d.id),
            "code": d.code,
            "name": d.name,
            "thumbnail_url": storage.get_thumbnail_url(d.file_path, d.file_format),
            "file_url": storage.get_design_url(d.file_path),
        }

    image_url = None
    raw = li.raw or {}
    for path in [("image",), ("image_url",), ("product", "image")]:
        v = raw
        ok = True
        for p in path:
            if isinstance(v, dict):
                v = v.get(p)
            else:
                ok = False
                break
        if ok and isinstance(v, str) and v.startswith("http"):
            image_url = v
            break

    # Fallback: line item raw'da görsel yok -> Design / KisiyeOzelProduct cache'inden product_id ile bul
    if not image_url and db is not None and li.product_id:
        pid = str(li.product_id)
        d = db.scalar(
            select(Design).where(Design.product_id == pid, Design.product_image_url.isnot(None))
        )
        if d and d.product_image_url:
            image_url = d.product_image_url
        else:
            kop = db.scalar(
                select(KisiyeOzelProduct).where(
                    KisiyeOzelProduct.product_id == pid,
                    KisiyeOzelProduct.product_image_url.isnot(None),
                )
            )
            if kop and kop.product_image_url:
                image_url = kop.product_image_url
    # Shopify'dan canlı ürün görseli (raw'da görsel yok -> product_id ile)
    if not image_url and adapter is not None and li.product_id:
        try:
            img = adapter.get_product_image(str(li.product_id))
            if img:
                image_url = img
        except Exception:
            pass
    # Vitrin (kendi mağaza) ürünü: katalog görselinden bul
    if not image_url and db is not None and li.product_id:
        try:
            from app.models import CatalogProduct
            _cp = db.get(CatalogProduct, uuid.UUID(str(li.product_id)))
            if _cp and _cp.images:
                image_url = f"/storage/{_cp.images[0].file_path}"
        except (ValueError, TypeError):
            pass
    # Son çare: atanmış tasarımın thumbnail'i
    if not image_url and li.assigned_design_id and li.assigned_design:
        image_url = storage.get_thumbnail_url(li.assigned_design.file_path, li.assigned_design.file_format)

    _is_couple = _is_couple_li(db, li, couple_pids)
    # Aksesuar / işleme girmeyen ürün: kalıp gerektirmez.
    _is_aksesuar = bool(li.product_id) and str(li.product_id) in (aksesuar_pids or set())

    return {
        "id": str(li.id),
        "title": li.title,
        "variant_title": li.variant_title,
        "device_model_override": li.device_model_override,
        # Couple (çift kılıf): 2 ayrı telefon modeli — 2. slot ayrı override alır.
        "device_model_override_2": li.device_model_override_2,
        "is_couple": _is_couple,
        # Kalıba girmeyen ürün — panel "kalıp bekliyor" saymasın.
        "is_aksesuar": _is_aksesuar,
        # Çift kılıf 2 alt ürün olarak döner; her yarının kendi tasarımı/modeli/
        # varyasyonu ve KENDİ kalıp+baskı durumu var.
        "parcalar": _couple_parcalar(li, db) if _is_couple else None,
        "couple_models": list(mold_planner.extract_couple_models(li)),
        "quantity": li.quantity,
        "price": (li.raw or {}).get("price"),
        "sku": li.sku,
        "product_id": li.product_id,
        "image_url": image_url,
        "tedarik_status": li.tedarik_status,
        "is_hazir": li.is_hazir,
        "is_hazir_2": li.is_hazir_2,
        "is_kaliba_eklendi": li.is_kaliba_eklendi,
        **_mold_info(li, db),
        "assigned_design": assigned,
        "birincil_renk": li.birincil_renk,
        "ikincil_renk": li.ikincil_renk,
        "ucuncu_renk": li.ucuncu_renk,
        "properties": [
            p for p in (li.properties or [])
            if isinstance(p, dict) and not (p.get("name") or "").startswith("_")
        ],
    }


def _serialize_detail(order: Order, db: Session | None = None) -> dict:
    adapter = _build_adapter(order)
    raw = order.raw or {}

    subtotal = _money_from_raw(raw, "subtotal_price") or _money_from_raw(raw, "current_subtotal_price")
    total = _money_from_raw(raw, "total_price") or _money_from_raw(raw, "current_total_price")
    shipping = None
    shipping_lines = raw.get("shipping_lines") or []
    if shipping_lines and isinstance(shipping_lines, list):
        shipping = _money_from_raw(shipping_lines[0], "price")
    total_tax = _money_from_raw(raw, "total_tax") or _money_from_raw(raw, "current_total_tax")
    total_discount = _money_from_raw(raw, "total_discounts") or _money_from_raw(raw, "current_total_discounts")
    if shipping is None:  # vitrin siparişi: kargo raw.payment altında
        shipping = _money_from_raw(raw.get("payment") or {}, "shipping_amount")
    currency = raw.get("currency") or raw.get("presentment_currency") or "TRY"

    payment_method = None
    gateway_names = raw.get("payment_gateway_names") or []
    if gateway_names:
        payment_method = ", ".join(str(g) for g in gateway_names)

    si = stage_info(order.current_stage)

    _molds_map = _molds_by_line_item(db, order)
    _cpids = _couple_pids(db, order.store_id)   # tek sorgu, tüm kalemler için
    _apids = _aksesuar_pids(db, order.store_id)
    _li_list = []
    for li in (order.line_items or []):
        _d = _serialize_line_item(li, db, adapter, couple_pids=_cpids,
                                  aksesuar_pids=_apids)
        _d["molds"] = sorted(_molds_map.get(li.id, []), key=lambda m: m["kod"] or "")
        _li_list.append(_d)

    return {
        "id": str(order.id),
        "store_id": str(order.store_id),
        "order_number": order.order_number,
        "name": order.name,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "fulfillment_status": order.fulfillment_status,
        "financial_status": order.financial_status,
        "created_at_platform": order.created_at_platform.isoformat() if order.created_at_platform else None,
        "kargo_deadline": order.kargo_deadline.isoformat() if order.kargo_deadline else None,
        "note": order.note,
        "tags": order.tags,

        "current_stage": order.current_stage,
        "current_stage_info": si,
        "progress_percent": progress_percent(order.current_stage),
        # Müşteri onayı (en güncel) — header rozeti için
        "approval_status": (order.approvals[0].status if getattr(order, "approvals", None) else None),
        # Telafi bilgisi: bu siparis bir telafi mi + ona bagli telafiler
        "is_telafi": bool(getattr(order, "is_telafi", False)),
        "telafi_sebep": getattr(order, "telafi_sebep", None),
        "telafiler": [
            {
                "id": str(t.id),
                "order_number": t.order_number,
                "telafi_sebep": t.telafi_sebep,
                "current_stage": t.current_stage,
                "current_stage_label": stage_info(t.current_stage)["label"],
                "progress_percent": progress_percent(t.current_stage),
                "item_count": len(t.line_items or []),
            }
            for t in (getattr(order, "telafiler", None) or [])
        ],
        "is_acil": order.is_acil,
        "is_tedarik_bekleme": order.is_tedarik_bekleme,
        "is_hatali_gonderildi": order.is_hatali_gonderildi,
        "is_iptal": order.is_iptal,
        "internal_lists": order.internal_lists or [],
        "barkod_kodu": order.barkod_kodu,

        "shipping_address": raw.get("shipping_address"),
        "billing_address": raw.get("billing_address"),
        # Adres düzenlenebilir mi: Shopify'dan senkron GERÇEK sipariş hariç hepsi
        # (bayii, manuel, telafi, shopify olmayan mağaza) elle güncellenebilir.
        "address_editable": _address_editable(order, raw),

        # Bayii siparişi ise: geri-navigasyon + tutar dökümü (ürün + kargo)
        "dealer_id": raw.get("dealer_id"),
        "is_bayii": (raw.get("source") == "bayii"),
        "bayii_tutar": ({
            "product_total": raw.get("total_price"),
            "shipping_fee": raw.get("shipping_fee"),
            "currency": raw.get("currency", "TRY"),
        } if raw.get("source") == "bayii" else None),

        "financial": {
            "subtotal": subtotal,
            "shipping": shipping,
            "total_tax": total_tax,
            "total_discount": total_discount,
            "total": total,
            "currency": currency,
            "payment_method": payment_method,
            "payment_status": order.financial_status,
        },

        # Vitrin siparişi işaretleri — panel raw.payment varlığına bakarak
        # iade/düzenleme butonlarını gösterir. Tüm raw AĞIR olduğundan yalnız
        # ihtiyaç duyulan özet döner (bu alan yanıtta yoktu → buton hiç çıkmıyordu).
        "raw": ({
            "payment": raw.get("payment"),
            "discount": raw.get("discount"),
        } if raw.get("payment") else None),

        # Kurumsal fatura bilgisi (vitrin checkout'unda opsiyonel alan)
        "invoice": raw.get("invoice") or None,
        # e-Fatura durumu — faturayı entegratör keser, sonucu entegrasyon
        # API'sinden geri yazar (bkz. routers/entegrasyon.py)
        "fatura_durum": order.fatura_durum,
        "fatura": order.fatura or None,

        "line_items": _li_list,
        # Kargo: tek gönderi bilgisi (Basit Kargo/Shopify takip no) — panelin
        # kargo kartı bunu okur; yanıtta yoktu, takip no hiç görünmüyordu
        "kargo_info": ({
            "takip_no": (order.kargo_info or {}).get("takip_no"),
            # Kayıtlı URL yoksa firmadan üretilir — kendi anlaşma ve Basit Kargo
            # akışında takip URL'i hiçbir yerden gelmiyor.
            "takip_url": kargo_takip.coz(
                (order.kargo_info or {}).get("handler_name"),
                (order.kargo_info or {}).get("takip_no"),
                (order.kargo_info or {}).get("takip_url"),
            ),
            "handler_name": (order.kargo_info or {}).get("handler_name"),
            "kaynak": (order.kargo_info or {}).get("kaynak"),
            # Basit Kargo gerçek kargo takip kodunu dönmezse KENDİ barkodunu
            # takip no olarak yazıyoruz — müşteri onunla takip yapamaz. Panel
            # bunu numara sanmasın diye açıkça işaretleniyor.
            "takip_bekliyor": bool(
                (_bk := (order.kargo_info or {}).get("barcode"))
                and (order.kargo_info or {}).get("takip_no") == _bk
            ),
            # ⚠ Shopify'a fulfillment YAZILAMADIYSA sipariş orada sonsuza dek
            # "gönderilmemiş" görünür ve Shopify kendi kargo mailini hiç
            # göndermez. Panel bunu rozetle söylüyor; eskiden yalnız durum
            # geçmişindeki bir not satırındaydı.
            "shopify_yazilamadi": (order.kargo_info or {}).get("shopify_ok") is False,
            "shopify_hata": (order.kargo_info or {}).get("shopify_err"),
        } if (order.kargo_info or {}).get("takip_no") else None),
        # Kısmi kargolama: gönderiler + kalem başına bekleyen adet
        "shipping": shipments_svc.serialize(order),
        "status_history": [
            {
                "id": str(h.id),
                "from_stage": h.from_stage,
                "to_stage": h.to_stage,
                "from_label": stage_info(h.from_stage)["label"] if h.from_stage else None,
                "to_label": stage_info(h.to_stage)["label"] if h.to_stage else None,
                "action": h.action,
                "note": h.note,
                "created_by": h.created_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in (order.status_history or [])
        ],
        "customer_requests": [
            {
                "id": str(r.id),
                "request_type": r.request_type,
                "message": r.message,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in (order.customer_requests or [])
        ],
        "email_logs": [
            {
                "id": str(e.id),
                "template_key": e.template_key,
                "to_email": e.to_email,
                "subject": e.subject,
                "status": e.status,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in (order.email_logs or [])
        ],
    }


# ─── Stage meta ─────────────────────────────────────────────

@router.get("/_meta/stages", response_model=None)
def get_stages(user: User = Depends(get_current_user)):
    return {"stages": all_stages_payload()}


# ─── Detay ──────────────────────────────────────────────────

@router.get("/{order_ref}/detail", response_model=None)
def get_order_detail(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


# ─── Kısmi kargolama (Shopify fulfillment) ──────────────────

class ShipmentItemIn(BaseModel):
    line_item_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=1000)


class ShipmentCreate(BaseModel):
    items: list[ShipmentItemIn] = Field(..., min_length=1, max_length=100)
    takip_no: str | None = Field(None, max_length=100)
    kargo_firma: str | None = Field(None, max_length=100)
    takip_url: str | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=500)
    send_email: bool = True


@router.post("/{order_ref}/shipments", response_model=None)
def create_shipment(
    order_ref: str,
    payload: ShipmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişin bir bölümünü kargola. Tümü gönderildiyse aşama kargoda olur."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    try:
        shipments_svc.create_shipment(
            db, order,
            items=[{"line_item_id": str(i.line_item_id), "quantity": i.quantity}
                   for i in payload.items],
            takip_no=payload.takip_no, kargo_firma=payload.kargo_firma,
            takip_url=payload.takip_url, note=payload.note,
            user_label=user.email, send_email=payload.send_email,
        )
    except shipments_svc.ShipmentError as e:
        raise HTTPException(422, str(e))
    activity.record(db, user, "kargo_gonderi", store_id=order.store_id, entity_type="siparis",
                    entity_id=order.id, entity_label=order.name or order.order_number,
                    detail={"takip_no": payload.takip_no, "firma": payload.kargo_firma,
                            "adet": sum(i.quantity for i in payload.items)})
    db.commit()
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


@router.delete("/{order_ref}/shipments/{shipment_id}", response_model=None)
def remove_shipment(
    order_ref: str,
    shipment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Yanlış girilen gönderiyi geri al (adetler bekleyene döner)."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    try:
        shipments_svc.delete_shipment(db, order, shipment_id, user_label=user.email)
    except shipments_svc.ShipmentError as e:
        raise HTTPException(404, str(e))
    activity.record(db, user, "kargo_geri", store_id=order.store_id, entity_type="siparis",
                    entity_id=order.id, entity_label=order.name or order.order_number)
    db.commit()
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


# ─── Durum güncelleme ───────────────────────────────────────

class StageUpdate(BaseModel):
    stage: int | None = None
    is_iptal: bool | None = None
    note: str | None = None


@router.patch("/{order_ref}/stage", response_model=None)
def update_stage(
    order_ref: str,
    payload: StageUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)

    if payload.is_iptal is not None:
        order.is_iptal = payload.is_iptal
        _log_history(db, order, user, action="iptal" if payload.is_iptal else "iptal_geri",
                     note=payload.note)

    if payload.stage is not None:
        if not is_valid_stage(payload.stage):
            raise HTTPException(status_code=400, detail="Geçersiz aşama numarası")
        old = order.current_stage
        order.current_stage = payload.stage
        _log_history(db, order, user, action="stage_change",
                     from_stage=old, to_stage=payload.stage, note=payload.note)

    db.commit()
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


# ─── Bayraklar ──────────────────────────────────────────────

class FlagsUpdate(BaseModel):
    is_acil: bool | None = None
    is_tedarik_bekleme: bool | None = None
    is_hatali_gonderildi: bool | None = None
    barkod_kodu: str | None = None
    add_to_list: str | None = None
    remove_from_list: str | None = None
    # Kargo sözü elle override: "YYYY-MM-DD" set eder, "" temizler, None dokunmaz
    kargo_deadline: str | None = None


@router.patch("/{order_ref}/flags", response_model=None)
def update_flags(
    order_ref: str,
    payload: FlagsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)

    if payload.is_acil is not None:
        order.is_acil = payload.is_acil
        _log_history(db, order, user, action="acil" if payload.is_acil else "acil_kaldir")

    if payload.is_tedarik_bekleme is not None:
        order.is_tedarik_bekleme = payload.is_tedarik_bekleme
        _log_history(db, order, user,
                     action="tedarik_bekle" if payload.is_tedarik_bekleme else "tedarik_devam")

    if payload.is_hatali_gonderildi is not None:
        order.is_hatali_gonderildi = payload.is_hatali_gonderildi
        if payload.is_hatali_gonderildi:
            _log_history(db, order, user, action="hatali_gonderildi")

    if payload.barkod_kodu is not None:
        order.barkod_kodu = payload.barkod_kodu.strip() or None

    if payload.kargo_deadline is not None:
        s = payload.kargo_deadline.strip()
        if not s:
            order.kargo_deadline = None
        else:
            try:
                from datetime import datetime as _dt
                from zoneinfo import ZoneInfo as _ZI
                order.kargo_deadline = _dt.strptime(s, "%Y-%m-%d").replace(tzinfo=_ZI("Europe/Istanbul"))
            except ValueError:
                raise HTTPException(status_code=400, detail="Geçersiz tarih (YYYY-MM-DD)")

    lists = list(order.internal_lists or [])
    if payload.add_to_list:
        if payload.add_to_list not in VALID_LISTS:
            raise HTTPException(status_code=400, detail="Geçersiz liste")
        if payload.add_to_list not in lists:
            lists.append(payload.add_to_list)
            _log_history(db, order, user, action="list_add", note=payload.add_to_list)
    if payload.remove_from_list and payload.remove_from_list in lists:
        lists.remove(payload.remove_from_list)
        _log_history(db, order, user, action="list_remove", note=payload.remove_from_list)
    order.internal_lists = lists

    db.commit()
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


# ─── Sipariş düzenleme (Shopify order editing) ──────────────
# Yalnız VİTRİN siparişleri, kargolanmadan önce. Adet değiştir / kalem
# çıkar / katalogdan kalem ekle; toplamlar yeniden hesaplanır ve tahsil
# edilen tutarla FARK döner (eksi → iade önerilir, artı → ek tahsilat).

class EditItemChange(BaseModel):
    op: str                       # set_qty | remove | add
    line_item_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    quantity: int | None = None


class EditItemsIn(BaseModel):
    changes: list[EditItemChange]


@router.post("/{order_ref}/edit-items", response_model=None)
def edit_order_items(
    order_ref: str,
    payload: EditItemsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from decimal import Decimal

    from app.models import CatalogProduct, CatalogVariant, LineItem

    order = _resolve_order(db, order_ref, user.tenant_id)
    raw = dict(order.raw or {})
    if not raw.get("payment"):
        raise HTTPException(400, "Yalnızca vitrin siparişleri düzenlenebilir")
    if order.cancelled_at:
        raise HTTPException(400, "İptal edilmiş sipariş düzenlenemez")
    if (order.current_stage or 1) >= 8:
        raise HTTPException(400, "Kargoya verilmiş sipariş düzenlenemez")
    if not payload.changes:
        raise HTTPException(422, "Değişiklik listesi boş")

    by_id = {li.id: li for li in order.line_items}
    # db.delete edilen kalem, flush sonrası bile order.line_items koleksiyonunda
    # kalabilir — toplamlar bu YEREL liste üzerinden hesaplanır.
    current_items = list(order.line_items)
    # Fiyatların kanonik kaynağı order.raw["line_items"] (id = external_id) —
    # düzenlemeler bu listeyi de senkron tutar (export/dashboard tutarlılığı).
    raw_lines: list[dict] = list(raw.get("line_items") or [])
    raw_by_ext = {str(x.get("id")): x for x in raw_lines}

    def _price_of(li) -> "Decimal":
        p = (li.raw or {}).get("price")
        if p in (None, ""):
            p = (raw_by_ext.get(str(li.external_id)) or {}).get("price")
        try:
            return Decimal(str(p or 0))
        except ArithmeticError:
            return Decimal("0")

    notes: list[str] = []

    for ch in payload.changes:
        if ch.op == "set_qty":
            li = by_id.get(ch.line_item_id)
            if not li:
                raise HTTPException(404, "Kalem bulunamadı")
            q = int(ch.quantity or 0)
            if not (1 <= q <= 20):
                raise HTTPException(422, "Adet 1-20 arasında olmalı")
            if q != li.quantity:
                notes.append(f"{li.title[:40]}: {li.quantity}→{q} adet")
                li.quantity = q
                rl = raw_by_ext.get(str(li.external_id))
                if rl:
                    rl["quantity"] = q
        elif ch.op == "remove":
            li = by_id.pop(ch.line_item_id, None)
            if not li:
                raise HTTPException(404, "Kalem bulunamadı")
            if len(current_items) <= 1:
                raise HTTPException(422, "Son kalem silinemez — siparişi iptal edin")
            notes.append(f"{li.title[:40]} çıkarıldı (×{li.quantity})")
            raw_lines = [x for x in raw_lines if str(x.get("id")) != str(li.external_id)]
            raw_by_ext.pop(str(li.external_id), None)
            current_items.remove(li)
            db.delete(li)
        elif ch.op == "add":
            variant = db.scalar(select(CatalogVariant).where(
                CatalogVariant.id == ch.variant_id,
                CatalogVariant.tenant_id == user.tenant_id))
            if not variant:
                raise HTTPException(404, "Varyant bulunamadı")
            product = db.get(CatalogProduct, variant.product_id)
            if not product or product.store_id != order.store_id:
                raise HTTPException(422, "Varyant bu mağazaya ait değil")
            q = max(1, min(20, int(ch.quantity or 1)))
            price = variant.price_override if variant.price_override is not None else product.base_price
            vtitle = variant.model_display + (f" / {variant.variation}" if variant.variation else "")
            li = LineItem(
                tenant_id=order.tenant_id, order_id=order.id,
                external_id=f"ek-{uuid.uuid4().hex[:10]}",
                product_id=str(product.id), variant_id=str(variant.id),
                title=product.title, variant_title=vtitle,
                quantity=q,
                position=max((x.position or 0) for x in current_items) + 1
                if current_items else 0,
                properties=[{"name": "Sonradan eklendi", "value": "sipariş düzenleme"}],
                raw={"price": str(price)},
                device_model_override=variant.model_display,
                kilif_varyasyon=variant.variation,
            )
            db.add(li)
            order.line_items.append(li)
            current_items.append(li)
            new_raw_line = {
                "id": li.external_id, "product_id": str(product.id),
                "variant_id": str(variant.id), "title": product.title,
                "variant_title": vtitle, "sku": None, "quantity": q,
                "price": str(price),
                "properties": [{"name": "Sonradan eklendi", "value": "sipariş düzenleme"}],
            }
            raw_lines.append(new_raw_line)
            raw_by_ext[str(li.external_id)] = new_raw_line
            notes.append(f"+ {product.title[:40]} ({vtitle}) ×{q}")
        else:
            raise HTTPException(422, f"Bilinmeyen işlem: {ch.op}")

    db.flush()
    raw["line_items"] = raw_lines

    # Toplamları yeniden hesapla (indirim ve kargo sabit kalır)
    items_total = Decimal("0")
    for li in current_items:
        items_total += _price_of(li) * li.quantity
    shipping = Decimal(str((raw.get("payment") or {}).get("shipping_amount") or 0))
    discounts = Decimal(str(raw.get("total_discounts") or 0))
    new_total = items_total - discounts + shipping
    raw["subtotal_price"] = str(items_total)
    raw["total_price"] = str(new_total)
    order.raw = raw
    flag_modified(order, "raw")

    paid = Decimal(str((raw.get("payment") or {}).get("amount") or 0))
    fark = new_total - paid
    _log_history(db, order, user, action="duzenlendi",
                 note="; ".join(notes)[:900] + (f" | fark: {fark:+.2f} TL" if fark else ""))
    db.commit()
    return {"ok": True, "yeni_toplam": str(new_total), "tahsil_edilen": str(paid),
            "fark": str(fark)}


# ─── Zaman akışı yorumu + etiketler (Shopify order detail paritesi) ──

class CommentIn(BaseModel):
    message: str


class AddressIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    address1: str | None = None
    city: str | None = None
    province: str | None = None
    zip: str | None = None


@router.patch("/{order_ref}/address", response_model=None)
def update_address(
    order_ref: str,
    body: AddressIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Shopify harici siparişlerde (bayii / manuel / telafi) müşteri kargo adresini güncelle."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    if not _address_editable(order):
        raise HTTPException(400, "Shopify siparişlerinin adresi Shopify tarafından düzenlenmeli.")
    raw = dict(order.raw or {})
    addr = dict(raw.get("shipping_address") or {})
    for k in ("name", "phone", "address1", "city", "province", "zip"):
        v = getattr(body, k)
        if v is not None:
            addr[k] = v.strip()
    raw["shipping_address"] = addr
    # İsim/telefon kolon + raw ile senkron (liste/kart bunları kullanıyor)
    if body.name is not None and body.name.strip():
        order.customer_name = body.name.strip()
    if body.phone is not None:
        raw["customer_phone"] = body.phone.strip()
    order.raw = raw
    flag_modified(order, "raw")
    _log_history(db, order, user, "address_update", note="Kargo adresi güncellendi")
    db.commit()
    db.refresh(order)
    return _serialize_detail(order, db)


@router.post("/{order_ref}/comment", response_model=None)
def add_comment(
    order_ref: str,
    payload: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Zaman akışına personel yorumu — yalnızca panelde görünür, müşteriye gitmez."""
    msg = (payload.message or "").strip()[:2000]
    if not msg:
        raise HTTPException(status_code=422, detail="Yorum boş olamaz")
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    _log_history(db, order, user, action="not", note=msg)
    db.commit()
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


class TagsIn(BaseModel):
    tags: list[str]


@router.put("/{order_ref}/tags", response_model=None)
def update_tags(
    order_ref: str,
    payload: TagsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sipariş etiketleri — virgüllü saklanır, filtre/arama için."""
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    clean: list[str] = []
    for t in (payload.tags or [])[:20]:
        t = str(t).strip()[:40]
        if t and t.lower() not in [c.lower() for c in clean]:
            clean.append(t)
    order.tags = ", ".join(clean) or None
    db.commit()
    return {"ok": True, "tags": order.tags}


# ─── Müşteriye şablonlu e-posta ─────────────────────────────

class CustomerEmailIn(BaseModel):
    subject: str
    body_html: str = ""
    title: str | None = None


@router.post("/{order_ref}/send-email", response_model=dict)
def send_customer_email(
    order_ref: str,
    req: CustomerEmailIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sipariş müşterisine şablonlu (markalı) e-posta gönder."""
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    to = (order.customer_email or "").strip()
    if not to:
        raise HTTPException(400, "Bu siparişte müşteri e-postası yok")
    from app.services import email_service
    if not email_service.is_configured():
        raise HTTPException(400, "E-posta ayarlı değil (.env SMTP_*)")
    from app.models import Tenant
    tenant = db.get(Tenant, user.tenant_id)
    bk = email_service.brand_kwargs(tenant)
    html = email_service.render_email(
        title=(req.title or req.subject),
        body_html=req.body_html or "",
        footer=f"Sipariş #{order.order_number} · Bu e-posta siparişinizle ilgilidir.",
        **bk,
    )
    from app.services import email_log
    ok = email_log.gonder_ve_kaydet(
        db, tenant_id=order.tenant_id, to=to, subject=req.subject, html=html,
        order_id=order.id, template_key="elle")
    if not ok:
        raise HTTPException(502, "E-posta gönderilemedi")
    _log_history(db, order, user, action="musteri_email", note=(req.subject or "")[:80])
    db.commit()
    return {"ok": True, "to": to}


# ─── Müşteri tasarım onayı ──────────────────────────────────

class ApprovalCreate(BaseModel):
    note: str | None = None


@router.post("/{order_ref}/approval", response_model=dict)
def create_design_approval(
    order_ref: str,
    payload: ApprovalCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Müşteri onay isteği oluştur (yeni versiyon). Link + hazır mesaj + telefon döner."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    from app.services import approvals as ap_svc
    try:
        ap = ap_svc.create_approval(db, order, user, note=payload.note)
    except ap_svc.NoApprovalItems as e:
        raise HTTPException(status_code=422, detail=str(e))
    _log_history(db, order, user, action="onay_gonderildi", note=f"v{ap.version}")
    db.commit()
    db.refresh(ap)
    data = ap_svc.serialize(ap, with_secrets=True)
    data["message"] = ap_svc.build_message(order, data["link"],
                                           revizyon=(ap.version or 1) > 1)
    data["phone"] = ap_svc.resolve_phone(order)
    data["customer_name"] = order.customer_name
    return data


@router.post("/{order_ref}/adres-degisim", response_model=dict)
def adres_degisim_baglantisi(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Müşteriye gönderilecek adres değişikliği bağlantısı + hazır WhatsApp mesajı.

    ⚠ Bağlantı yalnız kargo BAŞLAMADAN üretilir; barkod/kargo kaydı varsa
    müşteriye "değiştirebilirsin" demek yanlış olur (uygulama anında
    reddedilirdi ve müşteri boşa uğraşırdı).
    """
    order = _resolve_order(db, order_ref, user.tenant_id)
    from app.services import adres_degisim as ad_svc
    from app.services import model_degisim as md_svc

    izin, sebep = ad_svc.degistirilebilir_mi(order)
    if not izin:
        raise HTTPException(status_code=409, detail=sebep)

    tel = md_svc.siparis_telefonu(order)
    if not tel:
        raise HTTPException(status_code=422,
                            detail="Siparişte geçerli bir cep telefonu yok.")

    try:
        talep = ad_svc.talep_olustur(db, order)
    except ad_svc.ZatenDegistirildi as e:
        # Adres bir kez değiştirilebilir; ikinci düzeltme panelden elle yapılır.
        raise HTTPException(status_code=409, detail=str(e)) from e
    baglanti = ad_svc.link(talep.token)
    metin = ad_svc.mesaj(order, baglanti)
    _log_history(db, order, user, action="adres_baglantisi",
                 note=f"Adres değişikliği bağlantısı üretildi ({ad_svc.GECERLILIK_DAKIKA} dk)")
    db.commit()
    return {"link": baglanti, "message": metin, "phone": tel,
            "wa_url": md_svc.wa_url(tel, metin),
            "gecerlilik_dk": ad_svc.GECERLILIK_DAKIKA}


@router.get("/{order_ref}/eposta-gecmisi", response_model=dict)
def eposta_gecmisi(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bu siparişe gönderilen e-postalar ve TESLİMAT DURUMLARI.

    ⚠ NEDEN VAR: "mail gelmedi" şikayetinde elimizde hiçbir kanıt yoktu.
    Artık her gönderim kaydediliyor ve Resend webhook'u ULAŞTI / GERİ DÖNDÜ /
    SPAM bilgisini işliyor. Bilgi gelmemişse "bekleniyor" olarak gösterilir —
    "bilinmiyor" ile "ulaşmadı" ASLA karıştırılmamalı.
    """
    from app.config import get_settings
    from app.models import EmailLog
    from app.services import email_log

    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    kayitlar = db.scalars(
        select(EmailLog)
        .where(EmailLog.order_id == order.id, EmailLog.tenant_id == user.tenant_id)
        .order_by(desc(EmailLog.created_at))
        .limit(50)
    ).all()
    return {
        "items": [email_log.ozet(k) for k in kayitlar],
        "eposta": order.customer_email,
        # Webhook kurulu değilse panel "durum gelmiyor" diye boşuna beklemesin.
        "webhook_acik": bool((get_settings().resend_webhook_secret or "").strip()),
    }


@router.get("/{order_ref}/musteri-baglantilari", response_model=dict)
def musteri_baglantilari(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişin müşteriye gönderilmiş model/adres değişikliği bağlantıları.

    NEDEN VAR: bağlantı yalnız üretildiği anda (kalıptan çıkarma penceresinde)
    görünüyordu. WhatsApp sekmesi kapanır ya da mesaj gönderilemezse operatörün
    tek çıkışı kalemi tekrar kalıptan çıkarmaktı — yani üretimi bozmak. Bağlantı
    zaten veritabanında ve süresi doluncaya dek geçerli; burada tekrar
    gösteriliyor.

    Yalnız SON 30 GÜN: bundan eskisi ne geçerli ne de operatör için anlamlı.
    """
    from datetime import UTC, datetime, timedelta

    from app.models import AdresDegisimTalebi, ModelDegisimTalebi
    from app.services import adres_degisim as ad_svc
    from app.services import model_degisim as md_svc

    order = _resolve_order(db, order_ref, user.tenant_id)
    simdi = datetime.now(UTC)
    _sinir = simdi - timedelta(days=30)
    tel = md_svc.siparis_telefonu(order)

    def _ortak(t) -> dict:
        _gecerli = bool(t.durum == "bekliyor" and t.expires_at and t.expires_at > simdi)
        return {
            "id": str(t.id), "durum": t.durum, "gecerli": _gecerli,
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }

    model = []
    for t in db.scalars(
        select(ModelDegisimTalebi)
        .where(ModelDegisimTalebi.order_id == order.id,
               ModelDegisimTalebi.created_at >= _sinir)
        .order_by(desc(ModelDegisimTalebi.created_at))
    ).all():
        d = _ortak(t)
        d.update({"urun_adi": t.urun_adi, "mevcut_model": t.mevcut_model,
                  "kalip_turu": t.kalip_turu, "secilen_model": t.secilen_model,
                  "secilen_varyasyon": t.secilen_varyasyon})
        # Ölü bağlantının mesajını üretmiyoruz: operatör yanlışlıkla gönderirse
        # müşteri açılmayan bir sayfaya düşer.
        if d["gecerli"]:
            d["link"] = md_svc.link(t.token)
            d["message"] = md_svc.mesaj(
                order, urun_adi=t.urun_adi or "ürününüz",
                model=t.mevcut_model or "ürününüz",
                baglanti=d["link"], tur=t.kalip_turu)
            d["wa_url"] = md_svc.wa_url(tel, d["message"]) if tel else None
        model.append(d)

    adres = []
    for t in db.scalars(
        select(AdresDegisimTalebi)
        .where(AdresDegisimTalebi.order_id == order.id,
               AdresDegisimTalebi.created_at >= _sinir)
        .order_by(desc(AdresDegisimTalebi.created_at))
    ).all():
        d = _ortak(t)
        if d["gecerli"]:
            d["link"] = ad_svc.link(t.token)
            d["message"] = ad_svc.mesaj(order, d["link"])
            d["wa_url"] = md_svc.wa_url(tel, d["message"]) if tel else None
        adres.append(d)

    _izin, _sebep = ad_svc.degistirilebilir_mi(order)
    if _izin and ad_svc.zaten_degistirildi(db, order.id):
        _izin, _sebep = False, ad_svc.BIR_KEZ_MESAJI

    return {
        "phone": tel,
        "model": model,
        "adres": adres,
        # Panel "Adres bağlantısı üret" düğmesini buna göre açıp kapatıyor.
        "adres_uretilebilir": {"acik": _izin, "sebep": _sebep},
        "model_gecerlilik_saat": md_svc.GECERLILIK_SAAT,
        "adres_gecerlilik_dk": ad_svc.GECERLILIK_DAKIKA,
    }


@router.get("/{order_ref}/approvals", response_model=dict)
def list_design_approvals(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişin tüm onay istekleri (en yeni önce) + müşteri telefonu/mesajı."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    from app.services import approvals as ap_svc
    items = []
    for a in (order.approvals or []):
        d = ap_svc.serialize(a, with_secrets=True)
        # v1 ilk gönderim; v2+ müşteri revizyon istedikten sonraki tasarım.
        d["message"] = ap_svc.build_message(order, d["link"],
                                            revizyon=(a.version or 1) > 1)
        items.append(d)
    return {
        "items": items,
        "phone": ap_svc.resolve_phone(order),
        "customer_name": order.customer_name,
    }


# ─── Line item güncelleme ───────────────────────────────────

class LineItemWorkflowPatch(BaseModel):
    tedarik_status: str | None = None
    is_hazir: bool | None = None
    is_hazir_2: bool | None = None   # çift kılıfın 2. yarısı
    is_kaliba_eklendi: bool | None = None
    device_model_override: str | None = None
    device_model_override_2: str | None = None   # couple: 2. kılıfın telefon modeli
    fields_to_update: list[str] = []


@router.patch("/{order_ref}/line-items/{line_item_id}", response_model=None)
def update_line_item_workflow(
    order_ref: str,
    line_item_id: uuid.UUID,
    payload: LineItemWorkflowPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    li = db.scalar(
        select(LineItem).where(
            LineItem.id == line_item_id,
            LineItem.order_id == order.id,
            LineItem.tenant_id == user.tenant_id,
        )
    )
    if not li:
        raise HTTPException(status_code=404, detail="Line item bulunamadı")

    fields = set(payload.fields_to_update)
    if "tedarik_status" in fields and payload.tedarik_status is not None:
        li.tedarik_status = payload.tedarik_status
    if "is_hazir" in fields and payload.is_hazir is not None:
        li.is_hazir = payload.is_hazir
    if "is_hazir_2" in fields and payload.is_hazir_2 is not None:
        li.is_hazir_2 = payload.is_hazir_2
    if "is_kaliba_eklendi" in fields and payload.is_kaliba_eklendi is not None:
        li.is_kaliba_eklendi = payload.is_kaliba_eklendi
    if "device_model_override" in fields:
        from app.services.phone_models import gorunen_ad as _ad
        _new = _ad(db, order.tenant_id, (payload.device_model_override or "").strip()) or None
        if _new != li.device_model_override:
            _log_history(
                db, order, user, action="kalem_model_degisti",
                note=f"{(li.title or 'Ürün')[:48]}: {li.device_model_override or '—'} → {_new or '—'}",
            )
        li.device_model_override = _new
    if "device_model_override_2" in fields:
        from app.services.phone_models import gorunen_ad as _ad
        _new2 = _ad(db, order.tenant_id, (payload.device_model_override_2 or "").strip()) or None
        if _new2 != li.device_model_override_2:
            _log_history(
                db, order, user, action="kalem_model_degisti",
                note=f"{(li.title or 'Ürün')[:48]} (2. kılıf): {li.device_model_override_2 or '—'} → {_new2 or '—'}",
            )
        li.device_model_override_2 = _new2

    db.commit()
    db.refresh(li)
    return _serialize_line_item(li, db)


# ─── Geçmiş ─────────────────────────────────────────────────

@router.get("/{order_ref}/history", response_model=None)
def get_history(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    return {
        "items": [
            {
                "id": str(h.id),
                "from_stage": h.from_stage,
                "to_stage": h.to_stage,
                "from_label": stage_info(h.from_stage)["label"] if h.from_stage else None,
                "to_label": stage_info(h.to_stage)["label"] if h.to_stage else None,
                "action": h.action,
                "note": h.note,
                "created_by": h.created_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in (order.status_history or [])
        ]
    }


# ─── Sipariş kopyala ────────────────────────────────────────

@router.post("/{order_ref}/duplicate", response_model=None)
def duplicate_order(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    src = _resolve_order(db, order_ref, user.tenant_id)
    new = Order(
        tenant_id=src.tenant_id,
        store_id=src.store_id,
        external_id=f"COPY-{uuid.uuid4().hex[:10]}",
        order_number=f"{src.order_number}-K",
        name=src.name,
        customer_name=src.customer_name,
        customer_email=src.customer_email,
        raw=src.raw,
        note=src.note,
        tags=src.tags,
        current_stage=1,
    )
    db.add(new)
    db.flush()
    for li in (src.line_items or []):
        db.add(LineItem(
            tenant_id=new.tenant_id,
            order_id=new.id,
            product_id=li.product_id,
            variant_id=li.variant_id,
            title=li.title,
            variant_title=li.variant_title,
            sku=li.sku,
            quantity=li.quantity,
            position=li.position,
            properties=li.properties,
            raw=li.raw,
        ))
    db.commit()
    db.refresh(new)
    return {"id": str(new.id), "order_number": new.order_number}
