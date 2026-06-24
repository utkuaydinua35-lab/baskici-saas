"""Telafiler API — /api/telafiler.

Telafi siparisi: hatali model secimi / yanlis hazirlama yuzunden musteriye
tekrar gonderilecek urunler. Telafi = is_telafi=True isaretli bir Order kaydi.
Boylece kalip olusturucu + 9 asamali pipeline + line item/tasarim altyapisi
oldugu gibi yeniden kullanilir.

Olusturma 2 yolla:
  1) Mevcut siparisten klonla (line item subset) -> /from-order/{order_id}
  2) Sifirdan elle -> /manual

Eslestirme: telafi_kaynak_order_id ile normal siparise baglanir. Normal
siparis detayinda bu telafiler + guncel asamalari gosterilir.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func as sql_func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Design, LineItem, Order, OrderStatusHistory, Store, User
from app.stages import all_stages_payload, is_valid_stage, progress_percent, stage_info

router = APIRouter(prefix="/api/telafiler", tags=["telafiler"])


# ───────────────────────── Serializer ─────────────────────────

def _li_thumbnail(li: LineItem, db: Session | None = None) -> str | None:
    """Urun gorseli — order_detail._serialize_line_item ile ayni mantik:
    raw image -> Design/KisiyeOzel product_id -> atanmis tasarim thumbnail."""
    from app.services import storage
    from app.models import KisiyeOzelProduct

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
            return v

    if db is not None and li.product_id:
        pid = str(li.product_id)
        d = db.scalar(select(Design).where(
            Design.product_id == pid, Design.product_image_url.isnot(None)))
        if d and d.product_image_url:
            return d.product_image_url
        kop = db.scalar(select(KisiyeOzelProduct).where(
            KisiyeOzelProduct.product_id == pid,
            KisiyeOzelProduct.product_image_url.isnot(None)))
        if kop and kop.product_image_url:
            return kop.product_image_url

    if getattr(li, "product_image_url", None):
        return li.product_image_url
    d = li.assigned_design
    if d and getattr(d, "file_path", None):
        try:
            t = storage.get_thumbnail_url(d.file_path, d.file_format)
            if t:
                return t
        except Exception:
            pass
    return None


def _ser_li(li: LineItem, db: Session | None = None) -> dict:
    return {
        "id": str(li.id),
        "title": li.title,
        "variant_title": li.variant_title,
        "quantity": li.quantity,
        "device_model": li.device_model_override
        or next(
            (p.get("value") for p in (li.properties or [])
             if isinstance(p, dict) and (p.get("name") or "").endswith("Model")),
            None,
        ),
        "design_code": (li.assigned_design.code if li.assigned_design else None),
        "design_name": (li.assigned_design.name if li.assigned_design else None),
        "thumbnail_url": _li_thumbnail(li, db),
        "is_kaliba_eklendi": bool(li.is_kaliba_eklendi),
    }


def _ser_telafi(o: Order, detay: bool = False, db: Session | None = None) -> dict:
    si = stage_info(o.current_stage)
    kaynak = o.telafi_kaynak
    d = {
        "id": str(o.id),
        "store_id": str(o.store_id),
        "order_number": o.order_number,
        "customer_name": o.customer_name,
        "telafi_sebep": o.telafi_sebep,
        "current_stage": o.current_stage,
        "current_stage_info": si,
        "progress_percent": progress_percent(o.current_stage),
        "fulfillment_status": o.fulfillment_status,
        "is_iptal": o.is_iptal,
        "created_at_platform": o.created_at_platform.isoformat() if o.created_at_platform else None,
        "kaynak": (
            {
                "id": str(kaynak.id),
                "order_number": kaynak.order_number,
                "customer_name": kaynak.customer_name,
            }
            if kaynak else None
        ),
        "item_count": len(o.line_items or []),
    }
    if detay:
        d["line_items"] = [_ser_li(li, db) for li in (o.line_items or [])]
        d["note"] = o.note
    return d


# ───────────────────────── Liste / meta ─────────────────────────

@router.get("/_meta/stages", response_model=None)
def telafi_stages(user: User = Depends(get_current_user)):
    return {"stages": all_stages_payload()}


@router.get("", response_model=None)
def list_telafiler(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tum telafi siparislerini listele (yeniden eskiye)."""
    rows = db.scalars(
        select(Order)
        .where(Order.tenant_id == user.tenant_id, Order.is_telafi == True)  # noqa: E712
        .options(
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.telafi_kaynak),
        )
        .order_by(desc(Order.created_at_platform), desc(Order.fetched_at))
    ).all()
    return {"items": [_ser_telafi(o) for o in rows]}


