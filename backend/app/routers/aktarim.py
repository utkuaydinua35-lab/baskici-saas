"""Cihazlar arası dosya aktarımı — /api/aktarim (YALNIZ yönetim paneli).

Bayi hesapları giremez: kapı varsayılan RED (bkz. auth/dependencies).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services import dosya_aktarimi as da

router = APIRouter(prefix="/api/aktarim", tags=["aktarim"])


def _ser(k) -> dict:
    return {
        "id": str(k.id),
        "dosya_adi": k.dosya_adi,
        "boyut": k.boyut,
        "boyut_yazi": da.boyut_yaz(k.boyut or 0),
        "tur": k.tur,
        "yukleyen": k.yukleyen,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "indir": f"/api/aktarim/{k.id}/indir",
    }


@router.get("", response_model=dict)
def liste(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Süresi dolmamış dosyalar + sınırlar (ekran bunları yazıyor)."""
    kayitlar = da.listele(db, user.tenant_id)
    return {
        "items": [_ser(k) for k in kayitlar],
        "max_boyut": da.MAX_BOYUT,
        "max_boyut_yazi": da.boyut_yaz(da.MAX_BOYUT),
        "saklama_saat": da.SAKLAMA_SAAT,
        "toplam_boyut_yazi": da.boyut_yaz(sum(k.boyut or 0 for k in kayitlar)),
    }


@router.post("", response_model=dict, status_code=201)
def yukle(file: UploadFile = File(...), user: User = Depends(get_current_user),
          db: Session = Depends(get_db)):
    """Dosya yükle. 24 saat sonra kendiliğinden silinir."""
    try:
        kayit = da.kaydet(db, tenant_id=user.tenant_id, user=user, dosya=file)
    except ValueError as e:
        raise HTTPException(413 if "büyük" in str(e) else 400, str(e)) from None
    except OSError as e:
        raise HTTPException(500, f"Dosya yazılamadı: {str(e)[:150]}") from None
    db.commit()
    db.refresh(kayit)
    return _ser(kayit)


@router.get("/{kayit_id}/indir")
def indir(kayit_id: uuid.UUID, user: User = Depends(get_current_user),
          db: Session = Depends(get_db)):
    """Dosyayı indir.

    nginx X-Accel-Redirect varsa dosyayı NGINX gönderir (250 MB'lık bir
    indirme uvicorn worker'ını dakikalarca meşgul etmesin); yoksa doğrudan
    FastAPI gönderir — geliştirmede ve nginx ayarı yapılmamış sunucuda da
    çalışsın diye.
    """
    from fastapi.responses import Response

    from app.config import get_settings

    kayit = da.bul(db, user.tenant_id, kayit_id)
    if kayit is None:
        raise HTTPException(404, "Dosya bulunamadı")
    yol = da.tam_yol(kayit)
    if not yol.exists():
        raise HTTPException(410, "Dosya artık yok (süresi dolmuş olabilir)")

    ad = kayit.dosya_adi or "dosya"
    if getattr(get_settings(), "nginx_x_accel", False):
        r = Response(status_code=200)
        r.headers["X-Accel-Redirect"] = f"/_dahili_aktarim/{yol.name}"
        r.headers["Content-Disposition"] = f'attachment; filename="{ad}"'
        r.headers["Content-Type"] = kayit.tur or "application/octet-stream"
        return r
    return FileResponse(yol, filename=ad,
                        media_type=kayit.tur or "application/octet-stream")


@router.delete("/{kayit_id}", status_code=204)
def sil(kayit_id: uuid.UUID, user: User = Depends(get_current_user),
        db: Session = Depends(get_db)):
    """Süresi dolmadan elle sil — yanlış dosya yüklendiyse beklemek gerekmesin."""
    kayit = da.bul(db, user.tenant_id, kayit_id)
    if kayit is None:
        raise HTTPException(404, "Dosya bulunamadı")
    da.sil(db, kayit)
    db.commit()
    return None
