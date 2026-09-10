"""BERNZ Special stok listesi yönetimi — /api/ozel-seri/*

Special yalnız birkaç modelde stok bulunduruyor. Model değişikliği bağlantısı
(public_model_degisim) PARLAK ürünlerde YALNIZ bu listeyi gösteriyor; buradaki
`stokta` işareti müşterinin neyi seçebileceğini doğrudan belirliyor.

Liste tenant başına; ilk okumada varsayılanla doldurulur (services/ozel_seri.py).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import OzelSeriStok, User
from app.services import ozel_seri as svc

router = APIRouter(prefix="/api/ozel-seri", tags=["ozel-seri"])


def _cikti(r: OzelSeriStok) -> dict:
    return {"id": str(r.id), "model": r.model, "sira": r.sira, "stokta": bool(r.stokta),
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}


@router.get("/stok", response_model=dict)
def stok_listesi(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": [_cikti(r) for r in svc.liste(db, user.tenant_id)]}


class StokGuncelle(BaseModel):
    stokta: bool


@router.patch("/stok/{kayit_id}", response_model=dict)
def stok_guncelle(kayit_id: uuid.UUID, body: StokGuncelle,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(OzelSeriStok).where(
        OzelSeriStok.id == kayit_id, OzelSeriStok.tenant_id == user.tenant_id))
    if not r:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    r.stokta = bool(body.stokta)
    db.commit()
    return _cikti(r)


class ModelEkle(BaseModel):
    model: str


@router.post("/stok", response_model=dict)
def stok_ekle(body: ModelEkle,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services import phone_models as pm

    ad = (body.model or "").strip()
    if not ad:
        raise HTTPException(status_code=400, detail="Model adı boş olamaz")
    # ⚠ Kalıp motorunun TANIMADIĞI bir ad eklenirse müşteri onu seçer ve
    # sipariş "Model tanınmadı" ile kalıp dışında kalır.
    if not pm.has_spec(db, user.tenant_id, ad):
        raise HTTPException(status_code=400,
                            detail=f"'{ad}' kalıp ölçüsü tanınmıyor. Önce Telefon "
                                   f"Modelleri'nden ölçüsünü tanımlayın.")
    mevcut = db.scalar(select(OzelSeriStok).where(
        OzelSeriStok.tenant_id == user.tenant_id, OzelSeriStok.model == ad))
    if mevcut:
        raise HTTPException(status_code=409, detail="Bu model zaten listede")

    enson = db.scalar(select(OzelSeriStok.sira).where(
        OzelSeriStok.tenant_id == user.tenant_id).order_by(OzelSeriStok.sira.desc()))
    r = OzelSeriStok(tenant_id=user.tenant_id, model=ad,
                     sira=(enson or 0) + 1, stokta=True)
    db.add(r)
    db.commit()
    return _cikti(r)


@router.delete("/stok/{kayit_id}", response_model=dict)
def stok_sil(kayit_id: uuid.UUID,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(OzelSeriStok).where(
        OzelSeriStok.id == kayit_id, OzelSeriStok.tenant_id == user.tenant_id))
    if r:
        db.delete(r)
        db.commit()
    return {"ok": True}
