"""Kiracının kendi aboneliği — /api/abonelik

Plan, ödeme durumu, bir sonraki ödemenin tahmini tutarı, havale bilgileri ve
ödeme geçmişi. Salt okunur: ödemeyi yalnız platform yöneticisi kaydeder
(routers/platform.py). Askıdaki kiracı da görebilmeli — nasıl ödeyeceğini
buradan öğreniyor; GET abonelik kapısına takılmaz.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import AbonelikOdemesi, Tenant, User
from app.services import abonelik

router = APIRouter(prefix="/api/abonelik", tags=["abonelik"])


@router.get("", response_model=dict)
def benim_aboneligim(
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    from app.routers.platform import _ser_odeme

    t = db.get(Tenant, user.tenant_id)
    plan = t.plan_kaydi if t else None
    try:
        tahmin = abonelik.tahakkuk_hesapla(db, t).sozluk() if t else None
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
        "odemeler": [_ser_odeme(o, plan.ad if plan and o.plan_id == plan.id else None)
                     for o in odemeler],
    }
