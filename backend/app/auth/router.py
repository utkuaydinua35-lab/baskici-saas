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

from fastapi import APIRouter, Depends, HTTPException, Request, status
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


_login_hits: dict[str, list[float]] = {}
_LOGIN_WINDOW = 300   # 5 dakika
_LOGIN_MAX = 10       # IP basina 5 dakikada en fazla 10 basarisiz deneme


def _login_client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _login_rate_limit(request: Request) -> None:
    """Basarisiz giris denemelerini IP basina sinirla (brute-force korumasi)."""
    import time as _t
    ip = _login_client_ip(request)
    now = _t.time()
    arr = [x for x in _login_hits.get(ip, []) if now - x < _LOGIN_WINDOW]
    if len(arr) >= _LOGIN_MAX:
        raise HTTPException(429, "Çok fazla başarısız giriş denemesi. Lütfen birkaç dakika sonra tekrar deneyin.")
    _login_hits[ip] = arr
    if len(_login_hits) > 5000:
        for k in [k for k, v in _login_hits.items() if not v or now - v[-1] > _LOGIN_WINDOW]:
            _login_hits.pop(k, None)


def _login_record_fail(request: Request) -> None:
    import time as _t
    ip = _login_client_ip(request)
    _login_hits.setdefault(ip, []).append(_t.time())


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    _login_rate_limit(request)
    """Email + şifre ile giriş. Yanlış bilgi → 401."""
    user = db.scalar(select(User).where(User.email == req.email.lower()))
    if not user or not user.password_hash:
        # password_hash null = sadece OAuth user, email/şifre giriş yok
        _login_record_fail(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre hatalı",
        )

    if not verify_password(req.password, user.password_hash):
        _login_record_fail(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre hatalı",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap pasif. Yöneticiyle iletişime geç.",
        )

    # Abonelik kontrolü (white-label kiralama) — platform admin muaf
    if not user.is_platform_admin:
        tenant = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
        if tenant and not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Aboneliğiniz pasif durumda. Lütfen sağlayıcınızla iletişime geçin.",
            )
        if tenant and tenant.active_until and tenant.active_until < datetime.now(UTC).date():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Abonelik süreniz doldu. Lütfen sağlayıcınızla iletişime geçin.",
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


# ─── Şifre sıfırlama (e-posta ile) ───────────────────────────
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer  # noqa: E402

_PW_RESET_SALT = "pw-reset"
_PW_RESET_MAX_AGE = 3600  # 1 saat


def _pw_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt=_PW_RESET_SALT)


class _ForgotPasswordRequest(_PwBaseModel):
    email: str


class _ResetPasswordRequest(_PwBaseModel):
    token: str
    new_password: str


@router.post("/forgot-password", response_model=None)
def forgot_password(req: _ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Şifre sıfırlama e-postası gönder. E-postanın kayıtlı olup olmadığını ASLA
    açık etme (güvenlik) — her durumda aynı yanıt döner."""
    from app.services import email_service
    email = (req.email or "").strip().lower()
    user = db.scalar(select(User).where(User.email == email)) if email else None

    if user and user.password_hash and email_service.is_configured():
        token = _pw_serializer().dumps({"uid": str(user.id)})
        link = f"{settings.panel_base_url.rstrip('/')}/sifre-sifirla?token={token}"
        ad = (user.full_name or "").split()[0] if user.full_name else ""
        html = f"""
        <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;color:#1f2937">
          <h2 style="color:#6d28d9">Şifre Sıfırlama</h2>
          <p>Merhaba {ad or ''},</p>
          <p>Hesabınız için şifre sıfırlama talebinde bulunuldu. Yeni şifre belirlemek için
          aşağıdaki butona tıklayın (bağlantı <b>1 saat</b> geçerlidir):</p>
          <p style="margin:24px 0">
            <a href="{link}" style="background:#6d28d9;color:#fff;text-decoration:none;padding:12px 22px;border-radius:10px;font-weight:600">Şifremi Sıfırla</a>
          </p>
          <p style="font-size:12px;color:#6b7280">Buton çalışmazsa: <br>{link}</p>
          <p style="font-size:12px;color:#6b7280">Bu talebi siz yapmadıysanız bu e-postayı yok sayabilirsiniz.</p>
        </div>"""
        text = f"Şifre sıfırlama bağlantınız (1 saat geçerli):\n{link}"
        email_service.send_email(user.email, "Şifre Sıfırlama — BERNZ", html, text)

    return {"ok": True, "message": "E-posta adresiniz kayıtlıysa sıfırlama bağlantısı gönderildi."}


@router.post("/reset-password", response_model=None)
def reset_password(req: _ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 8 karakter olmalı")
    try:
        data = _pw_serializer().loads(req.token, max_age=_PW_RESET_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Bağlantının süresi dolmuş. Yeni bir talep oluşturun.")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Geçersiz bağlantı.")

    user = db.scalar(select(User).where(User.id == data.get("uid")))
    if not user:
        raise HTTPException(status_code=400, detail="Kullanıcı bulunamadı.")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"ok": True, "message": "Şifreniz güncellendi. Giriş yapabilirsiniz."}


# ─── Netflix tarzi profil secimi (Paket Profiles) ───
from pydantic import BaseModel as _PfBaseModel  # profil semalari


class _SelectProfileRequest(_PfBaseModel):
    user_id: str
    pin: str | None = None


@router.get("/profiles", response_model=None)
def list_profiles(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giris yapan kullanicinin tenant'indaki aktif profiller (Netflix 'Kim kullaniyor')."""
    rows = db.scalars(
        select(User).where(
            User.tenant_id == user.tenant_id,
            User.is_active.is_(True),
        ).order_by(User.created_at)
    ).all()
    return [
        {
            "id": str(u.id),
            "full_name": u.full_name or u.email.split("@")[0],
            "avatar_url": u.avatar_url,
            "role": u.role,
            "has_pin": bool(u.pin_hash),
        }
        for u in rows
    ]


@router.post("/select-profile", response_model=TokenResponse)
def select_profile(
    req: _SelectProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Profil sec — ayni tenant icinde, PIN'liyse PIN dogrula, secilen profilin token'ini ver."""
    import uuid as _uuid
    try:
        target_id = _uuid.UUID(req.user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Gecersiz profil")

    target = db.scalar(
        select(User).where(
            User.id == target_id,
            User.tenant_id == user.tenant_id,  # sadece ayni tenant
            User.is_active.is_(True),
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Profil bulunamadi")

    # PIN'liyse dogrula
    if target.pin_hash:
        if not req.pin or not verify_password(req.pin, target.pin_hash):
            raise HTTPException(status_code=401, detail="PIN yanlis")

    target.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(target)
    return _issue_token(target)
