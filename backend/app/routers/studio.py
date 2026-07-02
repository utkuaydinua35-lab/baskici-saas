"""Ürün Stüdyosu — tasarım görseli -> AI analiz -> PSD mockup -> Shopify ürünü.

Akış:
1) POST /api/studio/mockup   : mağazaya marka mockup PSD'si yükle (store.config.mockup_psd)
2) POST /api/studio/analyze  : tasarım görselleri yükle -> her biri için önizleme
3) POST /api/studio/publish  : onaylanan önizlemeleri Design + Shopify ürününe çevir
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import Design, Store, User
from app.services import product_studio as ps
from app.services import mockup as mockup_svc
from app.services.storage import STORAGE_ROOT

router = APIRouter(prefix="/api/studio", tags=["studio"])


def _get_store(db: Session, store_id: uuid.UUID, tenant_id) -> Store:
    s = db.scalar(select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id))
    if not s:
        raise HTTPException(404, "Mağaza bulunamadı")
    return s


def _brand(s: Store) -> str:
    return (s.config or {}).get("marka_adi") or s.name or "Marka"


def _studio_dir(tenant_id, store_id) -> Path:
    return STORAGE_ROOT / "tenants" / str(tenant_id) / "studio" / str(store_id)


def _cfg(s: Store) -> dict:
    c = s.config or {}
    brand = _brand(s)
    return {
        "store_id": str(s.id),
        "store_name": s.name,
        "brand": brand,
        "prefix": (c.get("kod_prefix") or ps.default_prefix(brand)).upper(),
        "price": c.get("studio_price"),
        "mockup_ready": bool(c.get("mockup_psd")),
    }


@router.get("/config", response_model=dict)
def studio_config(store_id: uuid.UUID, user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    return _cfg(_get_store(db, store_id, user.tenant_id))


class ConfigIn(BaseModel):
    store_id: uuid.UUID
    price: str | None = None
    prefix: str | None = None
    marka_adi: str | None = None


@router.patch("/config", response_model=dict)
def set_config(req: ConfigIn, user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    s = _get_store(db, req.store_id, user.tenant_id)
    cfg = dict(s.config or {})
    if req.price is not None:
        cfg["studio_price"] = req.price.strip() or None
    if req.prefix is not None:
        cfg["kod_prefix"] = (req.prefix.strip() or None) and req.prefix.strip().upper()
    if req.marka_adi is not None:
        cfg["marka_adi"] = req.marka_adi.strip() or None
    s.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(s, "config")
    db.commit()
    return {"ok": True, **_cfg(s)}


@router.post("/mockup", response_model=dict)
async def upload_mockup(
    store_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_permission("tasarim")),
    db: Session = Depends(get_db),
):
    """Mağazaya marka mockup PSD'si yükle."""
    s = _get_store(db, store_id, user.tenant_id)
    name = (file.filename or "").lower()
    if not name.endswith((".psd", ".psb")):
        raise HTTPException(400, "Yalnızca .psd/.psb yükleyin")
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(413, "Dosya çok büyük (max 200 MB)")
    d = _studio_dir(user.tenant_id, store_id)
    d.mkdir(parents=True, exist_ok=True)
    ext = ".psb" if name.endswith(".psb") else ".psd"
    rel = f"tenants/{user.tenant_id}/studio/{store_id}/mockup{ext}"
    (STORAGE_ROOT / rel).write_bytes(data)
    cfg = dict(s.config or {})
    cfg["mockup_psd"] = rel
    s.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(s, "config")
    db.commit()
    return {"ok": True, **_cfg(s)}


def _existing_studio_codes(tenant_id, store_id) -> set:
    d = _studio_dir(tenant_id, store_id)
    if not d.exists():
        return set()
    return {p.name for p in d.iterdir() if p.is_dir()}


