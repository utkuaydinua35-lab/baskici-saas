"""Masaüstü uygulaması kurulumları — YÖNETİM tarafı (/api/masaustu).

Bayi tarafı /api/bayii/uygulama; ikisi de aynı servisi (bayi_uygulama) ve aynı
klasörü okur, yalnız profil değişir. Bayi hesapları bu yola giremez (kapı
varsayılan RED).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.models import User
from app.services import bayi_uygulama as bu

router = APIRouter(prefix="/api/masaustu", tags=["masaustu"])


@router.get("/kurulumlar", response_model=dict)
def kurulumlar(profil: str = Query("studio"), user: User = Depends(get_current_user)):
    """Yayındaki kurulum dosyaları. profil: studio (yönetim) | bayi"""
    if profil not in bu.KALIPLAR:
        raise HTTPException(400, "Geçersiz profil")
    kayitlar = bu.kurulumlar(profil)
    return {
        "profil": profil,
        "kurulumlar": kayitlar,
        "son_surum": bu.son_surum(kayitlar, profil),
        "mac": [k for k in kayitlar if k["platform"] == "mac"],
        "windows": [k for k in kayitlar if k["platform"] == "windows"],
    }
