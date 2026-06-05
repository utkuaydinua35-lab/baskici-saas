"""
Güvenlik primitive'leri:
- bcrypt password hash/verify
- JWT encode/decode
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# bcrypt context — rounds=12 default, güvenli ve makul hızlı
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Password ────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Plain password → bcrypt hash."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Plain password ile hash karşılaştır."""
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ─── JWT ─────────────────────────────────────────────────────

def create_access_token(
    *,
    user_id: str,
    tenant_id: str,
    email: str,
    expires_minutes: int | None = None,
) -> str:
    """
    JWT üret. Payload:
      sub: user_id
      tenant_id: ...
      email: ...
      exp: ...
      iat: ...
    """
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """JWT'yi doğrula ve payload döndür. Hata varsa JWTError fırlatır."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def safe_decode(token: str) -> dict[str, Any] | None:
    """Hata fırlatmadan, None döner."""
    try:
        return decode_access_token(token)
    except JWTError:
        return None