@router.post("/analyze", response_model=dict)
async def analyze(
    store_id: uuid.UUID = Form(...),
    files: list[UploadFile] = File(...),
    user: User = Depends(require_permission("tasarim")),
    db: Session = Depends(get_db),
):
    """Tasarım görsellerini işle: AI analiz + PSD mockup + kod + içerik -> önizleme."""
    s = _get_store(db, store_id, user.tenant_id)
    cfg = _cfg(s)
    mockup_rel = (s.config or {}).get("mockup_psd")
    if not mockup_rel:
        raise HTTPException(400, "Önce bu mağazaya mockup PSD'si yükleyin")
    psd_path = STORAGE_ROOT / mockup_rel
    if not psd_path.exists():
        raise HTTPException(400, "Mockup dosyası bulunamadı, yeniden yükleyin")
    brand = cfg["brand"]
    prefix = cfg["prefix"]

    reserved = set(_existing_studio_codes(user.tenant_id, store_id))
    results = []
    for f in files:
        raw = await f.read()
        try:
            img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:  # noqa: BLE001
            results.append({"ok": False, "filename": f.filename, "error": "Görsel okunamadı"})
            continue
        media = "image/png" if (f.filename or "").lower().endswith("png") else "image/jpeg"
        analysis = ps.analyze_design(raw, media_type=media) or {}
        content = ps.build_content(analysis, brand)
        code = ps.next_design_code(db, store_id, prefix, reserved=reserved)
        reserved.add(code)
        # Mockup render + kaydet
        cdir = _studio_dir(user.tenant_id, store_id) / code
        cdir.mkdir(parents=True, exist_ok=True)
        try:
            mock = mockup_svc.render_psd_mockup(str(psd_path), img)
            mock.convert("RGB").save(str(cdir / "mockup.jpg"), "JPEG", quality=92)
        except Exception as e:  # noqa: BLE001
            results.append({"ok": False, "filename": f.filename, "error": f"Mockup üretilemedi: {str(e)[:120]}"})
            continue
        img.save(str(cdir / "baski.jpg"), "JPEG", quality=95)
        rel = f"tenants/{user.tenant_id}/studio/{store_id}/{code}"
        results.append({
            "ok": True,
            "code": code,
            "title": content["title"],
            "body_html": content["body_html"],
            "tags": content["tags"],
            "design_name": content["design_name"],
            "analysis": analysis,
            "mockup_url": f"/storage/{rel}/mockup.jpg",
            "baski_url": f"/storage/{rel}/baski.jpg",
        })
    return {"ok": True, "store_id": str(store_id), "items": results}


class PublishItem(BaseModel):
    code: str
    title: str
    body_html: str = ""
    tags: list[str] = []


class PublishIn(BaseModel):
    store_id: uuid.UUID
    items: list[PublishItem]


@router.post("/publish", response_model=dict)
def publish(req: PublishIn, user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    """Önizlenen ürünleri Design kaydı + Shopify ürününe çevir."""
    s = _get_store(db, req.store_id, user.tenant_id)
    cfg = _cfg(s)
    price = (s.config or {}).get("studio_price")
    brand = cfg["brand"]
    sdir = _studio_dir(user.tenant_id, req.store_id)

    from app.adapters import get_adapter
    adapter = None
    if s.platform == "shopify":
        try:
            adapter = get_adapter(s)
        except Exception:  # noqa: BLE001
            adapter = None

    out = []
    for it in req.items:
        code = (it.code or "").strip()
        if not code.isalnum():
            out.append({"code": it.code, "ok": False, "error": "Geçersiz kod"})
            continue
        cdir = sdir / code
        baski = cdir / "baski.jpg"
        mock = cdir / "mockup.jpg"
        if not baski.exists() or not mock.exists():
            out.append({"code": code, "ok": False, "error": "Dosyalar bulunamadı (önce analiz)"})
            continue

        # 1) Design kaydı (baskı dosyası = üretim tasarımı). Kod çakışırsa atla.
        exists = db.scalar(select(Design).where(Design.store_id == s.id, Design.code == code))
        if exists:
            design = exists
        else:
            rel_design = f"tenants/{user.tenant_id}/studio/{req.store_id}/{code}/baski.jpg"
            design = Design(
                tenant_id=user.tenant_id, store_id=s.id, code=code,
                name=it.title[:200], file_path=rel_design, file_format="jpg",
                file_size_bytes=baski.stat().st_size,
            )
            db.add(design)
            db.flush()

        # 2) Shopify ürünü (mockup görseli)
        shop = {"ok": False}
        if adapter is not None:
            import base64
            img_b64 = base64.standard_b64encode(mock.read_bytes()).decode()
            shop = adapter.create_product(
                title=it.title, body_html=it.body_html or "",
                tags=it.tags or [], image_b64=img_b64, image_filename=f"{code}.jpg",
                status="active", price=(str(price) if price not in (None, "") else None),
                vendor=brand,
            )
            if shop.get("ok") and shop.get("id"):
                design.product_id = str(shop["id"])
        out.append({
            "code": code, "ok": bool(shop.get("ok")),
            "design_id": str(design.id),
            "shopify_id": shop.get("id"),
            "admin_url": shop.get("admin_url"),
            "error": None if shop.get("ok") else (shop.get("error") or "Shopify yüklenmedi"),
        })
    db.commit()
    return {"ok": True, "results": out}
