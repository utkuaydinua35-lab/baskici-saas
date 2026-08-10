"""Entegrasyon API'si — dış sistemler siparişleri BURADAN okur.

Shopify'ın "Admin API"si ne işi görüyorsa bu da onu görür: e-fatura
entegratörü (Birfatura, Nilvera, İzibiz…) ya da muhasebe yazılımı, kendi
tarafından periyodik olarak buraya bağlanır, faturalanmamış siparişleri
çeker, faturayı keser ve sonucu geri yazar.

    GET  /api/entegrasyon/v1/saglik                       → bağlantı testi
    GET  /api/entegrasyon/v1/siparisler?durum=faturasiz   → liste
    GET  /api/entegrasyon/v1/siparisler/{no}              → tek sipariş
    POST /api/entegrasyon/v1/siparisler/{no}/fatura       → sonucu geri yaz

KİMLİK: `Authorization: Bearer <anahtar>`. Anahtar panelden üretilir, yalnız
özeti saklanır (bkz. models.IntegrationKey) ve TEK mağazaya bağlıdır.

GÜVENLİK SINIRLARI
  • Salt okunur — tek yazma ucu fatura bilgisidir; sipariş/ürün/fiyat
    değiştirilemez, silinemez.
  • Yalnız ÖDENMİŞ, iptal edilmemiş ve silinmemiş siparişler görünür.
  • Kart verisi, ödeme sağlayıcı sırları ve müşteri şifreleri dönmez.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func as sql_func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import IntegrationKey, Order, Store
from app.services import fatura as fatura_svc
from app.services.rate_limit import make_rate_limiter

log = logging.getLogger("entegrasyon")

router = APIRouter(prefix="/api/entegrasyon/v1", tags=["entegrasyon"])

# Entegratörler dakikada bir yoklar; cömert ama sınırsız değil
entegrasyon_rate_limit = make_rate_limiter(max_hits=120, window=60.0)

DURUMLAR = {"beklemede", "kesildi", "hata", "iptal"}


def anahtar_ozeti(ham: str) -> str:
    return hashlib.sha256(ham.strip().encode()).hexdigest()


def _anahtar(
    request: Request,
    authorization: str = Header(default=""),
    _rl: None = Depends(entegrasyon_rate_limit),
    db: Session = Depends(get_db),
) -> IntegrationKey:
    """Bearer anahtarını doğrula ve son kullanımı işaretle."""
    ham = authorization.removeprefix("Bearer ").removeprefix("bearer ").strip()
    if not ham:
        raise HTTPException(401, "Authorization: Bearer <anahtar> gerekli")
    k = db.scalar(select(IntegrationKey).where(
        IntegrationKey.key_hash == anahtar_ozeti(ham),
        IntegrationKey.is_active.is_(True),
        IntegrationKey.revoked_at.is_(None),
    ))
    if not k:
        raise HTTPException(401, "Anahtar geçersiz ya da iptal edilmiş")
    # Panelde "en son ne zaman bağlandı" görünsün (kurulum hatası teşhisi)
    k.last_used_at = datetime.now(UTC)
    k.last_used_ip = (request.client.host if request.client else None)
    db.commit()
    return k


def _siparis_sorgusu(store_id):
    """Faturalanabilir siparişler: ödenmiş, iptal edilmemiş.
    (Silinmişleri global ORM filtresi zaten gizler.)"""
    return (
        select(Order)
        .where(Order.store_id == store_id,
               Order.is_iptal.is_(False),
               Order.cancelled_at.is_(None),
               Order.financial_status == "paid")
        .options(selectinload(Order.line_items))
    )


@router.get("/saglik")
def saglik(k: IntegrationKey = Depends(_anahtar), db: Session = Depends(get_db)):
    """Entegratör kurulumunda 'bağlantı testi' için — anahtar geçerli mi?"""
    store = db.get(Store, k.store_id)
    bekleyen = db.scalar(select(sql_func.count()).select_from(
        _siparis_sorgusu(k.store_id)
        .where(Order.fatura_durum.is_(None)).subquery()))
    return {
        "ok": True,
        "magaza": store.name if store else None,
        "anahtar": k.label,
        "faturasiz_siparis": int(bekleyen or 0),
        "sunucu_zamani": datetime.now(UTC).isoformat(),
    }


@router.get("/siparisler")
def siparisler(
    durum: str = Query("faturasiz", pattern="^(faturasiz|hepsi)$"),
    since: datetime | None = Query(None, description="Bu tarihten sonrakiler (ISO 8601)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    k: IntegrationKey = Depends(_anahtar),
    db: Session = Depends(get_db),
):
    """Faturalanacak siparişler — en eskisi önce (fatura sırası bozulmasın)."""
    q = _siparis_sorgusu(k.store_id)
    if durum == "faturasiz":
        # "hata" olanlar da tekrar denensin diye listede kalır
        q = q.where(Order.fatura_durum.is_(None) | (Order.fatura_durum == "hata"))
    if since:
        q = q.where(Order.created_at_platform >= since)
    q = q.order_by(Order.created_at_platform.asc()).offset(offset).limit(limit)

    store = db.get(Store, k.store_id)
    kayitlar = list(db.scalars(q))
    return {
        "toplam_donen": len(kayitlar),
        "limit": limit,
        "offset": offset,
        # Sayfa doluysa devamı var demektir — entegratör offset'i ilerletir
        "devam_var": len(kayitlar) == limit,
        "siparisler": [fatura_svc.fatura_verisi(o, store) for o in kayitlar],
    }


@router.get("/siparisler/{siparis_no}")
def siparis(siparis_no: str, k: IntegrationKey = Depends(_anahtar),
            db: Session = Depends(get_db)):
    o = db.scalar(_siparis_sorgusu(k.store_id).where(Order.order_number == siparis_no))
    if not o:
        raise HTTPException(404, "Sipariş bulunamadı")
    return fatura_svc.fatura_verisi(o, db.get(Store, k.store_id))


class FaturaSonucu(BaseModel):
    """Entegratörün fatura kestikten sonra geri yazdığı bilgi."""
    durum: str = Field(..., pattern="^(beklemede|kesildi|hata|iptal)$")
    no: str | None = Field(None, max_length=40)          # ör. BRN2026000000123
    ettn: str | None = Field(None, max_length=64)        # GİB tekil numarası
    tarih: datetime | None = None
    pdf_url: str | None = Field(None, max_length=500)
    kaynak: str | None = Field(None, max_length=40)      # "birfatura" …
    hata: str | None = Field(None, max_length=500)


@router.post("/siparisler/{siparis_no}/fatura")
def fatura_yaz(
    siparis_no: str,
    govde: FaturaSonucu,
    k: IntegrationKey = Depends(_anahtar),
    db: Session = Depends(get_db),
):
    """Fatura sonucunu siparişe işle — panelde görünür, tekrar listelenmez."""
    o = db.scalar(_siparis_sorgusu(k.store_id).where(Order.order_number == siparis_no))
    if not o:
        raise HTTPException(404, "Sipariş bulunamadı")
    if govde.durum == "kesildi" and not (govde.no or govde.ettn):
        raise HTTPException(422, "Kesilen fatura için no ya da ettn gerekli")

    o.fatura_durum = govde.durum
    o.fatura = {
        "no": govde.no,
        "ettn": govde.ettn,
        "tarih": govde.tarih.isoformat() if govde.tarih else None,
        "pdf_url": govde.pdf_url,
        "kaynak": govde.kaynak or k.label,
        "hata": govde.hata,
        "islendi": datetime.now(UTC).isoformat(),
    }
    db.commit()
    log.info("fatura yazildi: siparis=%s durum=%s no=%s kaynak=%s",
             siparis_no, govde.durum, govde.no, k.label)
    return {"ok": True, "siparis_no": siparis_no, "fatura_durum": o.fatura_durum}
