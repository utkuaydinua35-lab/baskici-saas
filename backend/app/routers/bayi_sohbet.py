"""Bayi sohbeti — YÖNETİM tarafı (/api/bayi-sohbet).

Bayi tarafı /api/bayii/portal/sohbet altında; iki uç da AYNI servisi
(services/bayi_sohbet) kullanır, kurallar kopyalanmaz.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import BayiSohbet, Dealer, Order, User
from app.services import bayi_sohbet as bs

router = APIRouter(prefix="/api/bayi-sohbet", tags=["bayi_sohbet"],
    dependencies=[Depends(require_permission("bayii"))],
)


def _bayi(db: Session, dealer_id: uuid.UUID, user: User) -> Dealer:
    d = db.scalar(select(Dealer).where(Dealer.id == dealer_id,
                                       Dealer.tenant_id == user.tenant_id))
    if d is None:
        raise HTTPException(404, "Bayi bulunamadı")
    return d


class MesajIn(BaseModel):
    body: str | None = Field(None, max_length=4000)
    image_url: str | None = Field(None, max_length=500)
    order_id: uuid.UUID | None = None
    aciliyet: str = "normal"


@router.get("", response_model=dict)
def liste(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tüm bayilerin sohbet özeti — okunmamışlar ve ACİL olanlar üstte."""
    bayiler = db.scalars(select(Dealer).where(Dealer.tenant_id == user.tenant_id)
                         .order_by(Dealer.name)).all()
    sohbetler = {s.dealer_id: s for s in db.scalars(
        select(BayiSohbet).where(BayiSohbet.tenant_id == user.tenant_id)).all()}
    satirlar = [bs.ser_sohbet(sohbetler.get(d.id), d) for d in bayiler]
    satirlar.sort(key=lambda x: (
        not x["acil_bekliyor"],                 # acil olanlar en üstte
        not x["okunmamis_atolye"],              # sonra okunmamışı olanlar
        x["son_mesaj_at"] is None,              # hiç konuşulmamışlar en sonda
        -(datetime.fromisoformat(x["son_mesaj_at"]).timestamp() if x["son_mesaj_at"] else 0),
        x["dealer_ad"].lower(),
    ))
    return {
        "items": satirlar,
        "okunmamis_toplam": sum(x["okunmamis_atolye"] for x in satirlar),
        "acil_sayisi": sum(1 for x in satirlar if x["acil_bekliyor"]),
    }


@router.get("/{dealer_id}", response_model=dict)
def mesajlar(dealer_id: uuid.UUID, limit: int = Query(200, le=500),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = _bayi(db, dealer_id, user)
    sh = bs.sohbet_bul(db, d, olustur=False)
    return {"mesajlar": bs.mesajlari_getir(db, d, limit=limit),
            "sohbet": bs.ser_sohbet(sh, d),
            "bayi": {"id": str(d.id), "ad": d.name, "telefon": d.phone, "eposta": d.email}}


@router.get("/{dealer_id}/siparisler", response_model=dict)
def bayinin_siparisleri(dealer_id: uuid.UUID, limit: int = Query(200, le=500),
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Yanıta sipariş iliştirmek için bu bayinin siparişleri (yeniden eskiye).

    Süzgeç bayi portalındaki ile AYNI (_bayinin_sql_suzgeci) — iki yerde iki
    farklı "bu bayinin siparişi" tanımı olmasın.
    """
    from app.routers.bayii_portal import _bayinin_sql_suzgeci
    from app.stages import stage_label

    d = _bayi(db, dealer_id, user)
    satirlar = db.scalars(
        select(Order).where(_bayinin_sql_suzgeci(d))
        .order_by(Order.created_at_platform.desc().nullslast(), Order.id.desc())
        .limit(limit)
    ).all()
    return {"items": [{
        "id": str(o.id),
        "order_number": o.order_number,
        "musteri": o.customer_name,
        "tarih": o.created_at_platform.isoformat() if o.created_at_platform else None,
        "asama_adi": stage_label(o.current_stage or 1),
    } for o in satirlar]}


@router.post("/{dealer_id}", response_model=dict)
def yaz(dealer_id: uuid.UUID, body: MesajIn,
        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = _bayi(db, dealer_id, user)
    if not (body.body or "").strip() and not body.image_url:
        raise HTTPException(400, "Boş mesaj gönderilemez")
    order = None
    if body.order_id is not None:
        order = db.scalar(select(Order).where(Order.id == body.order_id,
                                              Order.tenant_id == user.tenant_id))
        if order is None:
            raise HTTPException(404, "Sipariş bulunamadı")
    m = bs.mesaj_ekle(db, d, gonderen=bs.ATOLYE, body=body.body, image_url=body.image_url,
                      order=order, aciliyet=body.aciliyet,
                      gonderen_ad=(user.full_name or user.email))
    db.commit()
    return bs.ser_mesaj(m, avatarlar=bs.avatarlar(db, d))


@router.post("/{dealer_id}/okundu", response_model=dict)
def okundu(dealer_id: uuid.UUID, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    d = _bayi(db, dealer_id, user)
    sayi = bs.okundu_isaretle(db, d, taraf=bs.ATOLYE)
    db.commit()
    return {"ok": True, "okundu": sayi}


@router.post("/gorsel/yukle", response_model=dict)
def gorsel(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """Sohbete görsel yükle — URL döner."""
    from app.services import uploads as uploads_service
    rel = uploads_service.save_image(file, klasor="bayi-sohbet")
    return {"url": uploads_service.public_url(rel)}