@router.get("/_meta/stores", response_model=None)
def telafi_stores(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Klonlama panelinde magaza filtresi icin magaza listesi (bayii haric)."""
    stores = db.scalars(select(Store).where(Store.tenant_id == user.tenant_id)).all()
    return {"items": [
        {"id": str(s.id), "name": s.name}
        for s in stores if getattr(s, "platform", None) != "bayii"
    ]}


@router.get("/searchable-orders", response_model=None)
def searchable_orders(
    q: str = Query("", min_length=0),
    store_id: uuid.UUID | None = Query(None),
    durum: str = Query("all"),  # all | acik | gonderilmis
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Klonlama/eslestirme icin normal (telafi olmayan) siparis ara.
    Filtreler: q (no/musteri), store_id, durum (acik/gonderilmis)."""
    query = (
        select(Order)
        .where(Order.tenant_id == user.tenant_id, Order.is_telafi == False)  # noqa: E712
        .options(
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.store),
        )
    )
    if store_id:
        query = query.where(Order.store_id == store_id)
    if durum == "gonderilmis":
        query = query.where(Order.fulfillment_status == "fulfilled")
    elif durum == "acik":
        query = query.where(
            (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None))
        )
    s = (q or "").strip()
    if s:
        like = f"%{s}%"
        query = query.where(
            or_(Order.order_number.ilike(like), Order.customer_name.ilike(like))
        )
    query = query.order_by(desc(Order.created_at_platform)).limit(limit)
    rows = db.scalars(query).all()
    return {
        "items": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "store_id": str(o.store_id),
                "store_name": (o.store.name if o.store else None),
                "fulfillment_status": o.fulfillment_status,
                "created_at_platform": o.created_at_platform.isoformat() if o.created_at_platform else None,
                "item_count": len(o.line_items or []),
                "line_items": [_ser_li(li, db) for li in (o.line_items or [])],
            }
            for o in rows
        ]
    }


@router.get("/{telafi_id}", response_model=None)
def get_telafi(
    telafi_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    o = db.scalar(
        select(Order)
        .where(Order.id == telafi_id, Order.tenant_id == user.tenant_id, Order.is_telafi == True)  # noqa: E712
        .options(
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.telafi_kaynak),
        )
    )
    if not o:
        raise HTTPException(status_code=404, detail="Telafi bulunamadi")
    return _ser_telafi(o, detay=True, db=db)


# ───────────────────────── Olusturma ─────────────────────────

def _yeni_telafi_kodu(db: Session, tenant_id) -> str:
    """T-1, T-2 ... benzersiz telafi siparis kodu uret."""
    n = db.scalar(
        select(sql_func.count(Order.id))
        .where(Order.tenant_id == tenant_id, Order.is_telafi == True)  # noqa: E712
    )
    return f"T-{(n or 0) + 1}"


class CloneIn(BaseModel):
    line_item_ids: list[uuid.UUID]
    telafi_sebep: str | None = None


