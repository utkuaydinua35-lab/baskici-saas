"""
Mağaza (Store) yönetimi — /api/stores/*

Endpoint'ler:
- GET    /api/stores             → tenant'ın mağazaları
- POST   /api/stores             → yeni mağaza ekle
- GET    /api/stores/{id}        → tek mağaza detay
- PATCH  /api/stores/{id}        → güncelle (config dahil)
- DELETE /api/stores/{id}        → sil
- POST   /api/stores/{id}/test   → API bağlantısını test et
"""
from __future__ import annotations

import re
import secrets
import uuid
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.config import get_settings
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
import requests
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters import PLATFORM_REGISTRY, get_adapter
from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import Store, User

router = APIRouter(prefix="/api/stores", tags=["stores"])


# ─── Schemas ─────────────────────────────────────────────────

class StoreCreate(BaseModel):
    """Yeni mağaza ekleme."""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9-]+$")
    platform: str = Field(..., pattern=r"^(shopify|ikas|storefront)$")
    config: dict[str, Any] = Field(default_factory=dict)
    badge_color: str | None = None

    @field_validator("slug")
    @classmethod
    def lowercase_slug(cls, v: str) -> str:
        return v.lower().strip()


class StoreUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    config: dict[str, Any] | None = None
    badge_color: str | None = None
    is_active: bool | None = None


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    platform: str
    config: dict[str, Any]
    badge_color: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    platform: str


# ─── Helpers ─────────────────────────────────────────────────

_SECRET_KEYS = {
    "access_token", "client_secret", "api_secret", "api_key", "password", "secret",
    "token", "refresh_token", "webhook_secret", "private_key",
    "iyzico_api_key", "iyzico_secret_key",
    "paytr_merchant_key", "paytr_merchant_salt",
}


