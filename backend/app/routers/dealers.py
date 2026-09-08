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

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func as sql_func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import (Dealer, DealerTransaction, Design, LineItem, Order,
                        OrderStatusHistory, Store, User)
from app.services import storage

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


def _is_manual_tx(t: DealerTransaction) -> bool:
    """Kullanıcının elle eklediği hareket mi (sipariş kaynaklı DEĞİL)."""
    return t.kind != "siparis" and not t.ref_order_id


def _ser_tx(t: DealerTransaction) -> dict:
    return {
        "id": str(t.id), "amount": float(t.amount), "kind": t.kind, "currency": getattr(t, "currency", "TRY") or "TRY",
        "description": t.description, "balance_after": float(t.balance_after),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "ref_order_id": str(t.ref_order_id) if t.ref_order_id else None,
        "dekont_url": f"/storage/{t.dekont_path}" if getattr(t, "dekont_path", None) else None,
        # Sipariş kaynaklı hareketler düzenlenmez/silinmez (siparişle senkron kalır);
        # elle eklenenlerde tutar düzenlenebilir + geri alınabilir.
        "manual": _is_manual_tx(t),
    }


def _recompute_dealer_balances(db: Session, dealer: Dealer) -> None:
    """Bir bayinin TÜM hareketlerini kronolojik sırayla yeniden hesapla:
    her hareketin balance_after'ını ve bayinin güncel bakiyelerini (TRY+USD) tazele.
    Herhangi bir tutar düzenleme / silme sonrası çağrılır — tutarlılık garanti."""
    txs = db.scalars(
        select(DealerTransaction).where(DealerTransaction.dealer_id == dealer.id)
        .order_by(DealerTransaction.created_at.asc(), DealerTransaction.id.asc())
    ).all()
    run = {"TRY": Decimal("0"), "USD": Decimal("0")}
    for t in txs:
        cur = (t.currency or "TRY").upper()
        if cur not in run:
            cur = "TRY"
        run[cur] += Decimal(str(t.amount))
        t.balance_after = run[cur]
    dealer.balance = run["TRY"]
    dealer.balance_usd = run["USD"]


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
    # Açık (gönderilmemiş): bayii siparişi Shopify fulfillment kullanmaz — gönderim
    # current_stage >= 8 (kargoya verildi) ile takip edilir. İkisinden biri gönderilmiş
    # sayılır (frontend rozetiyle aynı mantık); iptal/kapalı hariç.
    acik = sum(
        1 for o in orders
        if (o.fulfillment_status or "") != "fulfilled"
        and (o.current_stage or 0) < 8
        and o.cancelled_at is None
        and not o.is_iptal
    )

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
    db.commit(); db.refresh(d); db.refresh(tx)
    return {**_ser(d), "tx_id": str(tx.id)}


