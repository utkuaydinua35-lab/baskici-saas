"""Baskıcı SaaS — FastAPI ana uygulama."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth.router import router as auth_router
from app.routers.passkey import router as passkey_router
from app.config import get_settings
from app.routers.designs import router as designs_router
from app.routers.studio import router as studio_router
from app.routers import aski
from app.routers.kisiye_ozel import router as kisiye_ozel_router
from app.routers.accessories import router as accessories_router
from app.routers.users import router as users_router
from app.routers.dealers import router as dealers_router
from app.routers.couple import router as couple_router
from app.routers.order_detail import router as order_detail_router
from app.routers.orders import router as orders_router
from app.routers.notifications import router as notifications_router
from app.routers.molds import router as molds_router
from app.routers.phone_models import router as phone_models_router
from app.routers.stock import router as stock_router
from app.routers.packaging import router as packaging_router
from app.routers.dashboard import router as dashboard_router
from app.routers.public_shop import router as public_shop_router
from app.routers.public_tracker import router as public_tracker_router
from app.routers.public_support import router as public_support_router
from app.routers.public_approval import router as public_approval_router
from app.routers.webhooks import router as webhooks_router
from app.routers.marketing import router as marketing_router
from app.routers.public_marketing import router as public_marketing_router
from app.routers.platform import router as platform_router
from app.routers.support import router as support_router
from app.routers.templates import router as templates_router
from app.routers.pipeline import router as pipeline_router
from app.routers.notes import router as notes_router
from app.routers.telafiler import router as telafiler_router
from app.routers.settings import router as tenant_settings_router
from app.routers.shortcuts import router as shortcuts_router
from app.routers.stores import router as stores_router
from app.routers.catalog import router as catalog_router
from app.routers.discounts import router as discounts_router
from app.routers.blog import router as blog_router
from app.routers.design_requests import router as design_requests_router
from app.routers.customers import router as customers_router
from app.routers.analytics import router as analytics_router
from app.routers.checkout_admin import router as checkout_admin_router
from app.routers.store_settings import router as store_settings_router
from app.routers.audit import router as audit_router
from app.routers.search import router as search_router
from app.routers.push import router as push_router
from app.routers.instagram import router as instagram_router
from app.scheduler import shutdown_scheduler, start_scheduler
from app.services import storage as storage_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[baskici] starting up (env={settings.env})")
    storage_service.ensure_storage_root()
    print(f"[baskici] storage root: {storage_service.STORAGE_ROOT}")
    try:
        start_scheduler()
        print("[baskici] scheduler started (hourly sync)")
    except Exception as e:
        print(f"[baskici] scheduler start failed: {e}")
    yield
    shutdown_scheduler()
    print("[baskici] shutting down")


app = FastAPI(title="Baskıcı SaaS API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routers ──────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(passkey_router)
app.include_router(stores_router)
app.include_router(orders_router)
app.include_router(order_detail_router)
app.include_router(shortcuts_router)
app.include_router(pipeline_router)
app.include_router(notes_router)
app.include_router(telafiler_router)
app.include_router(designs_router)
app.include_router(studio_router)
app.include_router(tenant_settings_router)
app.include_router(kisiye_ozel_router)
app.include_router(accessories_router)
app.include_router(users_router)
app.include_router(dealers_router)
app.include_router(couple_router)
app.include_router(notifications_router)
app.include_router(molds_router)
app.include_router(templates_router)
app.include_router(phone_models_router)
app.include_router(stock_router)
app.include_router(packaging_router)
app.include_router(dashboard_router)
app.include_router(public_tracker_router)
app.include_router(public_support_router)
app.include_router(public_approval_router)
app.include_router(webhooks_router)
app.include_router(marketing_router)
app.include_router(public_marketing_router)
app.include_router(platform_router)
app.include_router(support_router)
app.include_router(aski.router)
app.include_router(audit_router)
app.include_router(search_router)
app.include_router(push_router)
app.include_router(instagram_router)
app.include_router(catalog_router)
app.include_router(discounts_router)
app.include_router(blog_router)
app.include_router(design_requests_router)
app.include_router(customers_router)
app.include_router(analytics_router)
app.include_router(checkout_admin_router)
app.include_router(store_settings_router)
app.include_router(public_shop_router)


# ─── Guvenli statik servis (SVG/HTML XSS korumasi) ────────────
from starlette.responses import Response as _Resp

class SafeStaticFiles(StaticFiles):
    """SVG/HTML/XML gibi tarayicida script calistirabilen dosyalari
    inline yerine attachment olarak + siki guvenlik basliklariyla servis eder.
    Resimler (png/jpg/jpeg/gif/webp) normal inline gosterilir."""
    _RISKY_EXT = {".svg", ".html", ".htm", ".xml", ".xhtml"}

    async def get_response(self, path: str, scope):
        resp = await super().get_response(path, scope)
        try:
            ext = Path(path).suffix.lower()
        except Exception:
            ext = ""
        # Tum statik dosyalara temel guvenlik basliklari
        resp.headers["X-Content-Type-Options"] = "nosniff"
        if ext in self._RISKY_EXT:
            # Tarayicida CALISTIRMA — indir + CSP ile script engelle
            resp.headers["Content-Disposition"] = "attachment"
            resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
            resp.headers["Content-Type"] = "application/octet-stream"
        return resp


# ─── Static files (tasarım dosyaları) ─────────────────────────
storage_service.ensure_storage_root()
app.mount(
    "/storage",
    SafeStaticFiles(directory=str(storage_service.STORAGE_ROOT)),
    name="storage",
)

# ─── Destek görselleri (public /uploads) ──────────────────────
from app.services import uploads as uploads_service
uploads_service.ensure_upload_root()
app.mount(
    "/uploads",
    SafeStaticFiles(directory=str(uploads_service.UPLOAD_ROOT)),
    name="uploads",
)


# ─── Health ───────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"ok": True, "env": settings.env}


@app.get("/api/version")
async def version():
    return {"version": app.version}