def _mask_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Hassas alanları UI'da maskele (kayıt değişmez, sadece dönüş).
    Token UI'da "shpat_xxxx_••••••" gibi görünür — kullanıcı yeniden girmesin.
    """
    masked = {}
    for k, v in (config or {}).items():
        if k in _SECRET_KEYS and isinstance(v, str) and v:
            # Sadece son 4 karakter (kullanici kendi girdigini tanisin); geri kalan TAMAMEN gizli
            masked[k] = ("••••••••" + v[-4:]) if len(v) >= 4 else "••••••••"
        else:
            masked[k] = v
    return masked


def _serialize_store(store: Store, mask_secrets: bool = True) -> dict:
    """Store ORM → response dict (config maskelenmiş)."""
    data = StoreResponse.model_validate(store).model_dump(mode="json")
    if mask_secrets:
        data["config"] = _mask_config(data["config"])
    return data


# ─── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=list[dict])
def list_stores(
    include_bayii: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mevcut tenant'ın mağazaları. Bayii (manuel) mağazalar varsayılan gizli;
    tasarım gibi akışlarda include_bayii=true ile dahil edilir."""
    q = select(Store).where(Store.tenant_id == user.tenant_id)
    if not include_bayii:
        q = q.where(Store.platform != "bayii")
    rows = db.scalars(q.order_by(Store.created_at)).all()
    return [_serialize_store(s) for s in rows]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_store(
    req: StoreCreate,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Tenant'a yeni mağaza ekle."""
    # Slug çakışması (tenant içinde)
    existing = db.scalar(
        select(Store).where(
            Store.tenant_id == user.tenant_id,
            Store.slug == req.slug,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bu slug zaten kullanılıyor: {req.slug}",
        )

    store = Store(
        tenant_id=user.tenant_id,
        slug=req.slug,
        name=req.name,
        platform=req.platform,
        config=req.config,
        badge_color=req.badge_color,
        is_active=True,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return _serialize_store(store)


@router.get("/{store_id}", response_model=dict)
def get_store(
    store_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == user.tenant_id,
        )
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")
    return _serialize_store(store)


@router.patch("/{store_id}", response_model=dict)
def update_store(
    store_id: uuid.UUID,
    req: StoreUpdate,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """
    Mağaza güncelle. config gönderilirse **birleştirilir** (merge),
    böylece sadece token güncellenmek için tüm config tekrar yollanmaz.
    Maskelenmiş değerler (••••) gönderilirse yok sayılır.
    """
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == user.tenant_id,
        )
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")

    if req.name is not None:
        store.name = req.name
    if req.badge_color is not None:
        store.badge_color = req.badge_color
    if req.is_active is not None:
        store.is_active = req.is_active

    if req.config is not None:
        merged = dict(store.config or {})
        for k, v in req.config.items():
            # Maskelenmiş değer geldiyse atla (kullanıcı değiştirmemiş)
            if isinstance(v, str) and "••••••" in v:
                continue
            merged[k] = v
        store.config = merged

    db.commit()
    db.refresh(store)
    return _serialize_store(store)


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_store(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == user.tenant_id,
        )
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")
    db.delete(store)
    db.commit()
    return None


@router.post("/{store_id}/test", response_model=TestConnectionResponse)
def test_connection(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """API bağlantısını test et — gerçek bir çağrı yapar."""
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == user.tenant_id,
        )
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")

    try:
        adapter = get_adapter(store)
        ok, msg = adapter.test_connection()
        return TestConnectionResponse(success=ok, message=msg, platform=store.platform)
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Adapter hatası: {str(e)[:200]}",
            platform=store.platform,
        )


@router.get("/_meta/platforms", response_model=list[dict])
def list_platforms():
    """Desteklenen platformları ve config alanlarını döndür (UI form için)."""
    return [
        {
            "id": "shopify",
            "name": "Shopify",
            "fields": [
                {"key": "store_url", "label": "Mağaza URL", "placeholder": "magazaniz.myshopify.com", "required": True},
                {"key": "access_token", "label": "Access Token", "type": "password", "required": True},
                {"key": "api_version", "label": "API Versiyonu", "default": "2024-01"},
            ],
        },
        {
            "id": "ikas",
            "name": "İkas",
            "fields": [
                {"key": "store_id", "label": "Mağaza ID", "required": True},
                {"key": "client_id", "label": "Client ID", "required": True},
                {"key": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            ],
        },
        {
            "id": "storefront",
            "name": "Kendi Mağazam (Vitrin)",
            "fields": [
                {"key": "shop_domain", "label": "Vitrin Alan Adı", "placeholder": "magaza.alanadiniz.com", "required": True},
                {"key": "payment_provider", "label": "Ödeme Sağlayıcı (iyzico | paytr)", "default": "iyzico", "required": True},
                {"key": "iyzico_api_key", "label": "iyzico API Key", "type": "password"},
                {"key": "iyzico_secret_key", "label": "iyzico Secret Key", "type": "password"},
                {"key": "iyzico_base_url", "label": "iyzico Base URL", "default": "https://sandbox-api.iyzipay.com"},
                {"key": "paytr_merchant_id", "label": "PayTR Merchant ID"},
                {"key": "paytr_merchant_key", "label": "PayTR Merchant Key", "type": "password"},
                {"key": "paytr_merchant_salt", "label": "PayTR Merchant Salt", "type": "password"},
                {"key": "sla_days", "label": "Kargo Sözü (gün)", "default": "3"},
            ],
        },
    ]



# ═════════════════════════════════════════════════════════════════════
# Shopify OAuth — public/custom distribution app'ler için (2026+)
# ═════════════════════════════════════════════════════════════════════
# Akış:
# 1. Frontend POST /api/stores/oauth/start → install URL üret + JWT state imzala
# 2. Tarayıcı Shopify'a yönlendir → kullanıcı izin verir
# 3. Shopify GET /api/stores/oauth/callback'a code+shop+state ile döner
# 4. Backend code'u access_token'a çevirir, Store kaydeder
# 5. Frontend'e redirect (?oauth=success&store_id=X)

SHOPIFY_OAUTH_SCOPES = (
    "read_orders,write_orders,read_products,"
    "read_fulfillments,write_fulfillments,read_customers"
)


class OAuthStartRequest(BaseModel):
    store_url: str  # örn "lunera.myshopify.com"
    client_id: str
    client_secret: str
    name: str       # görünen ad (Store.name)
    slug: str       # kısa kod (Store.slug)
    scopes: str | None = None  # opsiyonel override


class OAuthStartResponse(BaseModel):
    install_url: str


def _normalize_shop_domain(s: str) -> str:
    """'lunera.myshopify.com', 'https://lunera.myshopify.com/' gibi varyasyonları temizle."""
    s = (s or "").strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.rstrip("/")
    if not s.endswith(".myshopify.com"):
        if "." not in s:
            s = f"{s}.myshopify.com"
    return s


def _bekleyen_kurulum(db: Session, *, tenant_id, user_id, shop: str,
                     client_id: str, client_secret: str, name: str, slug: str,
                     scopes: str | None = None, store_id=None) -> str:
    """Kurulumu sunucuda kaydet, `state` için imzalı TEK KULLANIMLIK bilet üret.

    client_secret state'e KONMAZ (bkz. ShopifyOAuthPending). Bilet yalnız
    satırın id'sini taşır; imza + exp JWT'den, tekrar oynatma koruması
    kaydın callback'te silinmesinden gelir.
    """
    from app.config import get_settings as _gs
    from app.models import ShopifyOAuthPending

    settings = _gs()
    son = datetime.now(timezone.utc) + timedelta(minutes=10)
    kayit = ShopifyOAuthPending(
        tenant_id=tenant_id, user_id=user_id, store_id=store_id, shop=shop,
        client_id=client_id, client_secret=client_secret,
        name=name, slug=slug, scopes=scopes, expires_at=son,
    )
    db.add(kayit)
    db.commit()
    return jwt.encode(
        {"pending": str(kayit.id), "shop": shop, "exp": son},
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )


@router.post("/oauth/start", response_model=OAuthStartResponse)
def oauth_start(
    body: OAuthStartRequest,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Shopify install URL üret. Frontend bu URL'e yönlendirip kullanıcının
    Shopify'da izin vermesini bekleyecek."""
    from app.config import get_settings as _gs
    settings = _gs()

    shop = _normalize_shop_domain(body.store_url)
    if not shop.endswith(".myshopify.com"):
        raise HTTPException(400, "Geçersiz Shopify mağaza adresi")

    # Çakışma kontrol (aynı slug veya shop kullanıyor mu)
    existing = db.scalar(select(Store).where(
        Store.tenant_id == user.tenant_id,
        Store.slug == body.slug,
    ))
    if existing:
        raise HTTPException(400, f"Bu slug zaten kullanılıyor: {body.slug}")

    scopes = body.scopes or SHOPIFY_OAUTH_SCOPES
    state_token = _bekleyen_kurulum(
        db, tenant_id=user.tenant_id, user_id=user.id, shop=shop,
        client_id=body.client_id, client_secret=body.client_secret,
        name=body.name, slug=body.slug, scopes=scopes,
    )
    redirect_uri = f"{settings.backend_url}/api/stores/oauth/callback"

    qs = urlencode({
        "client_id": body.client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state_token,
    })
    # Shopify install URL
    install_url = f"https://{shop}/admin/oauth/authorize?{qs}"
    return OAuthStartResponse(install_url=install_url)


@router.post("/{store_id}/reauth", response_model=OAuthStartResponse)
def oauth_reauth(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Mevcut OAuth magazasini yeniden yetkilendir (yeni kalici/offline token al)."""
    from app.config import get_settings as _gs
    settings = _gs()

    store = db.scalar(select(Store).where(
        Store.id == store_id, Store.tenant_id == user.tenant_id,
    ))
    if not store:
        raise HTTPException(404, "Magaza bulunamadi")

    cfg = store.config or {}
    shop = _normalize_shop_domain(cfg.get("store_url", ""))
    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    if not shop.endswith(".myshopify.com") or not client_id or not client_secret:
        raise HTTPException(
            400,
            "Bu magaza OAuth ile bagli degil (client_id/secret yok). "
            "Custom app token'i icin magazayi duzenleyip access_token girin.",
        )

    state_token = _bekleyen_kurulum(
        db, tenant_id=user.tenant_id, user_id=user.id, shop=shop,
        client_id=client_id, client_secret=client_secret,
        name=store.name, slug=store.slug, store_id=store.id,
    )
    redirect_uri = f"{settings.backend_url}/api/stores/oauth/callback"
    qs = urlencode({
        "client_id": client_id,
        "scope": SHOPIFY_OAUTH_SCOPES,
        "redirect_uri": redirect_uri,
        "state": state_token,
    })
    return OAuthStartResponse(install_url=f"https://{shop}/admin/oauth/authorize?{qs}")


@router.get("/oauth/callback")
def oauth_callback(
    code: str,
    shop: str,
    state: str,
    db: Session = Depends(get_db),
):
    """Shopify install sonrası buraya redirect eder. code → access_token swap yap,
    Store kaydet, frontend'e geri yönlendir."""
    from app.config import get_settings as _gs
    settings = _gs()

    from app.models import ShopifyOAuthPending

    def _hata(sebep: str):
        return RedirectResponse(
            f"{settings.frontend_url}/stores?oauth=error&reason={sebep}", status_code=302)

    # State'i doğrula — imza + süre
    try:
        bilet = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return _hata("invalid_state")

    # Bilet yalnız kayıt id'sini taşır; gerçek config (client_secret dahil)
    # sunucudaki satırdan gelir. Satır TEK KULLANIMLIK: aşağıda silinir.
    try:
        pending_id = uuid.UUID(str(bilet.get("pending")))
    except (ValueError, TypeError):
        return _hata("invalid_state")
    kayit = db.get(ShopifyOAuthPending, pending_id)
    if not kayit:
        return _hata("state_used_or_expired")
    if kayit.expires_at and kayit.expires_at < datetime.now(timezone.utc):
        db.delete(kayit)
        db.commit()
        return _hata("state_used_or_expired")

    payload = {
        "user_id": str(kayit.user_id) if kayit.user_id else None,
        "tenant_id": str(kayit.tenant_id),
        "shop": kayit.shop,
        "client_id": kayit.client_id,
        "client_secret": kayit.client_secret,
        "name": kayit.name,
        "slug": kayit.slug,
        "store_id": str(kayit.store_id) if kayit.store_id else None,
    }
    # Tüket: aynı state ikinci kez kullanılamasın.
    db.delete(kayit)
    db.commit()

    if _normalize_shop_domain(shop) != payload["shop"]:
        return RedirectResponse(
            f"{settings.frontend_url}/stores?oauth=error&reason=shop_mismatch",
            status_code=302,
        )

    # Code'u access_token'a çevir
    try:
        token_resp = requests.post(
            f"https://{payload['shop']}/admin/oauth/access_token",
            json={
                "client_id": payload["client_id"],
                "client_secret": payload["client_secret"],
                "code": code,
            },
            timeout=15,
        )
        if token_resp.status_code != 200:
            return RedirectResponse(
                f"{settings.frontend_url}/stores?oauth=error&reason=token_exchange_failed",
                status_code=302,
            )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        granted_scopes = token_data.get("scope", "")
    except Exception as e:
        return RedirectResponse(
            f"{settings.frontend_url}/stores?oauth=error&reason=exception",
            status_code=302,
        )

    if not access_token:
        return RedirectResponse(
            f"{settings.frontend_url}/stores?oauth=error&reason=no_token",
            status_code=302,
        )

    # Store kaydet
    tenant_id = uuid.UUID(payload["tenant_id"])

    # ─── REAUTH: state'te store_id varsa mevcut store'un token'ini guncelle ───
    reauth_store_id = payload.get("store_id")
    if reauth_store_id:
        st = db.scalar(select(Store).where(
            Store.id == uuid.UUID(reauth_store_id),
            Store.tenant_id == tenant_id,
        ))
        if not st:
            return RedirectResponse(
                f"{settings.frontend_url}/stores?oauth=error&reason=store_not_found",
                status_code=302,
            )
        cfg = dict(st.config or {})
        cfg["access_token"] = access_token
        cfg["granted_scopes"] = granted_scopes
        cfg["auth_type"] = "oauth"
        cfg["store_url"] = payload["shop"]
        cfg.setdefault("api_version", "2024-01")
        st.config = cfg
        db.commit()
        return RedirectResponse(
            f"{settings.frontend_url}/stores?oauth=success&reauth=1&store_id={st.id}",
            status_code=302,
        )

    # Çakışma kontrol (yarış varsa)
    existing = db.scalar(select(Store).where(
        Store.tenant_id == tenant_id,
        Store.slug == payload["slug"],
    ))
    if existing:
        return RedirectResponse(
            f"{settings.frontend_url}/stores?oauth=error&reason=slug_exists",
            status_code=302,
        )

    store = Store(
        tenant_id=tenant_id,
        slug=payload["slug"],
        name=payload["name"],
        platform="shopify",
        is_active=True,
        config={
            "store_url": payload["shop"],
            "access_token": access_token,
            "client_id": payload["client_id"],
            "client_secret": payload["client_secret"],
            "api_version": "2024-01",
            "auth_type": "oauth",
            "granted_scopes": granted_scopes,
        },
    )
    db.add(store)
    db.commit()
    db.refresh(store)

    return RedirectResponse(
        f"{settings.frontend_url}/stores?oauth=success&store_id={store.id}",
        status_code=302,
    )

