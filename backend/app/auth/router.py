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
    dummy_verify,
    hash_password,
    verify_password,
)
from app.config import get_settings
from app.database import get_db
from app.models import LoginAttempt, Tenant, User, WebAuthnCredential

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


@router.get("/public-config", response_model=dict)
def public_config():
    """Giriş ekranının bilmesi gereken açık ayarlar (auth GEREKTİRMEZ)."""
    return {"signup_allowed": bool(settings.allow_public_signup)}


@router.post("/register", response_model=None, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """
    Yeni hesap aç:
    - Yeni Tenant oluştur (plan=trial, is_approved=False — yönetici onayı bekler)
    - Yeni User oluştur (role=owner)
    - JWT DÖNMEZ; hesap onaylanana kadar giriş yapılamaz.

    Email zaten kayıtlıysa 409 Conflict.
    Tenant slug çakışırsa otomatik suffix eklenir.
    """
    # Self-servis kayıt kapalıysa hiç başlama (varsayılan KAPALI).
    if not settings.allow_public_signup:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yeni kayıt kapalı. Hesap açılması için yöneticiyle iletişime geçin.",
        )
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

    # Tenant — yönetici onayı bekler (is_approved=False)
    tenant = Tenant(name=req.tenant_name, slug=slug, plan="trial", is_active=True, is_approved=False)
    db.add(tenant)
    db.flush()  # tenant.id elde edilsin

    # Kayıt anı meta (IP + tarayıcı/OS) — onay ekranında gösterilir, sahte kayıt ayıklama.
    _signup_ip = _login_client_ip(request)
    _signup_ua = (request.headers.get("user-agent") or "")[:400] or None

    # User
    user = User(
        tenant_id=tenant.id,
        email=req.email.lower(),
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role="owner",
        is_active=True,
        signup_ip=_signup_ip,
        signup_user_agent=_signup_ua,
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

    # Mobil push + Telegram (yeni magaza/atolye kaydi) — platform yoneticilerine onay hatirlatmasi
    try:
        from app.services import push
        from app.services.ua import summary as _ua_summary
        _cihaz = _ua_summary(_signup_ua)
        _body = (f"{req.tenant_name} kaydoldu — onay bekliyor\n"
                 f"E-posta: {req.email.lower()}\n"
                 f"IP: {_signup_ip or '?'} · {_cihaz}")
        push.send_to_platform_admins(
            db, "🆕 Yeni mağaza başvurusu", _body,
            url="/platform", tag=f"tenant-{tenant.id}",
        )
    except Exception:
        pass

    # Token DÖNMEZ — hesap onay bekliyor.
    return {
        "ok": True,
        "pending_approval": True,
        "message": "Kaydınız alındı. Hesabınız onay aşamasında — onay için yöneticiyle iletişime geçiniz.",
    }


_login_hits: dict[str, list[float]] = {}
_LOGIN_WINDOW = 300   # 5 dakika
_LOGIN_MAX = 10       # IP basina 5 dakikada en fazla 10 basarisiz deneme
_global_fails: list[float] = []   # tum IP'lerdeki basarisiz denemeler (dagitik saldiri tespiti)
_DISTRIB_THRESHOLD = 40           # 5 dk'da bu kadar basarisiz -> dagitik saldiri suphesi


def _login_client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _record_attempt(db, request: Request, email: str | None, reason: str,
                    user_id=None) -> None:
    """Basarisiz denemeyi kalici kaydet (kim, hangi hesap, nereden, neyle).

    ASLA giris akisini bozmaz — kayit hatasi yutulur. Tenant'a bagli degildir;
    denemelerin cogu var olmayan bir hesaba yapiliyor.
    """
    if db is None:
        return
    try:
        db.add(LoginAttempt(
            email=((email or "").strip().lower()[:200] or None),
            ip=_login_client_ip(request),
            user_agent=((request.headers.get("user-agent") or "")[:400] or None),
            reason=reason,
            user_id=user_id,
        ))
        db.commit()
    except Exception:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


def _login_rate_limit(request: Request, db=None, email: str | None = None) -> None:
    """Basarisiz giris denemelerini IP basina sinirla (brute-force korumasi)."""
    import time as _t
    ip = _login_client_ip(request)
    now = _t.time()
    arr = [x for x in _login_hits.get(ip, []) if now - x < _LOGIN_WINDOW]
    if len(arr) >= _LOGIN_MAX:
        _record_attempt(db, request, email, "engellendi")
        # Brute-force tespiti — platform yoneticilerine anlik uyari (throttle'li)
        try:
            from app.services import security_alert
            from app.services.ua import summary as _ua_summary
            _cihaz = _ua_summary(request.headers.get("user-agent") or "")
            _hedef = f"\nDenenen hesap: {email.strip().lower()}" if email else ""
            security_alert.alert(
                f"bruteforce:{ip}", "Şüpheli giriş denemeleri (brute-force)",
                f"IP {ip} · {_cihaz}{_hedef}\n"
                f"Son 5 dk içinde {len(arr)} başarısız giriş; erişim geçici engellendi.",
            )
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(429, "Çok fazla başarısız giriş denemesi. Lütfen birkaç dakika sonra tekrar deneyin.")
    _login_hits[ip] = arr
    if len(_login_hits) > 5000:
        for k in [k for k, v in _login_hits.items() if not v or now - v[-1] > _LOGIN_WINDOW]:
            _login_hits.pop(k, None)


def _login_record_fail(request: Request, db=None, email: str | None = None,
                       reason: str = "sifre_hatali", user_id=None) -> None:
    import time as _t
    _record_attempt(db, request, email, reason, user_id)
    ip = _login_client_ip(request)
    now = _t.time()
    _login_hits.setdefault(ip, []).append(now)
    # Dagitik saldiri tespiti: cok sayida IP'den toplam basarisiz deneme
    _global_fails.append(now)
    cutoff = now - _LOGIN_WINDOW
    while _global_fails and _global_fails[0] < cutoff:
        _global_fails.pop(0)
    if len(_global_fails) >= _DISTRIB_THRESHOLD:
        active_ips = sum(1 for v in _login_hits.values() if v and v[-1] >= cutoff)
        try:
            from app.services import security_alert
            security_alert.alert(
                "distributed", "Dağıtık giriş saldırısı şüphesi",
                f"Son 5 dk'da {len(_global_fails)} başarısız giriş, ~{active_ips} farklı IP.",
            )
        except Exception:  # noqa: BLE001
            pass


@router.post("/login", response_model=None)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _login_rate_limit(request, db, req.email)
    """Email + şifre ile giriş. Yanlış bilgi → 401."""
    user = db.scalar(select(User).where(User.email == req.email.lower()))
    if not user or not user.password_hash:
        # password_hash null = sadece OAuth user, email/şifre giriş yok.
        # Zamanlama esitleme: email yoksa da bcrypt calistir (enumeration onle).
        dummy_verify(req.password)
        _login_record_fail(request, db, req.email, "hesap_yok")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre hatalı",
        )

    if not verify_password(req.password, user.password_hash):
        _login_record_fail(request, db, req.email, "sifre_hatali", user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email veya şifre hatalı",
        )

    # Yalnızca-passkey modu: şifre DOĞRU olsa bile giriş verilmez.
    # (Kontrol şifre doğrulamasından SONRA — yanlış şifreye farklı cevap dönerse
    #  hesabın var olduğu ele verilir.)
    if user.password_login_disabled:
        _login_record_fail(request, db, req.email, "passkey_zorunlu", user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu hesap yalnızca geçiş anahtarı (passkey) ile giriş yapabilir.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap pasif. Yöneticiyle iletişime geç.",
        )

    # Abonelik kontrolü (white-label kiralama) — platform admin muaf
    if not user.is_platform_admin:
        tenant = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
        if tenant and not getattr(tenant, "is_approved", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hesabınız onay aşamasında. Onay için yöneticiyle iletişime geçiniz.",
            )
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

    # 2FA aktifse — token verme; önce TOTP doğrulanmalı (kısa ömürlü mfa_token).
    if user.totp_enabled and user.totp_secret:
        mfa_token = _mfa_serializer().dumps({"uid": str(user.id)})
        return {"requires_2fa": True, "mfa_token": mfa_token}

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


