"""
Bayii yonetimi — /api/dealers
Cari hesap + bilgi. Bayii eklenince sanal Store (platform='bayii') olusturulur.
require_permission('bayii') ile korumali.
"""
from __future__ import annotations

import io
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func as sql_func, select
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


def _ensure_store(db: Session, tenant_id, dealer) -> None:
    """Bayinin sanal store'u yoksa olustur (onarim)."""
    if dealer.store_id:
        # store gercekten var mi kontrol et
        st = db.scalar(select(Store).where(Store.id == dealer.store_id, Store.tenant_id == tenant_id))
        if st:
            return
    base = _slugify(dealer.name)
    slug = f"bayii-{base}"
    i = 1
    while db.scalar(select(Store).where(Store.tenant_id == tenant_id, Store.slug == slug)):
        i += 1
        slug = f"bayii-{base}-{i}"
    store = Store(tenant_id=tenant_id, slug=slug, name=f"Bayii: {dealer.name}", platform="bayii", is_active=True)
    db.add(store)
    db.flush()
    dealer.store_id = store.id


class DealerIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    note: str | None = None
    unit_price: float | None = None
    shipping_fee: float | None = None
    currency: str | None = Field("TRY", max_length=3)  # TRY | USD


class DealerUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    note: str | None = None
    unit_price: float | None = None
    shipping_fee: float | None = None
    currency: str | None = Field(None, max_length=3)  # TRY | USD
    is_active: bool | None = None


class PaymentIn(BaseModel):
    amount: float = Field(..., gt=0)        # odeme tutari (pozitif girilir)
    kind: str = Field("odeme", max_length=20)  # 'odeme' | 'duzeltme'
    description: str | None = Field(None, max_length=300)
    direction: str = Field("payment")       # 'payment' (alacak/borc azalt) | 'debt' (borc ekle)
    currency: str = Field("TRY")            # 'TRY' | 'USD'


def _ser(d: Dealer) -> dict:
    return {
        "id": str(d.id), "name": d.name, "phone": d.phone, "email": d.email,
        "address": d.address, "note": d.note, "balance": float(d.balance or 0), "balance_usd": float(d.balance_usd or 0),
        "unit_price": float(d.unit_price or 0), "shipping_fee": float(d.shipping_fee or 0), "currency": getattr(d, "currency", "TRY") or "TRY",
        "is_active": d.is_active, "store_id": str(d.store_id) if d.store_id else None,
    }


def _ser_tx(t: DealerTransaction) -> dict:
    return {
        "id": str(t.id), "amount": float(t.amount), "kind": t.kind, "currency": getattr(t, "currency", "TRY") or "TRY",
        "description": t.description, "balance_after": float(t.balance_after),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "ref_order_id": str(t.ref_order_id) if t.ref_order_id else None,
    }


@router.get("", response_model=list[dict])
def list_dealers(user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Dealer).where(Dealer.tenant_id == user.tenant_id).order_by(Dealer.name)
    ).all()
    # Store'u olmayan/silinmis bayileri onar
    _changed = False
    for d in rows:
        _before = d.store_id
        _ensure_store(db, user.tenant_id, d)
        if d.store_id != _before:
            _changed = True
    if _changed:
        db.commit()
    return [_ser(d) for d in rows]


class ParseContactIn(BaseModel):
    text: str = ""


@router.post("/parse-contact", response_model=dict)
def parse_contact_ep(req: ParseContactIn, user: User = Depends(require_permission("bayii"))):
    """Serbest metinden (Instagram/WhatsApp) alıcı adı/telefon/adres/il/ilçe ayrıştır."""
    from app.services.contact_parser import parse_contact
    return parse_contact(req.text or "")