@router.post("/{dealer_id}/transactions/{tx_id}/dekont", response_model=dict)
def upload_dekont(
    dealer_id: uuid.UUID, tx_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Cari hareketine (ödeme) dekont dosyası ekle — PDF ya da görsel."""
    tx = db.scalar(select(DealerTransaction).where(
        DealerTransaction.id == tx_id,
        DealerTransaction.dealer_id == dealer_id,
        DealerTransaction.tenant_id == user.tenant_id,
    ))
    if not tx:
        raise HTTPException(404, "Hareket bulunamadı")
    data = file.file.read()
    if not data:
        raise HTTPException(400, "Boş dosya")
    try:
        rel = storage.save_dealer_dekont(user.tenant_id, tx.id, data, file.filename or "dekont.pdf")
    except ValueError as e:
        raise HTTPException(400, str(e))
    tx.dekont_path = rel
    db.commit(); db.refresh(tx)
    return _ser_tx(tx)


@router.delete("/{dealer_id}/transactions/{tx_id}/dekont", response_model=dict)
def delete_dekont(
    dealer_id: uuid.UUID, tx_id: uuid.UUID,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Dekontu kaldır."""
    tx = db.scalar(select(DealerTransaction).where(
        DealerTransaction.id == tx_id,
        DealerTransaction.dealer_id == dealer_id,
        DealerTransaction.tenant_id == user.tenant_id,
    ))
    if not tx:
        raise HTTPException(404, "Hareket bulunamadı")
    if tx.dekont_path:
        try:
            (storage.STORAGE_ROOT / tx.dekont_path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        tx.dekont_path = None
        db.commit(); db.refresh(tx)
    return _ser_tx(tx)


class TxEditIn(BaseModel):
    description: str | None = None
    amount: float | None = Field(None, gt=0)   # yeni tutar (BÜYÜKLÜK); yön korunur


@router.patch("/{dealer_id}/transactions/{tx_id}", response_model=dict)
def edit_transaction(dealer_id: uuid.UUID, tx_id: uuid.UUID, body: TxEditIn,
                     user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    """Cari harekete sonradan açıklama ekle/düzenle; elle eklenen harekette tutarı düzenle
    (yön korunur, bakiye yeniden hesaplanır)."""
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    tx = db.scalar(select(DealerTransaction).where(
        DealerTransaction.id == tx_id, DealerTransaction.dealer_id == dealer_id,
        DealerTransaction.tenant_id == user.tenant_id))
    if not tx:
        raise HTTPException(404, "Hareket bulunamadı")

    if body.description is not None:
        tx.description = body.description.strip()[:300] or None

    if body.amount is not None:
        if not _is_manual_tx(tx):
            raise HTTPException(400, "Sipariş kaynaklı hareketin tutarı düzenlenemez (siparişten yönetilir).")
        sign = -1 if Decimal(str(tx.amount)) < 0 else 1
        tx.amount = sign * abs(Decimal(str(body.amount)))
        _recompute_dealer_balances(db, d)

    db.commit(); db.refresh(d)
    return {"ok": True, **_ser(d)}


@router.delete("/{dealer_id}/transactions/{tx_id}", response_model=dict)
def delete_transaction(dealer_id: uuid.UUID, tx_id: uuid.UUID,
                       user: User = Depends(require_permission("bayii")), db: Session = Depends(get_db)):
    """Elle eklenen cari hareketi geri al (sil) — bakiye yeniden hesaplanır.
    Sipariş kaynaklı hareketler silinemez (sipariş iptaliyle yönetilir)."""
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    tx = db.scalar(select(DealerTransaction).where(
        DealerTransaction.id == tx_id, DealerTransaction.dealer_id == dealer_id,
        DealerTransaction.tenant_id == user.tenant_id))
    if not tx:
        raise HTTPException(404, "Hareket bulunamadı")
    if not _is_manual_tx(tx):
        raise HTTPException(400, "Sipariş kaynaklı hareket silinemez (siparişten yönetilir).")
    if tx.dekont_path:
        try:
            (storage.STORAGE_ROOT / tx.dekont_path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
    db.delete(tx)
    db.flush()
    _recompute_dealer_balances(db, d)
    db.commit(); db.refresh(d)
    return {"ok": True, **_ser(d)}


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

    from app.services import dealer_debt
    orders = db.scalars(
        select(Order).where(Order.tenant_id == user.tenant_id, Order.store_id == d.store_id)
        .order_by(_desc(Order.created_at_platform)).limit(500)
    ).all()

    # Her siparişin cari borcu HÂLÂ AÇIK MI? Silme onayı bunu bilmeli: bayi
    # siparişi geri çektiyse borç zaten iade edilmiştir ve silmek bakiyeyi
    # DEĞİŞTİRMEZ. "Cari borcundan düşülecek" demek kullanıcıyı yanıltıyordu
    # (ikinci kez düşecek sanılıyor — düşmüyor, servis idempotent).
    # Para birimleri AYRI yürür (ürün bayi biriminde, kargo hep ₺) — tek bir
    # sayıya toplamak yanıltıcı olurdu. Ayrıca "hiç borç yazılmamış" (sipariş
    # henüz onaylanmadı) ile "yazılmış ama iade edilmiş" farkı burada ayrılıyor;
    # ikisinde de bakiye değişmez ama kullanıcıya söylenecek cümle farklı.
    _hareket: dict[uuid.UUID, dict] = {}
    if orders:
        for _oid, _cur, _kind, _tut in db.execute(
            select(DealerTransaction.ref_order_id, DealerTransaction.currency,
                   DealerTransaction.kind,
                   sql_func.coalesce(sql_func.sum(DealerTransaction.amount), 0))
            .where(DealerTransaction.ref_order_id.in_([o.id for o in orders]))
            .group_by(DealerTransaction.ref_order_id, DealerTransaction.currency,
                      DealerTransaction.kind)
        ):
            _h = _hareket.setdefault(_oid, {"borc_var": False, "net": {}})
            _c = (_cur or "TRY").upper()
            _h["net"][_c] = _h["net"].get(_c, 0.0) + float(_tut or 0)
            if _kind in dealer_debt.BORC_TURLERI:
                _h["borc_var"] = True
    out = []
    for o in orders:
        _raw = o.raw or {}
        _qty = db.scalar(select(sql_func.coalesce(sql_func.sum(LineItem.quantity), 0)).where(LineItem.order_id == o.id)) or 0
        _kayit = _hareket.get(o.id) or {"borc_var": False, "net": {}}
        _acik = {c: round(v, 2) for c, v in _kayit["net"].items() if abs(v) > 0.005}
        out.append({
            "id": str(o.id),
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "created_at": o.created_at_platform.isoformat() if o.created_at_platform else None,
            "current_stage": o.current_stage,
            "fulfillment_status": o.fulfillment_status,
            "is_iptal": bool(o.is_iptal),
            "total_qty": int(_qty),
            "total_price": _raw.get("total_price"),        # ürün bedeli (bayi para birimi)
            "shipping_fee": _raw.get("shipping_fee"),      # kargo (₺, ayrı) — 0/None olabilir
            "currency": _raw.get("currency", "TRY"),
            # Silme onayının doğru cümleyi kurabilmesi için (bkz. _hareket):
            # cari_kayit_var=False → borç hiç yazılmadı; cari_acik boş → iade
            # edilmiş. İkisinde de silmek bakiyeyi DEĞİŞTİRMEZ.
            "cari_kayit_var": _kayit["borc_var"],
            "cari_acik": _acik,
            "borc_acik": bool(_acik),
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


@router.delete("/{dealer_id}/orders/{order_id}", response_model=dict)
def delete_dealer_order(
    dealer_id: uuid.UUID,
    order_id: uuid.UUID,
    force: bool = Query(False, description="Kargoya verilmiş siparişi de sil"),
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Bayi siparişini sil + cari borcunu geri al.

    Soft-delete: sipariş çöp kutusuna gider, geri alınırsa borç TEKRAR yazılır
    (app.services.dealer_debt idempotent).

    Kargoya verilmiş sipariş (aşama >= 8) kazayla silinip borcu sıfırlanmasın
    diye ayrıca onay ister: force=true.
    """
    from app.services import dealer_debt

    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")

    order = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id))
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")

    # SAHIPLIK: siparis gercekten BU bayinin mi? Kontrol edilmezse baska bir
    # bayinin borcu geri alinabilirdi. Bayi siparisleri kendi magazasinda acilir;
    # raw.dealer_id de yaziliyor, ikisi de sinanir.
    _raw = order.raw or {}
    _rd = str(_raw.get("dealer_id") or "")
    # raw.dealer_id VARSA kesin ölçüt odur; yoksa mağaza eşleşmesine düşülür.
    # (OR ile bakmak, iki bayi aynı mağazayı paylaşırsa birinin diğerinin
    # siparişini silmesine izin verirdi.)
    _sahip = (_rd == str(d.id)) if _rd else (order.store_id == d.store_id)
    if not _sahip:
        raise HTTPException(403, "Bu sipariş bu bayiye ait değil")

    if (order.current_stage or 0) >= 8 and not force:
        raise HTTPException(
            409,
            "Bu sipariş kargoya verilmiş. Silersen bayinin borcu da geri alınır — "
            "emin isen onaylayarak tekrar dene.",
        )

    ozet = dealer_debt.uygula(db, order, reverse=True)
    order.deleted_at = datetime.now(UTC)
    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id, order_id=order.id,
        from_stage=order.current_stage, to_stage=order.current_stage,
        action="silindi",
        note=f"Bayi panelinden silindi ({d.name}) · borç iadesi: "
             + (", ".join(f"{x['delta']:.2f} {x['currency']}" for x in ozet) or "yok"),
        created_by=user.full_name or user.email,
    ))
    db.commit()
    return {"ok": True, "order_id": str(order.id), "iade": ozet}


class AddOrderItemsIn(BaseModel):
    items: list[DealerOrderItem] = Field(..., min_length=1)


@router.post("/{dealer_id}/orders/{order_id}/items", response_model=dict)
def add_dealer_order_items(
    dealer_id: uuid.UUID,
    order_id: uuid.UUID,
    req: AddOrderItemsIn,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Mevcut bayii siparişine sonradan ürün ekle. Yeni kalemler kalıba akar
    (is_kaliba_eklendi=False), sipariş tutarı ve cari GÜNCELLENİR (ürün bedeli
    bayi para biriminde; kargo eklenmez — o ilk siparişte uygulanır)."""
    import uuid as _uuid
    from sqlalchemy.orm.attributes import flag_modified

    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    order = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id, Order.store_id == d.store_id))
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı (bu bayiye ait değil)")
    if order.is_iptal:
        raise HTTPException(400, "İptal edilmiş siparişe ürün eklenemez")

    unit_price = Decimal(str(d.unit_price or 0))
    if unit_price <= 0:
        raise HTTPException(400, "Bu bayiye birim fiyat tanımlı değil — önce fiyat belirle")

    add_qty = sum(it.quantity for it in req.items)
    add_tutar = unit_price * Decimal(add_qty)
    _cur = (getattr(d, "currency", "TRY") or "TRY").upper()

    # Yeni kalemleri mevcut siparişin sonuna ekle (kalıba akması için design + model)
    max_pos = db.scalar(select(sql_func.coalesce(sql_func.max(LineItem.position), -1))
                        .where(LineItem.order_id == order.id)) or -1
    pos = int(max_pos) + 1
    for it in req.items:
        design_uuid = None
        if it.design_id:
            try:
                design_uuid = _uuid.UUID(it.design_id)
            except (ValueError, AttributeError):
                design_uuid = None
        title = it.model
        if it.design_label:
            title = f"{it.model} — {it.design_label}"
        db.add(LineItem(
            tenant_id=user.tenant_id, order_id=order.id, title=title,
            quantity=it.quantity, position=pos,
            assigned_design_id=design_uuid, device_model_override=it.model,
            properties=[], raw={"source": "bayii", "sonradan_eklendi": True},
        ))
        pos += 1

    # Sipariş tutarını güncelle (raw.total_price = ürün bedeli, kargo hariç)
    _raw = dict(order.raw or {})
    _prev_total = Decimal(str(_raw.get("total_price") or 0))
    _raw["total_price"] = str(_prev_total + add_tutar)
    order.raw = _raw
    flag_modified(order, "raw")

    # Cari borç — eklenen ürün bedeli (bayi para biriminde)
    if _cur == "USD":
        d.balance_usd = Decimal(str(d.balance_usd or 0)) + add_tutar
        new_balance = d.balance_usd
    else:
        d.balance = Decimal(str(d.balance or 0)) + add_tutar
        new_balance = d.balance
    db.add(DealerTransaction(
        tenant_id=user.tenant_id, dealer_id=d.id, amount=add_tutar, kind="siparis",
        currency=_cur, description=f"Sipariş #{order.order_number} — ek ürün ({add_qty} adet)",
        ref_order_id=order.id, balance_after=new_balance,
    ))
    db.commit()

    return {
        "order_id": str(order.id),
        "order_number": order.order_number,
        "added_qty": add_qty,
        "added_amount": float(add_tutar),
        "new_total": float(_prev_total + add_tutar),
        "currency": _cur,
        "new_balance": float(new_balance),
    }


# ─── Bayi portali: onay kuyrugu ─────────────────────────────
# Bayi portalinden gelen siparis 'bayii_onay_bekliyor' ile durur: kaliba
# girmez ve cari borcu ISLENMEZ. Yonetici varyasyonu secip onaylayinca borc
# yazilir (app.services.dealer_debt.ilk_borc — idempotent).
@router.get("/portal/onay-bekleyen", response_model=list[dict])
def portal_onay_bekleyen(
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    orders = db.scalars(
        select(Order).where(
            Order.tenant_id == user.tenant_id,
            Order.bayii_onay_bekliyor == True,  # noqa: E712
            Order.is_iptal == False,            # noqa: E712
        ).options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
        .order_by(Order.created_at_platform.desc())
    ).all()

    bayiler = {str(d.id): d for d in db.scalars(
        select(Dealer).where(Dealer.tenant_id == user.tenant_id)).all()}
    out = []
    for o in orders:
        raw = o.raw or {}
        d = bayiler.get(str(raw.get("dealer_id") or ""))
        out.append({
            "id": str(o.id),
            "order_number": o.order_number,
            "bayi": d.name if d else "—",
            "dealer_id": str(d.id) if d else None,
            # Tasarim secici bu magazanin katalogunu listeler
            "store_id": str(o.store_id) if o.store_id else None,
            # Kargo tiki bayinin AYARINDAN gelsin: ucret 0 ise tiksiz acilir.
            "kargo_ucreti": float(d.shipping_fee or 0) if d else 0.0,
            "para_birimi": (d.currency or "TRY").upper() if d else "TRY",
            "birim_fiyat": float(d.unit_price or 0) if d else 0.0,
            "kanal": raw.get("kanal"),
            "musteri": o.customer_name,
            "adres": raw.get("shipping_address") or {},
            "tarih": o.created_at_platform.isoformat() if o.created_at_platform else None,
            "not": o.note,
            "kalemler": [{
                "id": str(li.id),
                "model": li.device_model_override,
                "adet": li.quantity or 1,
                "varyasyon": li.kilif_varyasyon,
                "tasarim_id": str(li.assigned_design_id) if li.assigned_design_id else None,
                "tasarim_kodu": li.assigned_design.code if li.assigned_design else None,
                # Bayi JPG yukluyor; baski PDF ister. Panel bunu uyari olarak
                # gosterip indirme + PDF yukleme sunuyor.
                "format": (li.assigned_design.file_format or "").lower()
                if li.assigned_design else None,
                "dosya": storage.get_design_url(li.assigned_design.file_path)
                if li.assigned_design else None,
                "gorsel": storage.get_thumbnail_url(
                    li.assigned_design.file_path, li.assigned_design.file_format)
                if li.assigned_design else None,
                # ÖNİZLEME: bayinin yüklediği "kılıf üzerinde nasıl duracak"
                # görseli. AYRI alanda — baskı her zaman "dosya"dan gider.
                "onizleme": storage.onizleme_url(li.assigned_design.onizleme_path)
                if li.assigned_design else None,
            } for li in sorted(o.line_items or [], key=lambda x: x.position or 0)],
        })
    return out


class KalemDuzeltIn(BaseModel):
    """İkisi de opsiyonel — yalnız gönderilen alan değişir."""
    design_id: uuid.UUID | None = None
    varyasyon: str | None = None


def _kalem_kalipta_mi(db: Session, li) -> bool:
    """Kalem ŞU AN fiziksel bir kalıp slotunda mı?"""
    from app.models import MoldItem as _MI
    return bool(db.scalar(select(_MI.id).where(_MI.line_item_id == li.id).limit(1)))


@router.patch("/portal/siparis/{order_id}/kalem/{line_item_id}", response_model=dict)
# Eski yol: panelde açık kalmış sekmeler 404 almasın diye bir sürüm daha duruyor.
@router.patch("/portal/onay-bekleyen/{order_id}/kalem/{line_item_id}/tasarim",
              response_model=dict)
def portal_kalem_duzelt(
    order_id: uuid.UUID,
    line_item_id: uuid.UUID,
    req: KalemDuzeltIn,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Kalemin TASARIMINI ve/veya VARYASYONUNU düzelt.

    Sınır ONAY DEĞİL, KALIP: kalem fiziksel bir kalıp slotundaysa değiştirilemez
    (basılmış olabilir). Onaydan sonra da düzeltilebilir — onayı geri almak
    bayinin carisinde borç-iade-borç üçlemesi yaratırdı; hatanın kendisi
    içerikte, onayda değil.

    Tasarım için: bayi aynı görseli her siparişte yeniden yüklüyor; katalogdan
    seçmek yeni dosya oluşturmaz.
    """
    o = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id,
    ).options(selectinload(Order.line_items)))
    if not o:
        raise HTTPException(404, "Siparis bulunamadi")
    if o.is_iptal:
        raise HTTPException(409, "Siparis iptal edilmis")

    li = next((x for x in (o.line_items or []) if x.id == line_item_id), None)
    if li is None:
        raise HTTPException(404, "Kalem bulunamadi")
    if _kalem_kalipta_mi(db, li):
        raise HTTPException(
            409, "Kalem kalipta — once kaliptan cikar, sonra duzelt")

    degisiklikler: list[str] = []
    eski_id = li.assigned_design_id
    yeni = None

    if req.varyasyon is not None:
        from app.services import placement_rules
        _v = placement_rules.normalize_variation(req.varyasyon) or req.varyasyon
        if _v != li.kilif_varyasyon:
            degisiklikler.append(f"varyasyon: {li.kilif_varyasyon or '—'} -> {_v}")
            li.kilif_varyasyon = _v

    if req.design_id is not None:
        yeni = db.scalar(select(Design).where(
            Design.id == req.design_id, Design.tenant_id == user.tenant_id))
        if not yeni:
            raise HTTPException(404, "Tasarim bulunamadi")
        if eski_id != yeni.id:
            li.assigned_design_id = yeni.id
        else:
            yeni = None   # degismedi

    if yeni is None and not degisiklikler:
        return {"ok": True, "degismedi": True}
    db.flush()

    # Bayinin yukledigi tasarim artik HICBIR yerde kullanilmiyorsa panele
    # bildir — silme karari kullanicinin; sessizce silmek veri kaybi riski.
    eski_bosta = False
    eski_kod = None
    if yeni is not None and eski_id:
        _eski = db.get(Design, eski_id)
        eski_kod = _eski.code if _eski else None
        kalan = db.scalar(select(sql_func.count()).select_from(LineItem).where(
            LineItem.assigned_design_id == eski_id))
        eski_bosta = not kalan
    if yeni is not None:
        degisiklikler.append(f"tasarim: {eski_kod or '—'} -> {yeni.code}")

    _not = " · ".join(degisiklikler)
    db.add(OrderStatusHistory(
        tenant_id=o.tenant_id, order_id=o.id,
        from_stage=o.current_stage, to_stage=o.current_stage,
        action="bayii_kalem_duzeltildi",
        note=(f"Kalem duzeltildi ({li.device_model_override or '—'}) · {_not}"
              + ("" if o.bayii_onay_bekliyor else " · ONAY SONRASI")),
        created_by=user.full_name or user.email,
    ))
    # Onaydan SONRA yapilan duzeltmeyi bayi gormeli — sessiz degisiklik,
    # bayinin ekranindaki bilgiyle basilan urunu ayirir.
    if not o.bayii_onay_bekliyor:
        _bayiye_bildir(db, o, "Siparisinde duzeltme yapildi",
                       f"#{o.order_number} · {_not}")
    db.commit()
    return {
        "ok": True,
        "degisiklikler": degisiklikler,
        "varyasyon": li.kilif_varyasyon,
        "onay_sonrasi": not o.bayii_onay_bekliyor,
        "tasarim_id": str(yeni.id) if yeni else (str(eski_id) if eski_id else None),
        "tasarim_kodu": yeni.code if yeni else eski_kod,
        "format": (yeni.file_format or "").lower() or None if yeni else None,
        "gorsel": storage.get_thumbnail_url(yeni.file_path, yeni.file_format) if yeni else None,
        "dosya": storage.get_design_url(yeni.file_path) if yeni else None,
        "eski_bosta": eski_bosta,
        "eski_tasarim_id": str(eski_id) if (yeni and eski_id) else None,
        "eski_tasarim_kodu": eski_kod if yeni else None,
    }


class PortalOnayIn(BaseModel):
    # Kalem basina secilen varyasyon: {line_item_id: "SIYAH"|"BEYAZ"|...}
    varyasyonlar: dict[str, str] = Field(default_factory=dict)
    apply_shipping: bool = True


@router.post("/portal/onay-bekleyen/{order_id}", response_model=dict)
def portal_onayla(
    order_id: uuid.UUID,
    req: PortalOnayIn,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Bayi siparisini onayla: varyasyonlari yaz, cari borcu isle, kaliba ac."""
    from app.services import dealer_debt, placement_rules, push

    o = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id,
    ).options(selectinload(Order.line_items)))
    if not o:
        raise HTTPException(404, "Siparis bulunamadi")
    if not o.bayii_onay_bekliyor:
        raise HTTPException(409, "Bu siparis zaten onaylanmis")

    d = db.scalar(select(Dealer).where(
        Dealer.id == uuid.UUID(str((o.raw or {}).get("dealer_id"))),
        Dealer.tenant_id == user.tenant_id)) if (o.raw or {}).get("dealer_id") else None
    if not d:
        raise HTTPException(400, "Siparisin bayisi bulunamadi")

    for li in (o.line_items or []):
        sec = (req.varyasyonlar or {}).get(str(li.id))
        if sec:
            li.kilif_varyasyon = placement_rules.normalize_variation(sec) or sec

    adet = sum(int(li.quantity or 1) for li in (o.line_items or []))
    ozet = dealer_debt.ilk_borc(db, d, o, adet=adet, kargo_uygula=req.apply_shipping)

    # Bayinin gordugu tahmini tutarlar kesinlessin
    raw = dict(o.raw or {})
    raw["total_price"] = str(ozet["urun"])
    raw["shipping_fee"] = str(ozet["kargo"])
    o.raw = raw
    o.bayii_onay_bekliyor = False

    db.add(OrderStatusHistory(
        tenant_id=o.tenant_id, order_id=o.id,
        from_stage=o.current_stage, to_stage=o.current_stage,
        action="bayii_onay",
        note=f"Bayi siparisi onaylandi ({d.name}) · borc: "
             f"{ozet['urun']:.2f} {ozet['currency']}"
             + (f" + {ozet['kargo']:.2f} TRY kargo" if ozet["kargo"] else ""),
        created_by=user.full_name or user.email,
    ))
    # Bayiye haber ver
    try:
        for u in db.scalars(select(User).where(User.dealer_id == d.id)).all():
            push.send_to_user(db, u.id, "Siparisin onaylandi",
                              f"#{o.order_number} uretime alindi.",
                              url=f"/bayii/siparis/{o.id}")
    except Exception:  # noqa: BLE001
        pass
    db.commit()
    return {"ok": True, "order_id": str(o.id), **ozet}


# ─── Bayi portali: iptal talepleri ──────────────────────────
@router.get("/portal/duzeltilebilir", response_model=list[dict])
def portal_duzeltilebilir(
    limit: int = 20,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """ONAYLANMIS ama henuz kalibA GIRMEMIS bayi siparisleri.

    Hatali onaydan sonra duzeltme penceresi budur. Kalip asamasi baslamis
    siparis burada GORUNMEZ — degistirilemeyecegi icin listelemek yanıltır.
    """
    from app.models import MoldItem as _MI

    orders = db.scalars(
        select(Order).where(
            Order.tenant_id == user.tenant_id,
            Order.bayii_onay_bekliyor == False,   # noqa: E712
            Order.is_iptal == False,              # noqa: E712
            Order.deleted_at.is_(None),
            Order.raw["dealer_id"].astext.isnot(None),
        ).options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
        .order_by(desc(Order.created_at)).limit(min(max(limit, 1), 50) * 3)
    ).all()

    bayiler = {str(d.id): d for d in db.scalars(
        select(Dealer).where(Dealer.tenant_id == user.tenant_id)).all()}
    out = []
    for o in orders:
        if len(out) >= limit:
            break
        li_ids = [li.id for li in (o.line_items or [])]
        if not li_ids:
            continue
        kaliptaki = set(db.scalars(select(_MI.line_item_id).where(
            _MI.line_item_id.in_(li_ids))).all())
        serbest = [li for li in (o.line_items or []) if li.id not in kaliptaki]
        if not serbest:
            continue   # tamami kalipta — duzeltilemez
        d = bayiler.get(str((o.raw or {}).get("dealer_id") or ""))
        out.append({
            "id": str(o.id),
            "order_number": o.order_number,
            "store_id": str(o.store_id) if o.store_id else None,
            "bayi": d.name if d else "—",
            "musteri": o.customer_name,
            "kanal": (o.raw or {}).get("kanal"),
            "tarih": o.created_at_platform.isoformat() if o.created_at_platform else None,
            "asama": o.current_stage or 1,
            "kismen_kalipta": bool(kaliptaki),
            "kalemler": [{
                "id": str(li.id),
                "model": li.device_model_override,
                "adet": li.quantity or 1,
                "varyasyon": li.kilif_varyasyon,
                "tasarim_id": str(li.assigned_design_id) if li.assigned_design_id else None,
                "tasarim_kodu": li.assigned_design.code if li.assigned_design else None,
                "format": (li.assigned_design.file_format or "").lower()
                if li.assigned_design else None,
                "dosya": storage.get_design_url(li.assigned_design.file_path)
                if li.assigned_design else None,
                "gorsel": storage.get_thumbnail_url(
                    li.assigned_design.file_path, li.assigned_design.file_format)
                if li.assigned_design else None,
                # ÖNİZLEME: bayinin yüklediği "kılıf üzerinde nasıl duracak"
                # görseli. AYRI alanda — baskı her zaman "dosya"dan gider.
                "onizleme": storage.onizleme_url(li.assigned_design.onizleme_path)
                if li.assigned_design else None,
            } for li in sorted(serbest, key=lambda x: x.position or 0)],
        })
    return out


class YoneticiIptalIn(BaseModel):
    sebep: str = ""
    # Iade kurallari kaliba gore otomatik; basilmis kalipta iade YOK.
    # Yonetici yine de iptal etmek isterse bunu ACIKCA onaylar.
    onayla: bool = False


@router.post("/portal/siparis/{order_id}/iptal", response_model=dict)
def portal_yonetici_iptal(
    order_id: uuid.UUID,
    req: YoneticiIptalIn,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Yonetici bir bayi siparisini DOGRUDAN iptal eder.

    Bugune kadar iptal yalnizca bayinin TALEBI uzerine isliyordu; "hic
    onaylanmamaliydi" durumunda yoneticinin elinde yol yoktu.

    Iade kurali bayii_iptal'de (basilmis kalip varsa malzeme harcandi, iade
    yok). Sonuclari geri alinmasi zor oldugu icin onayla=true sart — ve
    onaydan once ne olacagini ONIZLEME olarak doner.
    """
    from app.services import bayii_iptal

    o = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id,
    ).options(selectinload(Order.line_items)))
    if not o:
        raise HTTPException(404, "Siparis bulunamadi")
    if not (o.raw or {}).get("dealer_id"):
        raise HTTPException(400, "Bu bir bayi siparisi degil")
    if o.is_iptal:
        raise HTTPException(409, "Siparis zaten iptal edilmis")

    durum, kaliplar = bayii_iptal.durumu_oku(db, o)
    if not req.onayla:
        # ONIZLEME: ne olacagini SOYLE, sonra onaylat. Sessizce yapmak,
        # geri alinamayan bir islemde kabul edilemez.
        return {
            "ok": False, "onay_gerekli": True,
            "iade_edilecek": durum.iade_edilir,
            "kaliba_girdi": durum.kaliba_girdi,
            "kalip_basildi": durum.basilmis_kalip_var,
            "etkilenecek_kalip": len(kaliplar),
            "mesaj": ("Iptal edilecek."
                      + (" Ucret cari hesaba IADE EDILECEK."
                         if durum.iade_edilir
                         else " Kilif basildigi icin ucret IADE EDILMEYECEK.")),
        }

    ozet = bayii_iptal.uygula(db, o, kim=user.full_name or user.email,
                              sebep=(req.sebep or "").strip() or "Yonetici iptali")
    _iade_var = bool(ozet.get("iade"))
    if _iade_var:
        _iade_metni = " Ucret cari hesabina iade edildi."
    elif ozet["iade_edildi"]:
        _iade_metni = " Iade edilecek borc yoktu."
    else:
        _iade_metni = " Kilif basildigi icin ucret iade edilmedi."
    _bayiye_bildir(db, o, "Siparisin iptal edildi",
                   f"#{o.order_number} iptal edildi." + _iade_metni
                   + (f" Sebep: {req.sebep.strip()}" if (req.sebep or "").strip() else ""))
    db.commit()
    return {"ok": True, "iade_tutari_var": _iade_var, **ozet}


@router.get("/portal/iptal-talepleri", response_model=list[dict])
def portal_iptal_talepleri(
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    from app.services import bayii_iptal

    orders = db.scalars(
        select(Order).where(
            Order.tenant_id == user.tenant_id,
            Order.bayii_iptal_talebi == True,   # noqa: E712
            Order.is_iptal == False,            # noqa: E712
        ).options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
        .order_by(Order.created_at_platform.desc())
    ).all()
    bayiler = {str(d.id): d for d in db.scalars(
        select(Dealer).where(Dealer.tenant_id == user.tenant_id)).all()}

    out = []
    for o in orders:
        raw = o.raw or {}
        d = bayiler.get(str(raw.get("dealer_id") or ""))
        durum, kaliplar = bayii_iptal.durumu_oku(db, o)
        out.append({
            "id": str(o.id),
            "order_number": o.order_number,
            "bayi": d.name if d else "—",
            "musteri": o.customer_name,
            "sebep": o.bayii_iptal_sebep,
            "tarih": o.created_at_platform.isoformat() if o.created_at_platform else None,
            # Onaylanirsa NE OLACAGI onceden gosterilsin — yonetici korukorune
            # onaylamasin (kalip silme ve para iadesi geri alinmasi zor).
            "sonuc": {
                "iade_edilir": durum.iade_edilir,
                "kaliplar_silinir": durum.kaliplar_silinir,
                "kalip_basildi": durum.basilmis_kalip_var,
                "kaliplar": [{"kod": m.kod, "asama": m.current_stage} for m in kaliplar],
            },
            "kalemler": [{
                "model": li.device_model_override,
                "adet": li.quantity or 1,
                "gorsel": storage.get_thumbnail_url(
                    li.assigned_design.file_path, li.assigned_design.file_format)
                if li.assigned_design else None,
            } for li in sorted(o.line_items or [], key=lambda x: x.position or 0)],
        })
    return out


@router.post("/portal/iptal-talepleri/{order_id}", response_model=dict)
def portal_iptal_onayla(
    order_id: uuid.UUID,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Iptal talebini ONAYLA: kural app.services.bayii_iptal'de."""
    from app.services import bayii_iptal, push

    o = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id,
    ).options(selectinload(Order.line_items)))
    if not o:
        raise HTTPException(404, "Siparis bulunamadi")
    if not o.bayii_iptal_talebi:
        raise HTTPException(409, "Bu siparis icin acik bir iptal talebi yok")

    ozet = bayii_iptal.uygula(db, o, kim=user.full_name or user.email,
                              sebep=o.bayii_iptal_sebep)
    _bayiye_bildir(db, o, "Iptal talebin onaylandi",
                   f"#{o.order_number} iptal edildi."
                   + (" Ucret cari hesabina iade edildi."
                      if ozet["iade_edildi"] else
                      " Kilif basildigi icin ucret iade edilmedi."))
    db.commit()
    return {"ok": True, **ozet}


@router.delete("/portal/iptal-talepleri/{order_id}", response_model=dict)
def portal_iptal_reddet(
    order_id: uuid.UUID,
    user: User = Depends(require_permission("bayii")),
    db: Session = Depends(get_db),
):
    """Iptal talebini REDDET — siparis uretimde kalir."""
    o = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id))
    if not o or not o.bayii_iptal_talebi:
        raise HTTPException(404, "Acik talep bulunamadi")
    o.bayii_iptal_talebi = False
    db.add(OrderStatusHistory(
        tenant_id=o.tenant_id, order_id=o.id,
        from_stage=o.current_stage, to_stage=o.current_stage,
        action="bayii_iptal_reddedildi", note="Iptal talebi reddedildi",
        created_by=user.full_name or user.email,
    ))
    _bayiye_bildir(db, o, "Iptal talebin reddedildi",
                   f"#{o.order_number} uretimde devam ediyor.")
    db.commit()
    return {"ok": True}


def _bayiye_bildir(db: Session, o: Order, baslik: str, govde: str) -> None:
    """Siparisin bayisinin kullanicilarina push. Hata ana islemi dusurmemeli."""
    try:
        from app.services import push
        dealer_id = (o.raw or {}).get("dealer_id")
        if not dealer_id:
            return
        for u in db.scalars(select(User).where(
                User.dealer_id == uuid.UUID(str(dealer_id)))).all():
            push.send_to_user(db, u.id, baslik, govde, url=f"/bayii/siparis/{o.id}")
    except Exception:  # noqa: BLE001
        pass


# ─── Bayi portali: giris hesaplari ──────────────────────────
# Bayi hesabi GENEL kullanici ekranindan degil buradan acilir: rol ve izin
# ZORLA sabitlenir. Rolu 'yonetici' olan bir kullaniciya dealer_id verilseydi
# permissions.is_admin() yuzunden TUM panellere erisirdi.
BAYI_ROL = "bayii_portal"
BAYI_IZIN = ["bayii_portal"]


class BayiHesapIn(BaseModel):
    # EmailStr: login semasi da EmailStr kullaniyor. Burada duz str birakilsaydi
    # login'in reddettigi bir adresle (ornegin .test/.local gibi ayrilmis alan
    # adlari) hesap acilir, bayi HIC giris yapamazdi.
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    full_name: str | None = None


def _ser_hesap(u: User) -> dict:
    return {"id": str(u.id), "email": u.email, "full_name": u.full_name,
            "is_active": bool(u.is_active),
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}


@router.get("/{dealer_id}/hesaplar", response_model=list[dict])
def bayi_hesaplari(dealer_id: uuid.UUID,
                   user: User = Depends(require_permission("bayii")),
                   db: Session = Depends(get_db)):
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    return [_ser_hesap(u) for u in db.scalars(
        select(User).where(User.dealer_id == d.id).order_by(User.created_at)).all()]


@router.post("/{dealer_id}/hesaplar", response_model=dict, status_code=201)
def bayi_hesap_ekle(dealer_id: uuid.UUID, req: BayiHesapIn,
                    user: User = Depends(require_permission("bayii")),
                    db: Session = Depends(get_db)):
    from app.auth.security import hash_password

    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayii bulunamadi")
    _ensure_store(db, user.tenant_id, d)   # portal siparisi bu store'a yazilacak
    email = req.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Bu e-posta zaten kayitli")
    u = User(
        tenant_id=user.tenant_id, email=email,
        password_hash=hash_password(req.password),
        full_name=(req.full_name or d.name).strip(),
        role=BAYI_ROL, permissions=list(BAYI_IZIN),
        dealer_id=d.id, is_active=True,
    )
    db.add(u)
    db.commit(); db.refresh(u)
    return _ser_hesap(u)


class BayiHesapGuncelle(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=200)
    full_name: str | None = None
    is_active: bool | None = None


@router.patch("/{dealer_id}/hesaplar/{user_id}", response_model=dict)
def bayi_hesap_guncelle(dealer_id: uuid.UUID, user_id: uuid.UUID, req: BayiHesapGuncelle,
                        user: User = Depends(require_permission("bayii")),
                        db: Session = Depends(get_db)):
    from app.auth.security import hash_password

    u = db.scalar(select(User).where(
        User.id == user_id, User.dealer_id == dealer_id, User.tenant_id == user.tenant_id))
    if not u:
        raise HTTPException(404, "Hesap bulunamadi")
    if req.password:
        u.password_hash = hash_password(req.password)
    if req.full_name is not None:
        u.full_name = req.full_name.strip()
    if req.is_active is not None:
        u.is_active = bool(req.is_active)
    # Rol/izin her guncellemede sabitlenir: elle yukseltilmis olsa bile geri iner
    u.role, u.permissions = BAYI_ROL, list(BAYI_IZIN)
    db.commit(); db.refresh(u)
    return _ser_hesap(u)


@router.delete("/{dealer_id}/hesaplar/{user_id}", response_model=dict)
def bayi_hesap_sil(dealer_id: uuid.UUID, user_id: uuid.UUID,
                   user: User = Depends(require_permission("bayii")),
                   db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(
        User.id == user_id, User.dealer_id == dealer_id, User.tenant_id == user.tenant_id))
    if not u:
        raise HTTPException(404, "Hesap bulunamadi")
    db.delete(u)
    db.commit()
    return {"ok": True}