@router.post("/from-order/{order_id}", response_model=None)
def create_from_order(
    order_id: uuid.UUID,
    body: CloneIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mevcut siparisten SECILI line item'lari klonlayarak telafi siparisi olustur.
    Tum urunler telafi olmak zorunda degil (orn 4 urunden 1'i)."""
    src = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.tenant_id == user.tenant_id)
        .options(selectinload(Order.line_items))
    )
    if not src:
        raise HTTPException(status_code=404, detail="Kaynak siparis bulunamadi")
    if not body.line_item_ids:
        raise HTTPException(status_code=400, detail="En az bir urun secmelisin")

    sec = {str(x) for x in body.line_item_ids}
    src_lis = [li for li in (src.line_items or []) if str(li.id) in sec]
    if not src_lis:
        raise HTTPException(status_code=400, detail="Secilen urunler kaynak sipariste bulunamadi")

    kod = _yeni_telafi_kodu(db, user.tenant_id)
    telafi = Order(
        tenant_id=user.tenant_id,
        store_id=src.store_id,
        external_id=f"telafi_{kod}_{uuid.uuid4().hex[:6]}",
        order_number=f"{src.order_number}{kod}",
        name=f"#{src.order_number} TELAFI",
        fulfillment_status=None,
        financial_status=None,
        customer_name=src.customer_name,
        customer_email=src.customer_email,
        created_at_platform=datetime.now(timezone.utc),
        note=src.note,
        tags="telafi",
        is_telafi=True,
        telafi_kaynak_order_id=src.id,
        telafi_sebep=(body.telafi_sebep or "").strip() or None,
        raw={"telafi": True, "kaynak_order_number": src.order_number,
             "customer_phone": (src.raw or {}).get("customer_phone"),
             "shipping_address": (src.raw or {}).get("shipping_address")},
    )
    db.add(telafi)
    db.flush()

    for pos, li in enumerate(sorted(src_lis, key=lambda x: x.position or 0)):
        db.add(LineItem(
            tenant_id=user.tenant_id,
            order_id=telafi.id,
            external_id=None,
            product_id=li.product_id,
            variant_id=li.variant_id,
            title=li.title,
            variant_title=li.variant_title,
            sku=li.sku,
            quantity=li.quantity,
            position=pos,
            properties=list(li.properties or []),
            raw={"telafi": True},
            assigned_design_id=li.assigned_design_id,
            device_model_override=li.device_model_override,
            birincil_renk=li.birincil_renk,
            ikincil_renk=li.ikincil_renk,
            ucuncu_renk=li.ucuncu_renk,
            product_image_url=li.product_image_url,
        ))

    db.commit()
    db.refresh(telafi)
    return _ser_telafi(telafi, detay=True, db=db)


class ManualLI(BaseModel):
    title: str
    quantity: int = 1
    device_model: str | None = None
    design_id: uuid.UUID | None = None
    color: str | None = None
    notes: str | None = None


class ManualTelafiIn(BaseModel):
    store_id: uuid.UUID
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    telafi_sebep: str | None = None
    note: str | None = None
    line_items: list[ManualLI]


