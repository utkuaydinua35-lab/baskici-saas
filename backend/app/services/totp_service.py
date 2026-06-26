"""2FA / TOTP yardımcıları — pyotp tabanlı authenticator-app desteği.

- Secret base32; DB'de Fernet ile ŞİFRELİ saklanır (pg_dump yedeklerine düz
  metin sızmasın). Fernet anahtarı session_secret'tan türetilir.
- Yedek (kurtarma) kodları bcrypt hash'li saklanır, tek kullanımlık.
"""
from __future__ import annotations

import base64
import hashlib
import io
import secrets

import pyotp
import qrcode
from cryptography.fernet import Fernet

from app.auth.security import hash_password, verify_password
from app.config import get_settings

ISSUER = "BERNZ Panel"


def _fernet() -> Fernet:
    """session_secret'tan stabil 32-byte Fernet anahtarı türet."""
    s = (get_settings().session_secret or "dev-secret").encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(s).digest())
    return Fernet(key)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:  # noqa: BLE001 — bozuk/eski token
        return None


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, account: str, issuer: str = ISSUER) -> str:
    """otpauth:// URI — authenticator uygulamasına eklemek için."""
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def verify_code(secret: str | None, code: str | None) -> bool:
    """6 haneli TOTP kodunu doğrula (±30sn saat kayması toleranslı)."""
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:  # noqa: BLE001
        return False


def qr_data_uri(uri: str) -> str:
    """otpauth URI → PNG data URI (frontend <img> ile gösterir)."""
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ─── Yedek (kurtarma) kodları ────────────────────────────────

def generate_backup_codes(n: int = 8) -> list[str]:
    """Okunabilir tek kullanımlık kodlar, örn. '3f9a-1c7d'."""
    out = []
    for _ in range(n):
        raw = secrets.token_hex(4)  # 8 hex karakter
        out.append(f"{raw[:4]}-{raw[4:]}")
    return out


def _normalize(code: str | None) -> str:
    return (code or "").replace("-", "").replace(" ", "").lower()


def hash_backup_codes(codes: list[str]) -> list[str]:
    return [hash_password(_normalize(c)) for c in codes]


def consume_backup_code(hashed_list: list[str], code: str | None) -> int | None:
    """Eşleşen yedek kodun index'ini döndür (tüketmek için), yoksa None."""
    norm = _normalize(code)
    if not norm:
        return None
    for i, h in enumerate(hashed_list or []):
        if verify_password(norm, h):
            return i
    return None
