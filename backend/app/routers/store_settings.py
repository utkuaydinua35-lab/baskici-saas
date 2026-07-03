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
