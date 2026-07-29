"""Geçiş anahtarı (passkey / WebAuthn) — parolasız giriş.

- register: giriş yapmış kullanıcı yeni passkey ekler (Ayarlar).
- login: passkey ile doğrulanınca normal JWT verilir (şifre/2FA gerekmez —
  passkey zaten phishing-dirençli güçlü kimlik).

Challenge kısa ömürlü imzalı JWT ile taşınır (ayrı tablo gerekmez). RP kimliği
panel domaininden (studio.bernzcompany.com) türetilir.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import func as sa_func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.router import _issue_token
from app.config import get_settings
from app.database import get_db
from app.models import Tenant, User, WebAuthnCredential

router = APIRouter(prefix="/api/auth/passkey", tags=["passkey"])

_s = get_settings()
_ORIGIN = (_s.panel_base_url or "http://localhost:5173").rstrip("/")
_RP_ID = urlparse(_ORIGIN).hostname or "localhost"
_RP_NAME = "BERNZ"


def _sign_state(data: dict) -> str:
    payload = {**data, "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())}
    return jwt.encode(payload, _s.jwt_secret, algorithm=_s.jwt_algorithm)


def _verify_state(token: str, purpose: str) -> dict:
    try:
        d = jwt.decode(token, _s.jwt_secret, algorithms=[_s.jwt_algorithm])
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Süre doldu — tekrar deneyin")
    if d.get("p") != purpose:
        raise HTTPException(400, "Geçersiz istek")
    return d


def _ser(c: WebAuthnCredential) -> dict:
    return {
        "id": str(c.id), "name": c.name or "Passkey",
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
    }


# ─── Kayıt (giriş yapmış kullanıcı) ─────────────────────────
class RegisterFinishIn(BaseModel):
    state: str
    credential: dict
    name: str | None = None


@router.get("", response_model=list)
def list_passkeys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
        .order_by(WebAuthnCredential.created_at.desc())
    ).all()
    return [_ser(c) for c in rows]


class PasskeyOnlyIn(BaseModel):
    enabled: bool


@router.get("/only", response_model=dict)
def get_passkey_only(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.scalar(
        select(sa_func.count()).select_from(WebAuthnCredential)
        .where(WebAuthnCredential.user_id == user.id)
    ) or 0
    return {"enabled": bool(user.password_login_disabled), "passkey_count": int(n)}


@router.post("/only", response_model=dict)
def set_passkey_only(body: PasskeyOnlyIn, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Yalnızca geçiş anahtarı ile giriş. Açıkken e-posta+şifre girişi reddedilir.

    KİLİTLENME KORUMASI: en az 1 passkey kayıtlı değilse açılamaz. Yine de
    kilitlenirsen sunucudan geri alınır:
      UPDATE users SET password_login_disabled = false WHERE email = '...';
    """
    if body.enabled:
        n = db.scalar(
            select(sa_func.count()).select_from(WebAuthnCredential)
            .where(WebAuthnCredential.user_id == user.id)
        ) or 0
        if n < 1:
            raise HTTPException(
                400, "Önce en az bir geçiş anahtarı ekle — yoksa hesabına giremezsin.",
            )
    user.password_login_disabled = bool(body.enabled)
    db.commit()
    return {"ok": True, "enabled": user.password_login_disabled}


@router.post("/register/begin", response_model=dict)
def register_begin(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
        ResidentKeyRequirement, UserVerificationRequirement,
    )
    existing = db.scalars(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
    ).all()
    opts = generate_registration_options(
        rp_id=_RP_ID, rp_name=_RP_NAME,
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.full_name or user.email,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id)) for c in existing
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    state = _sign_state({"c": bytes_to_base64url(opts.challenge), "u": str(user.id), "p": "reg"})
    return {"options": json.loads(options_to_json(opts)), "state": state}


