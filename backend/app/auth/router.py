"""
Auth router — /api/auth/*

Endpoints:
- POST /register   → yeni tenant + owner user + JWT
- POST /login      → JWT
- GET  /me         → mevcut kullanıcı + tenant bilgisi
- POST /logout     → istemci token'ı silsin (server-side no-op şimdilik)
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_tenant, get_current_user
from app.auth.schemas import (
    AuthMeResponse,
    LoginRequest,
    RegisterRequest,
    TenantResponse,
    TokenResponse,
    UserResponse,
    slugify,
)
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.config import get_settings
from app.database import get_db
from app.models import Tenant, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

settings = get_settings()


def _issue_token(user: User) -> TokenResponse:
    """User için JWT üret + response paketi."""
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Yeni hesap aç:
    - Yeni Tenant oluştur (plan=trial)
    - Yeni User oluştur (role=owner)
    - JWT döndür

    Email zaten kayıtlıysa 409 Conflict.
    Tenant slug çakışırsa otomatik suffix eklenir.
    """
    # Email zaten var mı?
    existing = db.scalar(select(User).where(User.email == req.email.lower()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu email zaten kayıtlı. Giriş yapmayı dene.",
        )

    # Tenant slug üret
    base_slug = slugify(req.tenant_name)
    if not base_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçerli bir firma adı gir",
        )

    # Slug çakışıyorsa suffix ekle (-2, -3, ...)
    slug = base_slug
    suffix = 2
    while db.scalar(select(Tenant).where(Tenant.slug == slug)):
        slug = f"{base_slug}-{suffix}"
        suffix += 1
        if suffix > 100:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Slug üretilemedi, firma adını değiştir",
            )

    # Tenant
    tenant = Tenant(name=req.tenant_name, slug=slug, plan="trial", is_active=True)
    db.add(tenant)
    db.flush()  # tenant.id elde edilsin

    # User
    user = User(
        tenant_id=tenant.id,
        email=req.email.lower(),
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role="owner",
        is_active=True,
        last_login_at=datetime.now(UTC),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıt sırasında çakışma — büyük ihtimalle email kullanılıyor",
        ) from e

    db.refresh(user)
    return _issue_token(user)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Email + şifre ile giriş. Yanlış bilgi → 401."""
    user = db.scalar(select(User).where(User.email == req.email.lower()))
    if not user or not user.password_hash:
        # password_hash null = sadece OAuth user, email/şifre giriş yok
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre hatalı",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre hatalı",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap pasif. Yöneticiyle iletişime geç.",
        )

    user.last_login_at = datetime.now(UTC)
    db.commit()

    return _issue_token(user)


@router.get("/me", response_model=AuthMeResponse)
def me(
    user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
) -> AuthMeResponse:
    """Mevcut kullanıcı + tenant bilgisi (frontend init için)."""
    return AuthMeResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> None:
    """
    Server-side logout no-op — JWT stateless, istemci token'ı silmeli.
    İleride: refresh token blacklist eklenebilir.
    """
    return None


from pydantic import BaseModel as _PwBaseModel  # 13a

class _VerifyPasswordRequest(_PwBaseModel):
    password: str

class _ChangePasswordRequest(_PwBaseModel):
    current_password: str
    new_password: str

@router.post("/verify-password", response_model=None)
def verify_password_endpoint(
    req: _VerifyPasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Şifre yanlış")
    return {"ok": True}

@router.post("/change-password", response_model=None)
def change_password_endpoint(
    req: _ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.password_hash or not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Mevcut şifre yanlış")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 8 karakter olmalı")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"ok": True}
