"""
Bayii yonetimi — /api/dealers
Cari hesap + bilgi. Bayii eklenince sanal Store (platform='bayii') olusturulur.
require_permission('bayii') ile korumali.
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import Dealer, DealerTransaction, LineItem, Order, Store, User

router = APIRouter(prefix="/api/dealers", tags=["dealers"])


def _slugify(s: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = s.translate(tr).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "bayii"


class DealerIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    note: str | None = None
    unit_price: float | None = None
    shipping_fee: float | None = None


class DealerUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    note: str | None = None
    unit_price: float | None = None
    shipping_fee: float | None = None
    is_active: bool | None = None


class PaymentIn(BaseModel):
    amount: float = Field(..., gt=0)        # odeme tutari (pozitif girilir)
    kind: str = Field("odeme", max_length=20)  # 'odeme' | 'duzeltme'
    description: str | None = Field(None, max_length=300)
    direction: str = Field("payment")       # 'payment' (alacak/borc azalt) | 'debt' (borc ekle)


def _ser(d: Dealer) -> dict:
    return {
        "id": str(d.id), "name": d.name, "phone": d.phone, "email": d.email,
        "address": d.address, "note": d.note, "balance": float(d.balance or 0),
        "unit_price": float(d.unit_price or 0), "shipping_fee": float(d.shipping_fee or 0),
        "is_active": d.is_active, "store_id": str(d.store_id) if d.store_id else None,
    }


def _ser_tx(t: DealerTransaction) -> dict:
    return {
        "id": str(t.id), "amount": float(t.amount), "kind": t.kind,
        "description": t.description, "balance_after": float(t.balance_after),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "ref_order_id": str(t.ref_order_id) if t.ref_order_id else None,
    }


@router.get("", response_model=list[dict])
def list_dealers(user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Dealer).where(Dealer.tenant_id == user.tenant_id).order_by(Dealer.name)
    ).all()
    return [_ser(d) for d in rows]


@router.post("", response_model=dict, status_code=201)
def create_dealer(req: DealerIn, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    # Sanal store olustur (platform='bayii')
    base = _slugify(req.name)
    slug = f"bayii-{base}"
    # slug cakismasi olursa sayi ekle
    i = 1
    while db.scalar(select(Store).where(Store.tenant_id == user.tenant_id, Store.slug == slug)):
        i += 1
        slug = f"bayii-{base}-{i}"
    store = Store(
        tenant_id=user.tenant_id,
        slug=slug,
        name=f"Bayii: {req.name}",
        platform="bayii",
        is_active=True,
    )
    db.add(store)
    db.flush()
    dealer = Dealer(
        tenant_id=user.tenant_id, store_id=store.id,
        name=req.name, phone=req.phone, email=req.email,
        address=req.address, note=req.note, balance=0, is_active=True,
        unit_price=req.unit_price or 0, shipping_fee=req.shipping_fee or 0,
    )
    db.add(dealer)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Bu isimde bayii zaten var") from e
    db.refresh(dealer)
    return _ser(dealer)


@router.get("/{dealer_id}", response_model=dict)
def get_dealer(dealer_id: uuid.UUID, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    return _ser(d)


@router.patch("/{dealer_id}", response_model=dict)
def update_dealer(dealer_id: uuid.UUID, req: DealerUpdate, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    for f in ("name", "phone", "email", "address", "note", "unit_price", "shipping_fee", "is_active"):
        v = getattr(req, f)
        if v is not None:
            setattr(d, f, v)
    db.commit(); db.refresh(d)
    return _ser(d)


@router.delete("/{dealer_id}", response_model=dict)
def delete_dealer(dealer_id: uuid.UUID, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    # Guvenli: pasiflestir (siparis/store iliskisi korunur)
    d.is_active = False
    db.commit()
    return {"ok": True}


@router.get("/{dealer_id}/transactions", response_model=list[dict])
def list_transactions(dealer_id: uuid.UUID, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    rows = db.scalars(
        select(DealerTransaction).where(DealerTransaction.dealer_id == dealer_id)
        .order_by(DealerTransaction.created_at.desc())
    ).all()
    return [_ser_tx(t) for t in rows]


@router.post("/{dealer_id}/payment", response_model=dict)
def add_payment(dealer_id: uuid.UUID, req: PaymentIn, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    """Cari hareket ekle. direction='payment' -> bakiye azalir (bayi odedi), 'debt' -> bakiye artar."""
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    delta = Decimal(str(req.amount))
    if req.direction == "payment":
        delta = -delta  # odeme: borc azalir
    new_balance = Decimal(str(d.balance or 0)) + delta
    d.balance = new_balance
    tx = DealerTransaction(
        tenant_id=user.tenant_id, dealer_id=d.id,
        amount=delta, kind=req.kind, description=req.description,
        balance_after=new_balance,
    )
    db.add(tx)
    db.commit(); db.refresh(d)
    return _ser(d)


# ─── Bayii manuel siparisi (Parca 4c) ───
class DealerOrderItem(BaseModel):
    model: str = Field(..., max_length=200)        # telefon modeli (device_model_override)
    design_id: str | None = None                    # kutuphaneden secilen tasarim
    design_label: str | None = None                 # tasarim adi (title icin)
    quantity: int = Field(1, ge=1, le=9999)


class DealerOrderIn(BaseModel):
    items: list[DealerOrderItem] = Field(..., min_length=1)
    note: str | None = None
    apply_shipping: bool = True                      # bu siparise kargo yansisin mi


@router.post("/{dealer_id}/orders", response_model=dict, status_code=201)
def create_dealer_order(
    dealer_id: uuid.UUID,
    req: DealerOrderIn,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Bayii icin manuel siparis: bayinin store'una Order + LineItem'lar yazilir,
    kaliba akar, cari borc eklenir (adet*birim_fiyat + opsiyonel kargo)."""
    import uuid as _uuid
    from datetime import UTC as _UTC, datetime as _dt

    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    if not d.store_id:
        # Store silinmis/yok — otomatik yeniden olustur (onarim)
        base = _slugify(d.name)
        slug = f"bayii-{base}"
        i = 1
        while db.scalar(select(Store).where(Store.tenant_id == user.tenant_id, Store.slug == slug)):
            i += 1
            slug = f"bayii-{base}-{i}"
        _store = Store(tenant_id=user.tenant_id, slug=slug, name=f"Bayii: {d.name}", platform="bayii", is_active=True)
        db.add(_store)
        db.flush()
        d.store_id = _store.id
        db.flush()
    if not d.is_active:
        raise HTTPException(400, "Bayii pasif")

    unit_price = Decimal(str(d.unit_price or 0))
    shipping = Decimal(str(d.shipping_fee or 0)) if (req.apply_shipping and d.shipping_fee) else Decimal("0")

    total_qty = sum(it.quantity for it in req.items)
    urun_tutar = unit_price * Decimal(total_qty)
    toplam = urun_tutar + shipping

    # Benzersiz siparis no
    now = _dt.now(_UTC)
    seq = now.strftime("%y%m%d%H%M%S")
    external_id = f"BAYII-{d.id.hex[:6]}-{seq}"
    order_number = f"B{seq}"

    order = Order(
        tenant_id=user.tenant_id,
        store_id=d.store_id,
        external_id=external_id,
        order_number=order_number,
        name=f"#{order_number}",
        customer_name=d.name,
        created_at_platform=now,
        note=req.note,
        current_stage=1,
        raw={
            "total_price": str(toplam),
            "currency": "TRY",
            "source": "bayii",
            "dealer_id": str(d.id),
            "shipping_fee": str(shipping),
        },
    )
    db.add(order)
    db.flush()

    # LineItem'lar — kaliba akmasi icin assigned_design_id + device_model_override
    for pos, it in enumerate(req.items):
        design_uuid = None
        if it.design_id:
            try:
                design_uuid = _uuid.UUID(it.design_id)
            except (ValueError, AttributeError):
                design_uuid = None
        title = it.model
        if it.design_label:
            title = f"{it.model} — {it.design_label}"
        li = LineItem(
            tenant_id=user.tenant_id,
            order_id=order.id,
            title=title,
            quantity=it.quantity,
            position=pos,
            assigned_design_id=design_uuid,
            device_model_override=it.model,
            properties=[],
            raw={"source": "bayii"},
        )
        db.add(li)

    # Cari borc: siparis tutari kadar bakiye artar
    new_balance = Decimal(str(d.balance or 0)) + toplam
    d.balance = new_balance
    tx = DealerTransaction(
        tenant_id=user.tenant_id,
        dealer_id=d.id,
        amount=toplam,
        kind="siparis",
        description=f"Sipariş #{order_number} — {total_qty} adet" + (f" (+kargo ₺{shipping})" if shipping else ""),
        ref_order_id=order.id,
        balance_after=new_balance,
    )
    db.add(tx)
    db.commit()
    db.refresh(order)

    return {
        "order_id": str(order.id),
        "order_number": order_number,
        "total": float(toplam),
        "item_count": len(req.items),
        "total_qty": total_qty,
        "new_balance": float(new_balance),
    }