@router.post("/register/finish", response_model=dict)
def register_finish(body: RegisterFinishIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from webauthn import verify_registration_response
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
    st = _verify_state(body.state, "reg")
    if st.get("u") != str(user.id):
        raise HTTPException(400, "Geçersiz istek")
    try:
        v = verify_registration_response(
            credential=json.dumps(body.credential),
            expected_challenge=base64url_to_bytes(st["c"]),
            expected_rp_id=_RP_ID,
            expected_origin=_ORIGIN,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Passkey doğrulanamadı: {str(e)[:150]}")
    cred_id = bytes_to_base64url(v.credential_id)
    if db.scalar(select(WebAuthnCredential).where(WebAuthnCredential.credential_id == cred_id)):
        raise HTTPException(409, "Bu passkey zaten kayıtlı")
    transports = None
    try:
        transports = (body.credential.get("response") or {}).get("transports")
    except Exception:  # noqa: BLE001
        pass
    c = WebAuthnCredential(
        user_id=user.id, tenant_id=user.tenant_id,
        credential_id=cred_id,
        public_key=bytes_to_base64url(v.credential_public_key),
        sign_count=v.sign_count,
        transports=transports,
        name=(body.name or "Passkey")[:100],
    )
    db.add(c)
    db.commit(); db.refresh(c)
    return {"ok": True, "passkey": _ser(c)}


@router.delete("/{cred_id}", response_model=dict)
def delete_passkey(cred_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import uuid as _uuid
    try:
        cid = _uuid.UUID(cred_id)
    except ValueError:
        raise HTTPException(404, "Passkey bulunamadı")
    c = db.scalar(select(WebAuthnCredential).where(
        WebAuthnCredential.id == cid, WebAuthnCredential.user_id == user.id))
    if not c:
        raise HTTPException(404, "Passkey bulunamadı")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ─── Giriş (parolasız) ──────────────────────────────────────
class LoginFinishIn(BaseModel):
    state: str
    credential: dict


@router.post("/login/begin", response_model=dict)
def login_begin():
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers import bytes_to_base64url
    from webauthn.helpers.structs import UserVerificationRequirement
    opts = generate_authentication_options(
        rp_id=_RP_ID,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    state = _sign_state({"c": bytes_to_base64url(opts.challenge), "p": "login"})
    return {"options": json.loads(options_to_json(opts)), "state": state}


@router.post("/login/finish", response_model=None)
def login_finish(body: LoginFinishIn, db: Session = Depends(get_db)):
    from webauthn import verify_authentication_response
    from webauthn.helpers import base64url_to_bytes
    st = _verify_state(body.state, "login")
    cred_id = body.credential.get("id") if isinstance(body.credential, dict) else None
    if not cred_id:
        raise HTTPException(400, "Geçersiz kimlik")
    cred = db.scalar(select(WebAuthnCredential).where(WebAuthnCredential.credential_id == cred_id))
    if not cred:
        raise HTTPException(404, "Passkey tanınmadı")
    try:
        v = verify_authentication_response(
            credential=json.dumps(body.credential),
            expected_challenge=base64url_to_bytes(st["c"]),
            expected_rp_id=_RP_ID,
            expected_origin=_ORIGIN,
            credential_public_key=base64url_to_bytes(cred.public_key),
            credential_current_sign_count=cred.sign_count,
            require_user_verification=False,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Passkey doğrulanamadı: {str(e)[:150]}")

    user = db.get(User, cred.user_id)
    if not user or not user.is_active:
        raise HTTPException(403, "Hesap aktif değil")
    tenant = db.get(Tenant, user.tenant_id)
    if tenant and not getattr(tenant, "is_approved", True):
        raise HTTPException(403, "Hesabınız onay aşamasında.")
    if tenant and not tenant.is_active:
        raise HTTPException(403, "Hesap aktif değil")

    cred.sign_count = v.new_sign_count
    cred.last_used_at = datetime.now(UTC)
    db.commit()
    return _issue_token(user)
