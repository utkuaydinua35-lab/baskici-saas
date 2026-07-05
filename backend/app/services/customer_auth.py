"""
Vitrin müşteri kimlik doğrulama — şifresiz (e-postaya 6 haneli kod).

Güvenlik:
- Kod bcrypt hash'iyle saklanır, 10 dk geçerli, 5 yanlış denemede iptal.
- login-request e-posta kayıtlı olmasa da AYNI yanıtı döner (enumeration yok);
  kayıtsız e-posta ilk girişte Customer olarak doğar.
- Token: HS256 JWT, payload {scope:"customer", email, store_id, exp 30 gün} —
  admin token'larından 'scope' ile ayrılır (admin akışı sub/tenant_id bekler).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.config import get_settings
from app.models import Customer, Store

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
TOKEN_TTL = timedelta(days=30)


def generate_login_code(db: Session, store: Store, email: str) -> tuple[Customer, str]:
    """Müşteriyi bul/oluştur, yeni kod üret ve hash'ini kaydet. Kodu döndürür."""
    email = email.strip().lower()
    customer = db.scalar(select(Customer).where(
        Customer.tenant_id == store.tenant_id, Customer.email == email))
    if not customer:
        customer = Customer(tenant_id=store.tenant_id, email=email)
        db.add(customer)
        db.flush()

    code = f"{secrets.randbelow(1_000_000):06d}"
    customer.login_code_hash = hash_password(code)
    customer.login_code_expires = datetime.now(timezone.utc) + CODE_TTL
    customer.login_code_attempts = 0
    db.commit()
    return customer, code


def verify_login_code(db: Session, store: Store, email: str, code: str) -> Customer | None:
    """Kodu doğrula. Başarısızsa None (5 denemede kod iptal edilir)."""
    email = email.strip().lower()
    customer = db.scalar(select(Customer).where(
        Customer.tenant_id == store.tenant_id, Customer.email == email))
    if not customer or not customer.login_code_hash:
        return None
    now = datetime.now(timezone.utc)
    if not customer.login_code_expires or now > customer.login_code_expires:
        return None
    if customer.login_code_attempts >= MAX_ATTEMPTS:
        return None

    if not verify_password(code.strip(), customer.login_code_hash):
        customer.login_code_attempts += 1
        if customer.login_code_attempts >= MAX_ATTEMPTS:
            customer.login_code_hash = None  # kod yakıldı — yeniden istenmeli
        db.commit()
        return None

    # Başarılı: kod tek kullanımlık
    customer.login_code_hash = None
    customer.login_code_expires = None
    customer.login_code_attempts = 0
    db.commit()
    return customer


def create_customer_token(customer: Customer, store: Store) -> str:
    s = get_settings()
    payload = {
        "scope": "customer",
        "email": customer.email,
        "store_id": str(store.id),
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_customer_token(token: str) -> dict | None:
    """Geçerli müşteri token'ı → payload; değilse None. scope şart."""
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    except JWTError:
        return None
    if payload.get("scope") != "customer":
        return None
    return payload
