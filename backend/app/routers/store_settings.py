"""
Mağaza Ayarları — /api/store-settings/{store_id}

Mağaza Paneli'nin yapılandırılmış ayar yüzeyi. Tek kaynak Store.config JSONB —
Baskıcı Atölyeler modalıyla aynı veriyi yazar (PATCH merge, tam replace değil).
Secretlar okuma yönünde maskelenir (_mask_config); '••' içeren değer yazılmaz.
"""
from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import Store, User
from app.routers.stores import _SECRET_KEYS, _mask_config

router = APIRouter(
    prefix="/api/store-settings", tags=["store-settings"],
    dependencies=[Depends(require_permission("vitrin"))],
)

# Panelden yönetilebilen config anahtarları (whitelist — serbest yazım yok)
_MONEY_KEYS = {"shipping_fee", "free_shipping_over", "min_order_amount"}
_TEXT_KEYS = {
    "payment_provider", "storefront_url", "custom_domain", "shop_domain",
    "contact_email", "contact_phone", "contact_address", "contact_instagram",
    "kvkk_text", "mesafeli_satis_text", "iade_text", "sla_days",
    "iyzico_base_url", "paytr_test_mode",
}
_SECRET_CFG_KEYS = {
    "iyzico_api_key", "iyzico_secret_key",
    "paytr_merchant_id", "paytr_merchant_key", "paytr_merchant_salt",
}
_BOOL_KEYS = {"abandoned_reminder_enabled"}
ALLOWED_KEYS = _MONEY_KEYS | _TEXT_KEYS | _SECRET_CFG_KEYS | _BOOL_KEYS


class SettingsPatch(BaseModel):
    store_name: str | None = Field(None, min_length=1, max_length=200)
    config: dict = Field(default_factory=dict)


def _get_store(db: Session, user: User, store_id: uuid.UUID) -> Store:
    store = db.scalar(select(Store).where(
        Store.id == store_id, Store.tenant_id == user.tenant_id,
        Store.platform == "storefront",
    ))
    if not store:
        raise HTTPException(404, "Vitrin mağazası bulunamadı")
    return store


@router.get("/{store_id}", response_model=dict)
def get_settings(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    config = _mask_config(store.config or {})
    return {
        "store_id": str(store.id),
        "store_name": store.name,
        "slug": store.slug,
        "config": {k: config.get(k) for k in sorted(ALLOWED_KEYS)},
    }


@router.patch("/{store_id}", response_model=dict)
def patch_settings(
    store_id: uuid.UUID,
    body: SettingsPatch,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)

    if body.store_name:
        store.name = body.store_name.strip()

    config = dict(store.config or {})
    for key, value in (body.config or {}).items():
        if key not in ALLOWED_KEYS:
            raise HTTPException(422, f"Bilinmeyen ayar: {key}")
        # Maskeli secret geri yazılmaz (kullanıcı değiştirmedi demektir)
        if key in (_SECRET_CFG_KEYS | _SECRET_KEYS) and isinstance(value, str) and "••" in value:
            continue
        if key in _MONEY_KEYS and value not in (None, ""):
            try:
                value = str(Decimal(str(value)).quantize(Decimal("0.01")))
            except (InvalidOperation, ValueError):
                raise HTTPException(422, f"Geçersiz tutar: {key}")
        if key in _BOOL_KEYS:
            value = bool(value)
        if value in (None, ""):
            config.pop(key, None)
        else:
            config[key] = value

    store.config = config
    flag_modified(store, "config")
    db.commit()
    db.refresh(store)
    return {
        "store_id": str(store.id),
        "store_name": store.name,
        "slug": store.slug,
        "config": {k: _mask_config(store.config).get(k) for k in sorted(ALLOWED_KEYS)},
    }


# ─── Tema ────────────────────────────────────────────────────

from fastapi import File, Form, UploadFile  # noqa: E402

from app.services.theme import resolve_theme, validate_theme_patch  # noqa: E402


@router.get("/{store_id}/theme", response_model=dict)
def get_theme(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    return resolve_theme(store.config)


@router.put("/{store_id}/theme", response_model=dict)
def put_theme(
    store_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    config = dict(store.config or {})
    config["theme"] = validate_theme_patch(body or {})
    store.config = config
    flag_modified(store, "config")
    db.commit()
    db.refresh(store)
    return resolve_theme(store.config)


@router.post("/{store_id}/assets", response_model=dict)
async def upload_asset(
    store_id: uuid.UUID,
    file: UploadFile = File(...),
    kind: str = Form(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Tema varlığı (logo | favicon | hero) yükle → /storage URL'i döner."""
    from app.services import storage as storage_svc

    store = _get_store(db, user, store_id)
    data = await file.read()
    try:
        url = storage_svc.save_store_asset(
            user.tenant_id, store.id, kind, data, file.filename or "asset.png")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"url": url, "kind": kind}


# ─── Özel domain doğrulama ───────────────────────────────────

@router.post("/{store_id}/verify-domain", response_model=dict)
def verify_domain(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """custom_domain'in DNS A kaydını sunucu IP'siyle karşılaştır.

    DNS yayılımı saatler sürebilir — başarısızlık 'yanlış kayıt' anlamına
    gelmeyebilir; mesaj bunu dürüstçe söyler.
    """
    import socket
    from datetime import datetime, timezone

    from app.config import get_settings

    store = _get_store(db, user, store_id)
    domain = ((store.config or {}).get("custom_domain") or "").strip().lower()
    if not domain:
        raise HTTPException(422, "Önce Ayarlar'dan özel alan adını kaydedin")

    expected_ip = (get_settings().server_ip or "").strip()
    try:
        infos = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
        resolved = sorted({i[4][0] for i in infos})
    except socket.gaierror:
        return {
            "verified": False,
            "domain": domain,
            "resolved_ips": [],
            "expected_ip": expected_ip or None,
            "message": "Alan adı çözümlenemedi — DNS kaydı henüz yayılmamış olabilir "
                       "(birkaç saat sonra tekrar deneyin) veya kayıt eksik.",
        }

    verified = bool(expected_ip) and expected_ip in resolved
    if verified:
        config = dict(store.config or {})
        config["custom_domain_verified_at"] = datetime.now(timezone.utc).isoformat()
        store.config = config
        flag_modified(store, "config")
        db.commit()

    return {
        "verified": verified,
        "domain": domain,
        "resolved_ips": resolved,
        "expected_ip": expected_ip or None,
        "message": "Alan adı doğrulandı ✓" if verified else (
            f"Alan adı şu an {', '.join(resolved)} adresine işaret ediyor; "
            f"beklenen {expected_ip or 'SERVER_IP tanımsız'}. DNS değişikliği "
            f"yayılıyorsa birkaç saat sonra tekrar deneyin."
        ),
    }
