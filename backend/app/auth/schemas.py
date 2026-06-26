"""
Pydantic şemaları — request validation + response serialization.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ─── REQUEST SCHEMAS ─────────────────────────────────────────

class RegisterRequest(BaseModel):
    """
    Yeni hesap kaydı — aynı anda hem tenant hem owner user oluşturur.
    Tenant slug otomatik üretilir tenant_name'den (lowercase, normalize).
    """
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=200)
    tenant_name: str = Field(..., min_length=2, max_length=200)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalı")
        return v

    @field_validator("tenant_name")
    @classmethod
    def normalize_tenant_name(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ─── RESPONSE SCHEMAS ────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # saniye


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    permissions: list[str] = []
    avatar_url: str | None = None
    is_active: bool
    is_platform_admin: bool = False
    totp_enabled: bool = False
    tenant_id: uuid.UUID
    last_login_at: datetime | None
    created_at: datetime


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    logo_url: str | None = None
    brand_color: str | None = None
    app_name: str | None = None
    slug: str
    plan: str
    is_active: bool
    created_at: datetime


class AuthMeResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse


# ─── HELPERS ─────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TURKISH_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
})


def slugify(text: str) -> str:
    """
    Tenant name → URL slug. Türkçe karakterleri normalize eder.
    "BERNZ Company" → "bernz-company"
    """
    text = text.translate(_TURKISH_MAP).lower()
    text = _SLUG_RE.sub("-", text).strip("-")
    return text[:50]  # max 50 char
