"""Baskıcı SaaS — FastAPI ana uygulama."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth.router import router as auth_router
from app.config import get_settings
from app.routers.designs import router as designs_router
from app.routers import aski
from app.routers.kisiye_ozel import router as kisiye_ozel_router
from app.routers.order_detail import router as order_detail_router
from app.routers.orders import router as orders_router
from app.routers.notifications import router as notifications_router
from app.routers.molds import router as molds_router
from app.routers.phone_models import router as phone_models_router
from app.routers.templates import router as templates_router
from app.routers.pipeline import router as pipeline_router
from app.routers.settings import router as tenant_settings_router
from app.routers.shortcuts import router as shortcuts_router
from app.routers.stores import router as stores_router
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
app.include_router(stores_router)
app.include_router(orders_router)
app.include_router(order_detail_router)
app.include_router(shortcuts_router)
app.include_router(pipeline_router)
app.include_router(designs_router)
app.include_router(tenant_settings_router)
app.include_router(kisiye_ozel_router)
app.include_router(notifications_router)
app.include_router(molds_router)
app.include_router(templates_router)
app.include_router(phone_models_router)
app.include_router(aski.router)


# ─── Static files (tasarım dosyaları) ─────────────────────────
storage_service.ensure_storage_root()
app.mount(
    "/storage",
    StaticFiles(directory=str(storage_service.STORAGE_ROOT)),
    name="storage",
)


# ─── Health ───────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"ok": True, "env": settings.env}


@app.get("/api/version")
async def version():
    return {"version": app.version}
