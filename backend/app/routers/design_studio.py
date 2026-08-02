"""
Tasarım Stüdyosu — kılıf şablonları (panel) + müşteri tasarımları (vitrin).

İki yüzey:
- /api/case-templates/*  : panel. Boş kılıf görselleri ve baskı alanı tanımı.
- /api/shop/{slug}/studio/* : vitrin. Şablon listesi (herkese açık) +
  müşteri tasarımları (müşteri token'ı zorunlu — hesap açan kaldığı yerden
  devam eder).

Baskı kalitesi ilkesi: müşterinin yüklediği dosya ORİJİNAL haliyle saklanır;
tuvalde yalnız hafif önizlemesi taşınır. Katman konumları baskı alanına göre
ORANSAL (0-1) tutulduğundan, aynı tasarım hem ekranda hem 300 DPI baskı
dosyasında aynı yere düşer.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import CaseTemplate, CustomerDesign, DesignAsset, Store, User
from app.services import activity
from app.services import storage as storage_svc

router = APIRouter(prefix="/api/case-templates", tags=["design-studio"],
                   dependencies=[Depends(require_permission("vitrin"))])

# Müşteriye sunulan hazır kılıf tipleri — panelde bunlardan seçilir
ONERILEN_TIPLER = [
    {"key": "seffaf", "label": "Şeffaf"},
    {"key": "beyaz", "label": "Beyaz (iPhone)"},
    {"key": "siyah", "label": "Siyah"},
    {"key": "parlak", "label": "Parlak"},
    {"key": "magsafe", "label": "MagSafe"},
]
MAX_LAYERS = 40


def _get_storefront_store(db: Session, tenant_id, store_id) -> Store:
    store = db.scalar(select(Store).where(
        Store.id == store_id, Store.tenant_id == tenant_id,
        Store.platform == "storefront"))
    if not store:
        raise HTTPException(404, "Vitrin mağazası bulunamadı")
    return store


def _ser_template(t: CaseTemplate) -> dict:
    return {
        "id": str(t.id),
        "key": t.key,
        "label": t.label,
        "description": t.description,
        "image_url": f"/storage/{t.image_path}" if t.image_path else None,
        "area": {"x": float(t.area_x), "y": float(t.area_y),
                 "w": float(t.area_w), "h": float(t.area_h),
                 "radius": float(t.area_radius or 0)},
        "cutouts": t.cutouts or [],
        "print": {"width_mm": t.print_width_mm, "height_mm": t.print_height_mm,
                  "dpi": t.print_dpi,
                  # Baskı dosyasının piksel ölçüsü — panelde bilgi olarak gösterilir
                  "px_w": round(t.print_width_mm / 25.4 * t.print_dpi),
                  "px_h": round(t.print_height_mm / 25.4 * t.print_dpi)},
        "position": t.position,
        "is_active": t.is_active,
    }


# ─── Panel: şablon yönetimi ──────────────────────────────────

class TemplateCreate(BaseModel):
    store_id: uuid.UUID
    key: str = Field(..., min_length=2, max_length=40, pattern="^[a-z0-9_-]+$")
    label: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=300)
    position: int = 0


class Cutout(BaseModel):
    """Basılamayan bölge — kamera adası, MagSafe halkası…"""
    x: Decimal = Field(..., ge=0, le=1)
    y: Decimal = Field(..., ge=0, le=1)
    w: Decimal = Field(..., gt=0, le=1)
    h: Decimal = Field(..., gt=0, le=1)
    radius: Decimal = Field(Decimal("0.2"), ge=0, le=0.5)
    label: str | None = Field(None, max_length=40)


class TemplateUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=300)
    image_path: str | None = Field(None, max_length=500)
    area_x: Decimal | None = Field(None, ge=0, le=1)
    area_y: Decimal | None = Field(None, ge=0, le=1)
    area_w: Decimal | None = Field(None, gt=0, le=1)
    area_h: Decimal | None = Field(None, gt=0, le=1)
    area_radius: Decimal | None = Field(None, ge=0, le=0.5)
    cutouts: list[Cutout] | None = Field(None, max_length=8)
    print_width_mm: int | None = Field(None, ge=10, le=500)
    print_height_mm: int | None = Field(None, ge=10, le=500)
    print_dpi: int | None = Field(None, ge=72, le=1200)
    position: int | None = None
    is_active: bool | None = None


@router.get("", response_model=dict)
def list_templates(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    _get_storefront_store(db, user.tenant_id, store_id)
    rows = db.scalars(select(CaseTemplate).where(
        CaseTemplate.store_id == store_id)
        .order_by(CaseTemplate.position, CaseTemplate.created_at)).all()
    kayitli = {t.key for t in rows}
    return {
        "templates": [_ser_template(t) for t in rows],
        # Henüz eklenmemiş hazır tipler — panel "tek tıkla ekle" gösterir
        "suggested": [t for t in ONERILEN_TIPLER if t["key"] not in kayitli],
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_template(
    body: TemplateCreate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    _get_storefront_store(db, user.tenant_id, body.store_id)
    if db.scalar(select(CaseTemplate).where(
            CaseTemplate.store_id == body.store_id, CaseTemplate.key == body.key)):
        raise HTTPException(409, "Bu anahtara sahip şablon zaten var")
    t = CaseTemplate(tenant_id=user.tenant_id, store_id=body.store_id,
                     key=body.key, label=body.label,
                     description=body.description, position=body.position)
    db.add(t)
    activity.record(db, user, "sablon_ekle", store_id=body.store_id,
                    entity_type="kilif_sablonu", entity_label=body.label)
    db.commit()
    db.refresh(t)
    return _ser_template(t)


@router.patch("/{template_id}", response_model=dict)
def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    t = db.scalar(select(CaseTemplate).where(
        CaseTemplate.id == template_id, CaseTemplate.tenant_id == user.tenant_id))
    if not t:
        raise HTTPException(404, "Şablon bulunamadı")
    updates = body.model_dump(exclude_unset=True)
    if updates.get("image_path"):
        updates["image_path"] = updates["image_path"].removeprefix("/storage/")
    if updates.get("cutouts") is not None:
        temiz = []
        for c in updates["cutouts"]:
            if float(c["x"]) + float(c["w"]) > 1 or float(c["y"]) + float(c["h"]) > 1:
                raise HTTPException(422, "Basılamayan bölge şablonun dışına taşıyor")
            temiz.append({k: (float(v) if isinstance(v, Decimal) else v)
                          for k, v in c.items() if v is not None})
        updates["cutouts"] = temiz
    for k, v in updates.items():
        setattr(t, k, v)
    # Baskı alanı görselin dışına taşmasın (editör ve baskı hesabı bozulur)
    if float(t.area_x) + float(t.area_w) > 1 or float(t.area_y) + float(t.area_h) > 1:
        raise HTTPException(422, "Baskı alanı şablonun dışına taşıyor")
    activity.record(db, user, "sablon_guncelle", store_id=t.store_id,
                    entity_type="kilif_sablonu", entity_id=t.id, entity_label=t.label,
                    detail={"alanlar": list(updates)})
    db.commit()
    db.refresh(t)
    return _ser_template(t)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    t = db.scalar(select(CaseTemplate).where(
        CaseTemplate.id == template_id, CaseTemplate.tenant_id == user.tenant_id))
    if not t:
        raise HTTPException(404, "Şablon bulunamadı")
    activity.record(db, user, "sablon_sil", store_id=t.store_id,
                    entity_type="kilif_sablonu", entity_label=t.label)
    db.delete(t)
    db.commit()


@router.post("/{template_id}/image", response_model=dict)
async def upload_template_image(
    template_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Boş kılıf görseli (mockup) yükle — müşterinin tuvalinde zemin olur."""
    t = db.scalar(select(CaseTemplate).where(
        CaseTemplate.id == template_id, CaseTemplate.tenant_id == user.tenant_id))
    if not t:
        raise HTTPException(404, "Şablon bulunamadı")
    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(422, "Dosya gerekli")
    data = await file.read()
    try:
        # Şablon görseli saydamlık taşıyabilir (şeffaf kılıf) → orijinal korunur
        url, _prev, _w, _h = storage_svc.save_design_original(
            user.tenant_id, t.store_id, data,
            getattr(file, "filename", None) or "sablon.png")
    except ValueError as e:
        raise HTTPException(422, str(e))
    t.image_path = url.removeprefix("/storage/")
    db.commit()
    return {"image_url": url}


