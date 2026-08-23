"""BirFatura Özel Entegrasyon uçları — BirFatura BİZİ çağırır.

BirFatura panelinde "Özel Entegrasyon" mağazası tanımlanırken verilen
adrese bağlanıp aşağıdaki beş ucu POST'lar. API Şifresi `token` başlığında
gelir (panelde üretilen entegrasyon anahtarı), parametreler JSON gövdede.

Yollar BirFatura tarafından SABİTTİR; vitrin bunları
storefront/app/api/{orders,orderStatus,…}/route.ts üzerinden buraya
yönlendirir. Backend'de `/api/birfatura/...` altında dururlar; `/api/orders`
paneldeki sipariş yönetimine ait olduğu için oraya dokunulmaz.

Veri dönüşümü services/birfatura.py'de; burada yalnız HTTP + kimlik + yazma.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.services.site import site_url
from app.database import get_db
from app.models import IntegrationKey, Order, Store
from app.routers.entegrasyon import anahtar_ozeti, entegrasyon_rate_limit
from app.services import birfatura as bf

log = logging.getLogger("birfatura")

router = APIRouter(prefix="/api/birfatura", tags=["birfatura"])

MAX_SIPARIS = 500      # tek çağrıda dönecek sipariş tavanı


def _anahtar(
    request: Request,
    token: str = Header(default=""),
    authorization: str = Header(default=""),
    _rl: None = Depends(entegrasyon_rate_limit),
    db: Session = Depends(get_db),
) -> IntegrationKey:
    """`token` başlığı — BirFatura böyle gönderiyor. Elle denerken kolaylık
    olsun diye `Authorization: Bearer ...` de kabul edilir."""
    ham = (token or "").strip() or authorization.removeprefix("Bearer ").strip()
    if not ham:
        raise HTTPException(403, "Access forbidden")
    k = db.scalar(select(IntegrationKey).where(
        IntegrationKey.key_hash == anahtar_ozeti(ham),
        IntegrationKey.is_active.is_(True),
        IntegrationKey.revoked_at.is_(None),
    ))
    if not k:
        # Anahtarın varlığını belli etmemek için tek tip yanıt
        raise HTTPException(403, "Access forbidden")
    k.last_used_at = datetime.now(UTC)
    k.last_used_ip = (request.client.host if request.client else None)
    db.commit()
    return k


@router.post("/orderStatus")
def order_status(_k: IntegrationKey = Depends(_anahtar)):
    """Tanımlı sipariş durumlarımız — BirFatura 'hangi durumda fatura kesilsin'
    seçimini bu listeden yaptırır."""
    return bf.durum_listesi()


@router.post("/paymentMethods")
def payment_methods(_k: IntegrationKey = Depends(_anahtar)):
    return bf.odeme_listesi()


@router.post("/orders")
def orders(
    govde: dict = Body(default={}),
    k: IntegrationKey = Depends(_anahtar),
    db: Session = Depends(get_db),
):
    """Tarih aralığı + duruma göre siparişler (BirFatura Orders şeması)."""
    bas = bf.tarih_coz(govde.get("startDateTime"))
    bit = bf.tarih_coz(govde.get("endDateTime"))
    try:
        durum_id = int(govde.get("orderStatusId") or 0)
    except (TypeError, ValueError):
        durum_id = 0

    q = (select(Order)
         .where(Order.store_id == k.store_id)
         .options(selectinload(Order.line_items))
         .order_by(Order.created_at_platform.asc()))
    if bas:
        q = q.where(Order.created_at_platform >= bas)
    if bit:
        q = q.where(Order.created_at_platform <= bit)

    store = db.get(Store, k.store_id)
    kanal = site_url(store) if store else None

    cikti = []
    for o in db.scalars(q.limit(MAX_SIPARIS * 2)):
        # Vitrin dışı (elle/Shopify) siparişlerin numarası sayısal değil;
        # BirFatura OrderId'yi tam sayı ister ve faturayı onunla geri yazar
        if not str(o.order_number).isdigit():
            continue
        if not bf.durum_eslesir(o, durum_id):
            continue
        cikti.append(bf.siparis(o, store, kanal))
        if len(cikti) >= MAX_SIPARIS:
            break

    log.info("birfatura orders: durum=%s aralik=%s..%s → %d siparis",
             durum_id, bas, bit, len(cikti))
    return {"Orders": cikti}


def _siparis_bul(db: Session, store_id, order_id) -> Order | None:
    try:
        no = str(int(order_id))
    except (TypeError, ValueError):
        return None
    return db.scalar(select(Order).where(
        Order.store_id == store_id, Order.order_number == no))


@router.post("/invoiceLinkUpdate")
def invoice_link_update(
    govde: dict = Body(default={}),
    k: IntegrationKey = Depends(_anahtar),
    db: Session = Depends(get_db),
):
    """Kesilen faturayı siparişe işle — panelde görünür, tekrar kesilmez."""
    o = _siparis_bul(db, k.store_id, govde.get("orderId"))
    if not o:
        raise HTTPException(404, "Order not found")
    tarih = bf.tarih_coz(govde.get("faturaTarihi"))
    o.fatura_durum = "kesildi"
    o.fatura = {
        "no": (str(govde.get("faturaNo") or "").strip() or None),
        "ettn": None,
        "tarih": tarih.isoformat() if tarih else None,
        "pdf_url": (str(govde.get("faturaUrl") or "").strip() or None),
        "kaynak": k.label or "BirFatura",
        "hata": None,
        "islendi": datetime.now(UTC).isoformat(),
    }
    db.commit()
    log.info("birfatura fatura: siparis=%s no=%s", o.order_number,
             o.fatura.get("no"))
    return {}


@router.post("/orderCargoUpdate")
def order_cargo_update(
    govde: dict = Body(default={}),
    k: IntegrationKey = Depends(_anahtar),
    db: Session = Depends(get_db),
):
    """BirFatura'nın kargo takip kodu bildirimi (opsiyonel uç).

    Kargoyu biz kendimiz oluşturuyoruz; bu yüzden ELDEKİ takip no EZİLMEZ,
    yalnız boşsa doldurulur. Aksi hâlde dış sistem kendi kodunu yazıp
    müşteriye giden takip bağlantısını bozabilirdi.
    """
    o = _siparis_bul(db, k.store_id, govde.get("orderId"))
    if not o:
        raise HTTPException(404, "Order not found")
    kod = str(govde.get("cargoTrackingCode") or "").strip()
    mevcut = (o.kargo_info or {}).get("takip_no")
    if kod and not mevcut:
        bilgi = dict(o.kargo_info or {})
        bilgi.update({
            "takip_no": kod[:100],
            "takip_url": str(govde.get("cargoTrackingCodeUrl") or "").strip() or None,
            "handler_name": str(govde.get("cargoCompany") or "").strip() or None,
            "kaynak": "birfatura",
        })
        o.kargo_info = bilgi
        db.commit()
        log.info("birfatura kargo: siparis=%s takip=%s", o.order_number, kod)
    return {}
