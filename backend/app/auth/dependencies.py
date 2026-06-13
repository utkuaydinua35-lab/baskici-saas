"""
FastAPI dependency'leri:

- get_current_user: JWT'den user'ı çek, DB'den hidrate et
- get_current_tenant: user.tenant_id'den tenant'ı çek
- TenantContext: request.state.tenant_id (DB sorgularında kullanmak için)

Korumalı endpoint:
    @router.get("/orders")
    def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return db.scalars(select(Order).where(Order.tenant_id == user.tenant_id)).all()
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import safe_decode
from app.database import get_db
from app.models import Tenant, User

# HTTPBearer header'dan "Authorization: Bearer <token>" alır
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """JWT'yi doğrula, user'ı döndür. Token yok/geçersizse 401."""
    if not creds or creds.scheme.lower() != "bearer":
        raise _unauthorized("Bearer token gerekli")

    payload = safe_decode(creds.credentials)
    if not payload:
        raise _unauthorized("Geçersiz veya süresi dolmuş token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise _unauthorized("Token'da kullanıcı bilgisi yok")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise _unauthorized("Geçersiz token formatı") from None

    user = db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise _unauthorized("Kullanıcı bulunamadı veya pasif")

    # Tenant izolasyonu için request.state'e yaz — log/audit için faydalı
    request.state.user_id = user.id
    request.state.tenant_id = user.tenant_id

    return user


def get_current_tenant(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tenant:
    """Aktif tenant'ı döndür. Abonelik biti, aktif değil vs. kontrolü burada."""
    tenant = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant bulunamadı",
        )
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap pasif. Lütfen yöneticiyle iletişime geçin.",
        )
    # active_until kontrolü ileride: abonelik bittiyse read-only mod vs.
    return tenant


def require_role(*allowed: str):
    """Belirli rolleri zorla. Örn: require_role("owner")."""
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için yetki yok. Gerekli rol: {', '.join(allowed)}",
            )
        return user
    return dep


from app.auth import permissions as _perms  # esnek yetki sistemi


def require_permission(perm: str):
    """Panel yetkisi zorla. Yonetici her zaman gecer. Orn: require_permission('kalip')."""
    def dep(user: User = Depends(get_current_user)) -> User:
        if not _perms.has_permission(user, perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu panel icin yetkin yok: {perm}",
            )
        return user
    return dep