# ─── Panel: sipariş edilen tasarımlar ────────────────────────

@router.get("/designs/{design_id}", response_model=dict)
def get_design(
    design_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Sipariş detayındaki tasarım kartı — önizleme + baskı dosyası."""
    d = db.scalar(select(CustomerDesign).where(
        CustomerDesign.id == design_id, CustomerDesign.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Tasarım bulunamadı")
    t = db.scalar(select(CaseTemplate).where(
        CaseTemplate.store_id == d.store_id, CaseTemplate.key == d.template_key))
    kullanilan = [
        {"id": str(a.id), "original_url": f"/storage/{a.original_path}",
         "width": a.width, "height": a.height, "filename": a.filename}
        for a in db.scalars(select(DesignAsset).where(DesignAsset.id.in_(
            [str(l.get("asset_id")) for l in (d.layers or [])
             if l.get("type") == "image" and l.get("asset_id")] or ["00000000-0000-0000-0000-000000000000"]
        ))).all()
    ]
    return {
        "id": str(d.id),
        "name": d.name,
        "status": d.status,
        "template": t.label if t else d.template_key,
        "preview_url": f"/storage/{d.preview_path}" if d.preview_path else None,
        "print_url": f"/storage/{d.print_path}" if d.print_path else None,
        "print_size": ({"px_w": round(t.print_width_mm / 25.4 * t.print_dpi),
                        "px_h": round(t.print_height_mm / 25.4 * t.print_dpi),
                        "mm": f"{t.print_width_mm}×{t.print_height_mm} mm",
                        "dpi": t.print_dpi} if t else None),
        "layer_count": len(d.layers or []),
        # Müşterinin yüklediği ORİJİNAL dosyalar — rötuş için doğrudan indirilir
        "assets": kullanilan,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.post("/designs/{design_id}/render", response_model=dict)
def rerender_design(
    design_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Baskı dosyasını yeniden üret (şablon ölçüsü değiştiyse veya hata olduysa)."""
    from app.services.design_render import render_print_file

    d = db.scalar(select(CustomerDesign).where(
        CustomerDesign.id == design_id, CustomerDesign.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Tasarım bulunamadı")
    t = db.scalar(select(CaseTemplate).where(
        CaseTemplate.store_id == d.store_id, CaseTemplate.key == d.template_key))
    if not t:
        raise HTTPException(422, "Tasarımın kılıf şablonu bulunamadı")
    try:
        veri = render_print_file(db, d, t)
    except ValueError as e:
        raise HTTPException(422, str(e))
    d.print_path = storage_svc.save_design_render(
        d.tenant_id, d.store_id, d.id, veri, "baski").removeprefix("/storage/")
    db.commit()
    return {"print_url": f"/storage/{d.print_path}", "bytes": len(veri)}