@router.post("/manual", response_model=None)
def create_manual_telafi(
    body: ManualTelafiIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sifirdan elle telafi siparisi olustur."""
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(status_code=404, detail="Magaza bulunamadi")
    if not body.customer_name.strip():
        raise HTTPException(status_code=400, detail="Musteri adi zorunlu")
    if not body.line_items:
        raise HTTPException(status_code=400, detail="En az bir urun eklemelisin")

    kod = _yeni_telafi_kodu(db, user.tenant_id)
    telafi = Order(
        tenant_id=user.tenant_id,
        store_id=body.store_id,
        external_id=f"telafi_{kod}_{uuid.uuid4().hex[:6]}",
        order_number=kod,
        name=f"#{kod} TELAFI",
        fulfillment_status=None,
        financial_status=None,
        customer_name=body.customer_name.strip(),
        customer_email=body.customer_email,
        created_at_platform=datetime.now(timezone.utc),
        note=body.note,
        tags="telafi",
        is_telafi=True,
        telafi_sebep=(body.telafi_sebep or "").strip() or None,
        raw={"telafi": True, "manual": True, "customer_phone": body.customer_phone},
    )
    db.add(telafi)
    db.flush()

    for pos, li in enumerate(body.line_items):
        if not (li.title or "").strip():
            raise HTTPException(status_code=400, detail=f"Urun #{pos+1}: baslik zorunlu")
        design = None
        if li.design_id:
            design = db.scalar(select(Design).where(
                Design.id == li.design_id, Design.store_id == body.store_id,
                Design.tenant_id == user.tenant_id))
            if not design:
                raise HTTPException(status_code=400, detail=f"Urun #{pos+1}: tasarim bulunamadi")
        if li.device_model:
            from app.services._private import case_dimensions as _cd
            if not _cd.has_spec(li.device_model):
                raise HTTPException(status_code=400, detail=f"Urun #{pos+1}: model taninmadi '{li.device_model}'")
        properties = []
        if li.device_model:
            properties.append({"name": "Telefon Modeli", "value": li.device_model})
        if li.notes:
            properties.append({"name": "Not", "value": li.notes})
        db.add(LineItem(
            tenant_id=user.tenant_id,
            order_id=telafi.id,
            title=li.title.strip(),
            quantity=max(1, int(li.quantity or 1)),
            position=pos,
            properties=properties,
            raw={"telafi": True, "manual": True, "notes": li.notes},
            assigned_design_id=design.id if design else None,
            device_model_override=li.device_model,
            birincil_renk=li.color,
        ))

    db.commit()
    db.refresh(telafi)
    return _ser_telafi(telafi, detay=True, db=db)


# ───────────────────────── Eslestirme / asama / sil ─────────────────────────

class MatchIn(BaseModel):
    order_id: uuid.UUID | None = None


def _get_telafi(db, telafi_id, tenant_id) -> Order:
    o = db.scalar(select(Order).where(
        Order.id == telafi_id, Order.tenant_id == tenant_id, Order.is_telafi == True))  # noqa: E712
    if not o:
        raise HTTPException(status_code=404, detail="Telafi bulunamadi")
    return o


@router.patch("/{telafi_id}/match", response_model=None)
def match_telafi(
    telafi_id: uuid.UUID,
    body: MatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Telafiyi normal bir siparisle eslestir (veya order_id=None ile esi kaldir)."""
    o = _get_telafi(db, telafi_id, user.tenant_id)
    if body.order_id is None:
        o.telafi_kaynak_order_id = None
    else:
        kaynak = db.scalar(select(Order).where(
            Order.id == body.order_id, Order.tenant_id == user.tenant_id, Order.is_telafi == False))  # noqa: E712
        if not kaynak:
            raise HTTPException(status_code=404, detail="Eslestirilecek siparis bulunamadi")
        o.telafi_kaynak_order_id = kaynak.id
    db.commit()
    db.refresh(o)
    return _ser_telafi(o, detay=True, db=db)


class StageIn(BaseModel):
    current_stage: int
    note: str | None = None


@router.patch("/{telafi_id}/stage", response_model=None)
def update_stage(
    telafi_id: uuid.UUID,
    body: StageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    o = _get_telafi(db, telafi_id, user.tenant_id)
    if not is_valid_stage(body.current_stage):
        raise HTTPException(status_code=400, detail="Gecersiz asama")
    eski = o.current_stage
    o.current_stage = body.current_stage
    db.add(OrderStatusHistory(
        tenant_id=user.tenant_id, order_id=o.id,
        from_stage=eski, to_stage=body.current_stage,
        action="stage_change", note=body.note,
        created_by=getattr(user, "email", None),
    ))
    db.commit()
    return {"ok": True, "current_stage": o.current_stage}


@router.delete("/{telafi_id}", status_code=204)
def delete_telafi(
    telafi_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    o = _get_telafi(db, telafi_id, user.tenant_id)
    db.delete(o)
    db.commit()
