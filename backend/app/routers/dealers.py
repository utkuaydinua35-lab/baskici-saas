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
from app.models import Dealer, DealerTransaction, Order, Store, User

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


class DealerUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    note: str | None = None
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
    for f in ("name", "phone", "email", "address", "note", "is_active"):
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