from pydantic import BaseModel as _ProfBaseModel, Field as _ProfField  # noqa: E402


class _ProfileUpdateRequest(_ProfBaseModel):
    full_name: str = _ProfField(..., min_length=1, max_length=200)


@router.patch("/me", response_model=None)
def update_me(
    req: _ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kendi profil bilgisini güncelle (şimdilik yalnız ad soyad)."""
    user.full_name = req.full_name.strip()
    db.commit()
    return {"ok": True, "full_name": user.full_name}


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
        body = (
            f"<p style='margin:0 0 14px'>Merhaba {ad or ''},</p>"
            "<p style='margin:0 0 14px'>Hesabınız için bir şifre sıfırlama talebi aldık. "
            "Yeni şifrenizi belirlemek için aşağıdaki butona tıklayın. "
            "Bağlantı <b>1 saat</b> boyunca geçerlidir.</p>"
            "<p style='margin:0 0 6px;font-size:13px;color:#6b7280'>Buton çalışmazsa bu bağlantıyı "
            f"tarayıcınıza yapıştırın:</p><p style='margin:0 0 4px;font-size:12px;word-break:break-all'>"
            f"<a href='{link}' style='color:#6d28d9'>{link}</a></p>"
        )
        tenant = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
        html = email_service.render_email(
            title="Şifre Sıfırlama",
            emoji="🔒",
            body_html=body,
            button_text="Şifremi Sıfırla",
            button_url=link,
            preheader="Şifre sıfırlama bağlantınız (1 saat geçerli)",
            footer="Bu talebi siz yapmadıysanız bu e-postayı yok sayabilirsiniz. Şifreniz değişmez.",
            **email_service.brand_kwargs(tenant),
        )
        text = f"Şifre sıfırlama bağlantınız (1 saat geçerli):\n{link}"
        email_service.send_email(
            user.email, f"Şifre Sıfırlama — {get_settings().brand_name}", html, text)

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


# ─── 2FA / İki adımlı doğrulama (TOTP) ───────────────────────
# Not: totp_service (pyotp/qrcode) endpoint içinde lazy import edilir; VPS'te
# paketler kurulmadan restart edilirse app boot olmaya devam etsin diye.

_MFA_SALT = "mfa-login"
_MFA_MAX_AGE = 300  # 5 dakika — login ile kod doğrulama arası


def _mfa_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt=_MFA_SALT)


class _TwoFACodeRequest(_PwBaseModel):
    code: str


class _TwoFADisableRequest(_PwBaseModel):
    password: str | None = None
    code: str | None = None


class _TwoFAVerifyLoginRequest(_PwBaseModel):
    mfa_token: str
    code: str


@router.post("/2fa/setup", response_model=None)
def twofa_setup(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Yeni TOTP secret üret (henüz aktif değil) + QR/URI döndür. Aktifleşmesi
    için /2fa/enable ile kod doğrulanmalı."""
    from app.services import totp_service
    if not user.password_hash:
        raise HTTPException(400, "Şifresiz (OAuth) hesaplarda 2FA kullanılamaz.")
    if user.totp_enabled:
        raise HTTPException(400, "2FA zaten aktif. Önce kapatıp tekrar kurun.")
    secret = totp_service.generate_secret()
    user.totp_secret = totp_service.encrypt_secret(secret)
    user.totp_enabled = False
    db.commit()
    uri = totp_service.provisioning_uri(secret, user.email)
    return {"secret": secret, "otpauth_uri": uri, "qr": totp_service.qr_data_uri(uri)}


@router.post("/2fa/enable", response_model=None)
def twofa_enable(
    req: _TwoFACodeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kurulumdaki secret'ı kodla doğrula → 2FA'yı aç + tek kullanımlık yedek
    kodları üret (yalnızca burada bir kez gösterilir)."""
    from app.services import totp_service
    if not user.totp_secret:
        raise HTTPException(400, "Önce 2FA kurulumunu başlatın.")
    secret = totp_service.decrypt_secret(user.totp_secret)
    if not secret or not totp_service.verify_code(secret, req.code):
        raise HTTPException(400, "Kod doğrulanamadı. Uygulamadaki güncel kodu girin.")
    codes = totp_service.generate_backup_codes()
    user.totp_backup_codes = totp_service.hash_backup_codes(codes)
    user.totp_enabled = True
    db.commit()
    return {"ok": True, "backup_codes": codes}


@router.post("/2fa/disable", response_model=None)
def twofa_disable(
    req: _TwoFADisableRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """2FA'yı kapat — kimlik için şifre VEYA geçerli TOTP kodu gerekir."""
    from app.services import totp_service
    if not user.totp_enabled:
        return {"ok": True}
    ok = False
    if req.password and user.password_hash and verify_password(req.password, user.password_hash):
        ok = True
    elif req.code and user.totp_secret:
        secret = totp_service.decrypt_secret(user.totp_secret)
        ok = bool(secret and totp_service.verify_code(secret, req.code))
    if not ok:
        raise HTTPException(401, "Doğrulama başarısız (şifre veya kod hatalı).")
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_backup_codes = []
    db.commit()
    return {"ok": True}


@router.post("/2fa/verify-login", response_model=TokenResponse)
def twofa_verify_login(
    req: _TwoFAVerifyLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Login'in 2. adımı: mfa_token + kod (veya yedek kod) → gerçek JWT."""
    from app.services import totp_service
    _login_rate_limit(request, db)
    try:
        data = _mfa_serializer().loads(req.mfa_token, max_age=_MFA_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(400, "Doğrulama süresi doldu. Tekrar giriş yapın.")
    except BadSignature:
        raise HTTPException(400, "Geçersiz oturum. Tekrar giriş yapın.")

    user = db.scalar(select(User).where(User.id == data.get("uid")))
    if not user or not user.totp_enabled or not user.totp_secret:
        raise HTTPException(400, "2FA doğrulanamadı.")

    secret = totp_service.decrypt_secret(user.totp_secret)
    ok = bool(secret and totp_service.verify_code(secret, req.code))
    if not ok:
        # TOTP tutmadıysa yedek kod mu?
        idx = totp_service.consume_backup_code(user.totp_backup_codes or [], req.code)
        if idx is not None:
            remaining = list(user.totp_backup_codes)
            remaining.pop(idx)
            user.totp_backup_codes = remaining  # JSONB — yeniden atama (mutation algılansın)
            ok = True

    if not ok:
        _login_record_fail(request, db, user.email, "2fa_kod_hatali", user.id)
        raise HTTPException(401, "Kod hatalı.")

    user.last_login_at = datetime.now(UTC)
    db.commit()
    return _issue_token(user)


# ─── Netflix tarzi profil secimi (Paket Profiles) ───
from pydantic import BaseModel as _PfBaseModel  # profil semalari


_ADMIN_ROLES = {"owner", "yonetici"}


class _SelectProfileRequest(_PfBaseModel):
    user_id: str
    pin: str | None = None
    code: str | None = None       # yönetici profili için 2FA kodu (veya yedek kod)
    password: str | None = None   # yönetici profili 2FA kurulu değilse parola


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
    out = []
    for u in rows:
        is_admin = (u.role or "").lower() in _ADMIN_ROLES
        out.append({
            "id": str(u.id),
            "full_name": u.full_name or u.email.split("@")[0],
            "avatar_url": u.avatar_url,
            "role": u.role,
            "is_admin": is_admin,
            "requires_2fa": is_admin and bool(u.totp_enabled),
            # Yönetici profilinde PIN kullanılmaz (2FA/parola ile korunur)
            "has_pin": (not is_admin) and bool(u.pin_hash),
        })
    return out


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

    is_admin = (target.role or "").lower() in _ADMIN_ROLES

    if is_admin:
        # Yönetici profiline başka bir profilden geçişte 2FA (yoksa parola) gerekir.
        # Kendi profilini seçiyorsa (zaten giriş yaptı) tekrar sorulmaz.
        if target.id != user.id:
            if target.totp_enabled and target.totp_secret:
                from app.services import totp_service
                code = (req.code or "").strip()
                ok = False
                if code:
                    secret = totp_service.decrypt_secret(target.totp_secret)
                    ok = bool(secret and totp_service.verify_code(secret, code))
                    if not ok:
                        idx = totp_service.consume_backup_code(target.totp_backup_codes or [], code)
                        if idx is not None:
                            remaining = list(target.totp_backup_codes)
                            remaining.pop(idx)
                            target.totp_backup_codes = remaining
                            ok = True
                if not ok:
                    raise HTTPException(status_code=401, detail="Yönetici profili için 2FA kodu gerekli veya yanlış.")
            else:
                if not req.password or not target.password_hash \
                        or not verify_password(req.password, target.password_hash):
                    raise HTTPException(status_code=401, detail="Yönetici profili için parola gerekli (veya 2FA kurun).")
        # Yönetici profilinde PIN kullanılmaz — varsa kaldır.
        if target.pin_hash:
            target.pin_hash = None
    else:
        # PIN'liyse dogrula (kendi profilin haric — zaten giriş yaptın)
        if target.id != user.id and target.pin_hash:
            if not req.pin or not verify_password(req.pin, target.pin_hash):
                raise HTTPException(status_code=401, detail="PIN yanlis")

    target.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(target)
    return _issue_token(target)
