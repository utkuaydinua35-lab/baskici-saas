"""Kiracının kendi aboneliği — /api/abonelik

Plan, ödeme durumu, bir sonraki ödemenin tahmini tutarı, havale bilgileri ve
ödeme geçmişi. Salt okunur: ödemeyi yalnız platform yöneticisi kaydeder
(routers/platform.py). Askıdaki kiracı da görebilmeli — nasıl ödeyeceğini
buradan öğreniyor; GET abonelik kapısına takılmaz.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.config import get_settings
from app.database import get_db
from app.models import AbonelikOdemesi, Tenant, User
from app.services import abonelik, abonelik_kart

logger = logging.getLogger("abonelik")

router = APIRouter(prefix="/api/abonelik", tags=["abonelik"])


@router.get("", response_model=dict)
def benim_aboneligim(
    ay_sayisi: int = 1,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    from app.routers.platform import _ser_odeme

    t = db.get(Tenant, user.tenant_id)
    plan = t.plan_kaydi if t else None
    try:
        tahmin = abonelik.tahakkuk_hesapla(db, t, max(1, min(12, ay_sayisi))).sozluk() if t else None
    except ValueError:
        tahmin = None
    odemeler = db.scalars(
        select(AbonelikOdemesi)
        .where(AbonelikOdemesi.tenant_id == user.tenant_id,
               AbonelikOdemesi.durum == "odendi")
        .order_by(AbonelikOdemesi.created_at.desc()).limit(36)
    ).all()
    ucretli = bool(plan and (plan.aylik_ucret or plan.komisyon_orani))
    return {
        "plan": {
            "ad": plan.ad, "aylik_ucret": str(plan.aylik_ucret),
            "komisyon_orani": str(plan.komisyon_orani),
            "moduller": [abonelik.MODUL_ADLARI[m] for m in abonelik.plan_modulleri(t)],
        } if plan else None,
        "active_until": t.active_until.isoformat() if t and t.active_until else None,
        "durum": abonelik.durum(t).sozluk(),
        # Ücretsiz planda tahmin ve havale bilgisi gösterilmez
        "tahmin": tahmin if ucretli else None,
        "havale": abonelik.havale_bilgisi(db) if ucretli else None,
        # Havale açıklamasına yazılacak kod — ödemeyi kiracıyla eşleştirmek için
        "odeme_kodu": t.slug if t else None,
        # Platformun iyzico anahtarları girilmişse "Kartla öde" görünür
        "kart_acik": bool(ucretli and abonelik_kart.acik_mi()),
        "odemeler": [_ser_odeme(o, plan.ad if plan and o.plan_id == plan.id else None)
                     for o in odemeler],
    }


# ─── Kartla ödeme (Faz 4) ──────────────────────────────────────────────────

class KartRequest(BaseModel):
    ay_sayisi: int = Field(1, ge=1, le=12)
    # Ekranda gösterilen toplam — arada değiştiyse kiracı görmediği tutarı ödemesin
    beklenen_toplam: Decimal


@router.post("/kart", response_model=dict)
def kartla_ode(
    req: KartRequest, request: Request,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Tutarı dondur, iyzico ödeme sayfası aç. Salt-okunur / askıdaki kiracı
    da çağırabilir (ABONELIK_YAZMA_ACIK) — borcunu ödeyebilmeli."""
    if not abonelik_kart.acik_mi():
        raise HTTPException(503, "Kartla ödeme henüz açık değil; havale ile ödeyebilirsiniz.")
    t = db.get(Tenant, user.tenant_id)
    try:
        kayit = abonelik.kart_odemesi_hazirla(
            db, t, ay_sayisi=req.ay_sayisi, beklenen_toplam=req.beklenen_toplam,
            kaydeden_id=user.id)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    try:
        ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else None)
        url = abonelik_kart.odeme_baslat(kayit, t, user, istemci_ip=ip)
    except Exception as e:  # noqa: BLE001 — sağlayıcı hatası kiracıya sade mesaj
        kayit.durum = "basarisiz"
        kayit.not_ = f"Başlatılamadı: {str(e)[:300]}"
        db.commit()
        logger.warning("[abonelik] kart ödemesi başlatılamadı (%s): %s", t.slug, e)
        raise HTTPException(502, "Ödeme sayfası açılamadı, lütfen biraz sonra tekrar deneyin.")
    return {"url": url}


@router.post("/kart/donus/{kayit_id}")
def kart_donus(kayit_id: uuid.UUID, token: str = Form(""), db: Session = Depends(get_db)):
    """iyzico ödeme sonrası tarayıcıyı buraya POST'lar. KİMLİK DOĞRULAMASIZ —
    güven yalnız iyzico'ya sunucudan sorulan doğrulamadan gelir (tutar,
    conversationId = kayıt kimliği, durum). Sonuç panele yönlendirilir."""
    panel = get_settings().magaza_panel_url.rstrip("/")

    def git(sonuc: str) -> RedirectResponse:
        return RedirectResponse(f"{panel}/abonelik?odeme={sonuc}", status_code=303)

    kayit = db.get(AbonelikOdemesi, kayit_id)
    if kayit is None or kayit.yontem != "kart":
        return git("hata")
    if kayit.durum == "odendi":          # tarayıcı iki kez döndüyse
        return git("basarili")
    sonuc = abonelik_kart.dogrula(kayit, {"token": token})
    if sonuc.status != "paid":
        if kayit.durum == "bekliyor":
            kayit.durum = "basarisiz"
            kayit.not_ = (sonuc.error or "ödeme onaylanmadı")[:300]
            db.commit()
        return git("hata")

    tutarli = abonelik.kart_odemesini_tamamla(db, kayit, saglayici_ref=sonuc.provider_ref or token)
    db.commit()
    t = db.get(Tenant, kayit.tenant_id)
    from app.services import telegram
    telegram.send_message(
        f"💳 <b>Abonelik kartla ödendi</b>\n{escape(t.name)} · {kayit.toplam} TL\n"
        f"Yeni bitiş: {kayit.yeni_bitis:%d.%m.%Y}"
        + ("" if tutarli else "\n⚠ <b>İnceleme gerekli</b>: ödeme sırasında başka ödeme işlenmiş, "
                             "komisyon dönemi çakışıyor olabilir."))
    return git("basarili")