@router.get("/{dealer_id}/dashboard", response_model=dict)
def dealer_dashboard(dealer_id: uuid.UUID, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    """Bayiye özel dashboard: bakiye + aylık/toplam sipariş adedi, açık sipariş vb."""
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    _ensure_store(db, user.tenant_id, d)
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Bayinin sanal store'u YALNIZCA bu bayinin siparislerini icerir
    orders = db.scalars(
        select(Order).where(Order.tenant_id == user.tenant_id, Order.store_id == d.store_id)
    ).all()
    total = len(orders)
    ay_orders = [o for o in orders if o.created_at_platform and o.created_at_platform >= month_start]
    acik = sum(1 for o in orders if (o.fulfillment_status or "") != "fulfilled" and o.cancelled_at is None and not o.is_iptal)

    def _qty(olist):
        if not olist:
            return 0
        ids = [o.id for o in olist]
        rows = db.execute(
            select(LineItem.order_id, LineItem.quantity).where(LineItem.order_id.in_(ids))
        ).all()
        return sum((q or 1) for _, q in rows)

    base = _ser(d)
    base.update({
        "total_orders": total,
        "month_orders": len(ay_orders),
        "month_qty": _qty(ay_orders),
        "total_qty": _qty(orders),
        "open_orders": acik,
        "month_label": now.strftime("%m/%Y"),
    })
    return base


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
        currency=(req.currency or "TRY").upper(),
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
    for f in ("name", "phone", "email", "address", "note", "unit_price", "shipping_fee", "currency", "is_active"):
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


def _slug_ascii(s: str) -> str:
    tr = str.maketrans("şŞğĞıİçÇöÖüÜ", "sSgGiIcCoOuU")
    s = (s or "bayi").translate(tr)
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "bayi"


@router.get("/{dealer_id}/statement.pdf")
def dealer_statement_pdf(
    dealer_id: uuid.UUID,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Bayi cari ekstre + kârlılık özeti PDF'i indir."""
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    from app.services.dealer_pdf import build_statement_pdf
    data = build_statement_pdf(db, d, date_from=date_from, date_to=date_to)
    fname = f"cari-ekstre-{_slug_ascii(d.name)}.pdf"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@router.post("/{dealer_id}/payment", response_model=dict)
def add_payment(dealer_id: uuid.UUID, req: PaymentIn, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    """Cari hareket ekle. direction='payment' -> bakiye azalir (bayi odedi), 'debt' -> bakiye artar."""
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    delta = Decimal(str(req.amount))
    if req.direction == "payment":
        delta = -delta  # odeme: borc azalir
    cur = (req.currency or "TRY").upper()
    if cur == "USD":
        new_balance = Decimal(str(d.balance_usd or 0)) + delta
        d.balance_usd = new_balance
    else:
        cur = "TRY"
        new_balance = Decimal(str(d.balance or 0)) + delta
        d.balance = new_balance
    tx = DealerTransaction(
        tenant_id=user.tenant_id, dealer_id=d.id,
        amount=delta, kind=req.kind, description=req.description,
        balance_after=new_balance, currency=cur,
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
    # Alıcı (nihai müşteri) bilgisi — akıllı siparişten gelir, kargo için saklanır
    customer_name: str | None = None
    phone: str | None = None
    address: str | None = None
    il: str | None = None
    ilce: str | None = None


@router.get("/{dealer_id}/orders", response_model=list[dict])
def list_dealer_orders(dealer_id: uuid.UUID, user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    """Bayinin siparişleri (mağaza sipariş listesi gibi) — en yeni önce."""
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    from sqlalchemy import desc as _desc
    orders = db.scalars(
        select(Order).where(Order.tenant_id == user.tenant_id, Order.store_id == d.store_id)
        .order_by(_desc(Order.created_at_platform)).limit(500)
    ).all()
    out = []
    for o in orders:
        _raw = o.raw or {}
        _qty = db.scalar(select(sql_func.coalesce(sql_func.sum(LineItem.quantity), 0)).where(LineItem.order_id == o.id)) or 0
        out.append({
            "id": str(o.id),
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "created_at": o.created_at_platform.isoformat() if o.created_at_platform else None,
            "current_stage": o.current_stage,
            "fulfillment_status": o.fulfillment_status,
            "is_iptal": bool(o.is_iptal),
            "total_qty": int(_qty),
            "total_price": _raw.get("total_price"),
            "currency": _raw.get("currency", "TRY"),
            "note": o.note,
        })
    return out


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
    _ensure_store(db, user.tenant_id, d)
    db.flush()
    if not d.is_active:
        raise HTTPException(400, "Bayii pasif")

    unit_price = Decimal(str(d.unit_price or 0))                # bayi para biriminde (USD/TRY)
    shipping = Decimal(str(d.shipping_fee or 0)) if (req.apply_shipping and d.shipping_fee) else Decimal("0")  # HER ZAMAN ₺

    total_qty = sum(it.quantity for it in req.items)
    urun_tutar = unit_price * Decimal(total_qty)               # ürün bedeli (bayi para birimi)

    # Benzersiz siparis no
    now = _dt.now(_UTC)
    seq = now.strftime("%y%m%d%H%M%S")
    external_id = f"BAYII-{d.id.hex[:6]}-{seq}"
    order_number = f"B{seq}"

    # Alıcı (nihai müşteri) — akıllı siparişten; yoksa bayi adı
    _cust = (req.customer_name or "").strip() or d.name
    _raw = {
        "total_price": str(urun_tutar),
        "currency": (getattr(d, "currency", "TRY") or "TRY").upper(),
        "source": "bayii",
        "dealer_id": str(d.id),
        "shipping_fee": str(shipping),
    }
    # Kargo için Shopify-benzeri shipping_address (packaging _addr_parts bunu okur)
    if (req.address or req.phone or req.il):
        _raw["shipping_address"] = {
            "name": _cust,
            "phone": (req.phone or "").strip(),
            "address1": (req.address or "").strip(),
            "city": (req.il or "").strip(),        # il
            "province": (req.ilce or "").strip(),  # ilçe
            "country": "Türkiye",
        }
        _raw["customer_phone"] = (req.phone or "").strip()
    order = Order(
        tenant_id=user.tenant_id,
        store_id=d.store_id,
        external_id=external_id,
        order_number=order_number,
        name=f"#{order_number}",
        customer_name=_cust,
        created_at_platform=now,
        note=req.note,
        current_stage=1,
        raw=_raw,
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

    # Cari borç — ürün bedeli bayi para biriminde, KARGO her zaman ₺ (ayrı hareket).
    _cur = (getattr(d, "currency", "TRY") or "TRY").upper()
    # 1) Ürün bedeli -> bayi para birimi bakiyesi
    if _cur == "USD":
        d.balance_usd = Decimal(str(d.balance_usd or 0)) + urun_tutar
        urun_bakiye = d.balance_usd
    else:
        d.balance = Decimal(str(d.balance or 0)) + urun_tutar
        urun_bakiye = d.balance
    db.add(DealerTransaction(
        tenant_id=user.tenant_id, dealer_id=d.id, amount=urun_tutar, kind="siparis",
        currency=_cur, description=f"Sipariş #{order_number} — {total_qty} adet",
        ref_order_id=order.id, balance_after=urun_bakiye,
    ))
    # 2) Kargo -> HER ZAMAN ₺ bakiyesi (ayrı hareket)
    if shipping > 0:
        d.balance = Decimal(str(d.balance or 0)) + shipping
        db.add(DealerTransaction(
            tenant_id=user.tenant_id, dealer_id=d.id, amount=shipping, kind="kargo",
            currency="TRY", description=f"Kargo — Sipariş #{order_number}",
            ref_order_id=order.id, balance_after=d.balance,
        ))
    db.commit()
    db.refresh(order)

    return {
        "order_id": str(order.id),
        "order_number": order_number,
        "total": float(urun_tutar),
        "currency": _cur,
        "shipping_try": float(shipping),
        "item_count": len(req.items),
        "total_qty": total_qty,
        "new_balance": float(urun_bakiye),
    }
