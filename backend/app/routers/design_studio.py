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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import (
    CaseTemplate, CustomerDesign, DesignAsset, DesignOverlay, Store, User,
)
from app.services import activity
from app.services import storage as storage_svc
from starlette.concurrency import run_in_threadpool

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
        url, _prev, _w, _h = await run_in_threadpool(
            storage_svc.save_design_original,
            user.tenant_id, t.store_id, data,
            getattr(file, "filename", None) or "sablon.png")
    except ValueError as e:
        raise HTTPException(422, str(e))
    t.image_path = url.removeprefix("/storage/")
    db.commit()
    return {"image_url": url}


# ─── Panel: hazır tasarım şablonları (overlay) ───────────────
# Müşterinin tasarımının ÜSTÜNE binen şeffaf PNG'ler (fotoğraf çerçevesi vb.).
# Katman sırası her yerde aynı: görseller → overlay → yazılar.

def _ser_overlay(o: DesignOverlay) -> dict:
    return {
        "id": str(o.id),
        "label": o.label,
        "case_template_id": str(o.case_template_id) if o.case_template_id else None,
        "image_url": f"/storage/{o.image_path}",
        "thumb_url": f"/storage/{o.thumb_path}" if o.thumb_path else f"/storage/{o.image_path}",
        "mod": o.mod,
        "kategori": o.kategori,
        "sadece_urunde": o.sadece_urunde,
        "alanlar": [
            {**a, "image_url": f"/storage/{a['image_path']}" if a.get("image_path") else None}
            for a in (o.alanlar or [])
        ],
        "forma": _ser_forma(o.forma),
        "position": o.position,
        "is_active": o.is_active,
    }


def _ser_forma(f: dict | None) -> dict | None:
    """Panel için forma ayarı — yüklenen amblemlere adres eklenir."""
    if not f:
        return None
    return {**f, "ozel_amblemler": [
        {**a, "url": f"/storage/{a['image_path']}"} for a in (f.get("ozel_amblemler") or [])]}


class OverlayAlan(BaseModel):
    """Kısıtlı şablonda müşterinin doldurabildiği tek bir alan."""
    key: str = Field(..., min_length=1, max_length=30, pattern="^[a-z0-9_-]+$")
    tip: str = Field(..., pattern="^(yazi|gorsel|foto|ilerleme)$")
    etiket: str = Field(..., min_length=1, max_length=60)
    x: Decimal = Field(Decimal("0.1"), ge=0, le=1)
    y: Decimal = Field(Decimal("0.1"), ge=0, le=1)
    w: Decimal = Field(Decimal("0.8"), gt=0, le=1)
    h: Decimal | None = Field(None, gt=0, le=1)          # görsel alanı
    # yazı alanı
    varsayilan: str | bool | None = None
    max: int | None = Field(None, ge=1, le=40)
    size: Decimal | None = Field(None, gt=0, le=0.6)
    font: str | None = Field(None, max_length=30)
    renk: str | None = Field(None, max_length=9)
    hiza: str | None = Field(None, pattern="^(left|center|right)$")
    # Yazı çerçeveye sığmazsa punto otomatik küçülsün mü (varsayılan: evet).
    # DİKKAT: foto alanının "sigdir" alanı METİNdir ("kapla"/"sigdir") — aynı
    # adı kullanmak Pydantic'te ikinci tanımın birinciyi ezmesine ve panelin
    # "Input should be a valid string" hatası almasına yol açmıştı.
    otomatik_kucult: bool | None = None
    # görsel alanı — dosya ayrı uçtan yüklenir, burada yolu taşınır
    image_path: str | None = Field(None, max_length=500)
    # foto alanı — MÜŞTERİNİN yükleyeceği görselin çerçeveye oturma biçimi
    sigdir: str | None = Field(None, pattern="^(kapla|sigdir)$")
    # ilerleme alanı — hangi süre alanlarından oran hesaplanacak
    kaynak_gecen: str | None = Field(None, max_length=30)
    kaynak_toplam: str | None = Field(None, max_length=30)
    kalinlik: Decimal | None = Field(None, gt=0, le=0.2)
    boyut: Decimal | None = Field(None, gt=0, le=0.2)
    renk_pasif: str | None = Field(None, max_length=9)
    # true → şablonun ALTINA çizilir (delikli şablonda fotoğraf oradan görünür)
    arkada: bool | None = None


@router.get("/overlays/list", response_model=dict)
def list_overlays(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    _get_storefront_store(db, user.tenant_id, store_id)
    rows = db.scalars(select(DesignOverlay).where(
        DesignOverlay.store_id == store_id)
        .order_by(DesignOverlay.position, DesignOverlay.created_at)).all()
    return {"items": [_ser_overlay(o) for o in rows]}


@router.post("/overlays", response_model=dict)
async def create_overlay(
    request: Request,
    store_id: uuid.UUID = Query(...),
    label: str = Query(..., min_length=1, max_length=120),
    case_template_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Hazır şablon yükle. Şeffaf PNG önerilir — saydam kısımda müşterinin
    görseli görünür, dolu kısım (çerçeve) onun üstünü kapatır."""
    _get_storefront_store(db, user.tenant_id, store_id)
    if case_template_id and not db.scalar(select(CaseTemplate).where(
            CaseTemplate.id == case_template_id, CaseTemplate.store_id == store_id)):
        raise HTTPException(404, "Kılıf şablonu bulunamadı")

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(422, "Dosya gerekli")
    data = await file.read()
    try:
        # Saydamlık korunmalı → orijinal saklanır, tuval için hafif önizleme
        url, onizleme, _w, _h = await run_in_threadpool(
            storage_svc.save_design_original,
            user.tenant_id, store_id, data,
            getattr(file, "filename", None) or "hazir-sablon.png")
    except ValueError as e:
        raise HTTPException(422, str(e))

    o = DesignOverlay(
        tenant_id=user.tenant_id, store_id=store_id,
        case_template_id=case_template_id, label=label.strip()[:120],
        image_path=url.removeprefix("/storage/"),
        thumb_path=(onizleme or url).removeprefix("/storage/"),
        position=db.scalar(select(func.count()).select_from(DesignOverlay).where(
            DesignOverlay.store_id == store_id)) or 0,
    )
    db.add(o)
    activity.record(db, user, "hazir_sablon_ekle", store_id=store_id,
                    entity_type="hazir_sablon", entity_label=o.label)
    db.commit()
    db.refresh(o)
    return _ser_overlay(o)


class OverlayUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=120)
    case_template_id: uuid.UUID | None = None
    kategori: str | None = Field(None, max_length=60)
    sadece_urunde: bool | None = None
    mod: str | None = Field(None, pattern="^(serbest|kisitli)$")
    alanlar: list[OverlayAlan] | None = Field(None, max_length=12)
    # Forma tasarlayıcı ayarı — serbest sözlük, services/forma'da doğrulanır.
    # {"aktif": false} ya da null → kapatır.
    forma: dict | None = None
    position: int | None = None
    is_active: bool | None = None


@router.get("/forma/secenekler", response_model=dict)
def forma_secenekleri(user: User = Depends(require_permission("vitrin"))):
    """Panel forma ayarı için sabit listeler: desenler, hazır amblemler,
    önerilen fontlar, örnek renk takımları, yerleşik yasak kelimeler."""
    from app.services import forma, yasak_kelime
    return {
        "desenler": [{"key": k, "ad": v} for k, v in forma.DESENLER.items()],
        "amblemler": [{"key": k, "ad": v, "url": f"/storage/sablon/amblem/{k}.png"}
                      for k, v in forma.AMBLEMLER.items()],
        "fontlar": forma.VARSAYILAN_FONTLAR,
        "paletler": forma.VARSAYILAN_PALETLER,
        "yasak_yerlesik": len(yasak_kelime.ICEREN) + len(yasak_kelime.TAM),
    }


@router.patch("/overlays/{overlay_id}", response_model=dict)
def update_overlay(
    overlay_id: uuid.UUID,
    body: OverlayUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    o = db.scalar(select(DesignOverlay).where(
        DesignOverlay.id == overlay_id, DesignOverlay.tenant_id == user.tenant_id))
    if not o:
        raise HTTPException(404, "Hazır şablon bulunamadı")
    guncel = body.model_dump(exclude_unset=True)
    if guncel.get("alanlar") is not None:
        anahtarlar = set()
        temiz = []
        for a in guncel["alanlar"]:
            if a["key"] in anahtarlar:
                raise HTTPException(422, f"Aynı alan anahtarı iki kez: {a['key']}")
            anahtarlar.add(a["key"])
            if a["tip"] == "gorsel" and not a.get("image_path"):
                raise HTTPException(422, f"“{a['etiket']}” alanına görsel yüklenmedi")
            if a["tip"] == "ilerleme":
                yazilar = {x["key"] for x in guncel["alanlar"] if x["tip"] == "yazi"}
                for alan_adi, etiket in (("kaynak_gecen", "geçen süre"),
                                         ("kaynak_toplam", "toplam süre")):
                    if a.get(alan_adi) not in yazilar:
                        raise HTTPException(
                            422, f"“{a['etiket']}” için {etiket} alanı seçilmedi — "
                                 "önce o süreyi bir yazı alanı olarak ekleyin")
            temiz.append({
                k: (float(v) if isinstance(v, Decimal) else v)
                for k, v in a.items() if v is not None
            })
        guncel["alanlar"] = temiz
    if "forma" in guncel:
        from app.services import forma as forma_svc
        guncel["forma"] = forma_svc.yapilandirma_temizle(guncel["forma"], o.forma)
    for k, v in guncel.items():
        setattr(o, k, v)
    if o.mod == "kisitli" and not (o.alanlar or []):
        raise HTTPException(422, "Kısıtlı şablonda en az bir alan tanımlanmalı")
    if o.forma and o.mod != "kisitli":
        raise HTTPException(422, "Forma tasarlayıcı yalnız kısıtlı şablonda açılabilir")
    db.commit()
    db.refresh(o)
    return _ser_overlay(o)


@router.post("/overlays/{overlay_id}/alan-gorseli", response_model=dict)
async def upload_overlay_field_image(
    overlay_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Kısıtlı şablondaki açılabilir öğenin görseli (bayrak, logo…).
    Şeffaf PNG önerilir; dosya yüklenir, alana bağlama PATCH ile yapılır."""
    o = db.scalar(select(DesignOverlay).where(
        DesignOverlay.id == overlay_id, DesignOverlay.tenant_id == user.tenant_id))
    if not o:
        raise HTTPException(404, "Hazır şablon bulunamadı")
    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(422, "Dosya gerekli")
    data = await file.read()
    try:
        url, _prev, _w, _h = await run_in_threadpool(
            storage_svc.save_design_original,
            user.tenant_id, o.store_id, data,
            getattr(file, "filename", None) or "alan.png")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"image_path": url.removeprefix("/storage/"), "image_url": url}


class OverlayKopya(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)


@router.post("/overlays/{overlay_id}/kopyala", response_model=dict)
def kopyala_overlay(
    overlay_id: uuid.UUID,
    body: OverlayKopya,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Hazır şablonu çoğalt — aynı forma, farklı renkte hazır ürünler
    ("Sarı-Kırmızı", "Siyah-Beyaz"…) tek tek sıfırdan kurulmasın.
    Görsel dosyaları paylaşılır (kopyalanmaz); alanlar ve forma ayarı kopyalanır."""
    import copy

    o = db.scalar(select(DesignOverlay).where(
        DesignOverlay.id == overlay_id, DesignOverlay.tenant_id == user.tenant_id))
    if not o:
        raise HTTPException(404, "Hazır şablon bulunamadı")
    yeni = DesignOverlay(
        tenant_id=o.tenant_id, store_id=o.store_id, case_template_id=o.case_template_id,
        label=body.label.strip()[:120], image_path=o.image_path, thumb_path=o.thumb_path,
        mod=o.mod, sadece_urunde=o.sadece_urunde, kategori=o.kategori,
        alanlar=copy.deepcopy(o.alanlar or []), forma=copy.deepcopy(o.forma),
        position=(o.position or 0) + 1, is_active=o.is_active,
    )
    db.add(yeni)
    activity.record(db, user, "hazir_sablon_kopyala", store_id=o.store_id,
                    entity_type="hazir_sablon", entity_label=yeni.label)
    db.commit()
    db.refresh(yeni)
    return _ser_overlay(yeni)


@router.post("/overlays/{overlay_id}/amblem", response_model=dict)
async def upload_forma_amblem(
    overlay_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Forma tasarlayıcıya mağazanın KENDİ amblemini ekler.

    Yüklenen görsel tek renkli MASKEYE çevrilir (müşteri rengini seçecek):
    saydam zeminli PNG'de saydamlık, düz zeminli görselde koyuluk şekli
    belirler. Amblem şablonun forma ayarına eklenir ve müşteriye sunulur."""
    from sqlalchemy.orm.attributes import flag_modified

    o = db.scalar(select(DesignOverlay).where(
        DesignOverlay.id == overlay_id, DesignOverlay.tenant_id == user.tenant_id))
    if not o:
        raise HTTPException(404, "Hazır şablon bulunamadı")
    if not (o.forma or {}).get("aktif"):
        raise HTTPException(422, "Önce forma tasarlayıcıyı açıp kaydedin")
    if len(o.forma.get("ozel_amblemler") or []) >= 20:
        raise HTTPException(422, "En fazla 20 özel amblem eklenebilir")
    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(422, "Dosya gerekli")
    ad = str(form.get("ad") or "").strip()[:30] or "Amblem"
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(422, "Amblem dosyası en fazla 8 MB olabilir")
    try:
        maske = await run_in_threadpool(_amblem_maskesi, data)
        url, _prev, _w, _h = await run_in_threadpool(
            storage_svc.save_design_original, user.tenant_id, o.store_id, maske, "amblem.png")
    except ValueError as e:
        raise HTTPException(422, str(e))
    kayit = {"key": f"ozel-{uuid.uuid4().hex[:8]}", "ad": ad,
             "image_path": url.removeprefix("/storage/")}
    f = dict(o.forma)
    f["ozel_amblemler"] = [*(f.get("ozel_amblemler") or []), kayit]
    f["amblemler"] = [*(f.get("amblemler") or []), kayit["key"]]
    o.forma = f
    flag_modified(o, "forma")
    db.commit()
    db.refresh(o)
    return _ser_overlay(o)


def _amblem_maskesi(data: bytes) -> bytes:
    """Yüklenen görsel → beyaz, saydam zeminli maske PNG (en fazla 600 px)."""
    import io

    from PIL import Image, ImageOps

    try:
        g = Image.open(io.BytesIO(data))
        g.load()
    except Exception:  # noqa: BLE001
        raise ValueError("Görsel okunamadı — PNG ya da JPG yükleyin")
    g = g.convert("RGBA")
    alfa = g.getchannel("A")
    if alfa.getextrema()[0] >= 250:
        # Saydamlık yok (düz zemin): koyu yerler şekil sayılır
        alfa = ImageOps.invert(g.convert("L"))
    kutu = alfa.point(lambda v: 255 if v > 12 else 0).getbbox()
    if not kutu:
        raise ValueError("Görselde şekil bulunamadı — saydam zeminli PNG yükleyin")
    alfa = alfa.crop(kutu)
    alfa.thumbnail((600, 600), Image.LANCZOS)
    cikti = Image.new("RGBA", alfa.size, (255, 255, 255, 0))
    cikti.putalpha(alfa)
    buf = io.BytesIO()
    cikti.save(buf, "PNG", optimize=True)
    return buf.getvalue()


@router.delete("/overlays/{overlay_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_overlay(
    overlay_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    o = db.scalar(select(DesignOverlay).where(
        DesignOverlay.id == overlay_id, DesignOverlay.tenant_id == user.tenant_id))
    if not o:
        raise HTTPException(404, "Hazır şablon bulunamadı")
    activity.record(db, user, "hazir_sablon_sil", store_id=o.store_id,
                    entity_type="hazir_sablon", entity_label=o.label)
    db.delete(o)
    db.commit()


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
        # Sürüm damgalı — "yeniden üret" sonrası önbellekten eski dosya gelmesin
        "print_url": storage_svc.design_render_url(d.print_path),
        "print_pdf_url": storage_svc.design_render_url(d.print_pdf_path),
        # Rötuş sonrası numune — müşteri onayında bu gösterilir
        "proof_url": f"/storage/{d.proof_path}" if d.proof_path else None,
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
    """Baskı dosyalarını yeniden üret (şablon ölçüsü değiştiyse veya hata olduysa).

    İkisi birden üretilir: ekranla birebir PNG + matbaa/RIP için vektörel
    CMYK PDF."""
    from app.services.design_pdf import render_print_pdf
    from app.services.design_render import render_print_file
    from app.services.icc import magaza_icc

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
    pdf_hata = None
    try:
        pdf = render_print_pdf(db, d, t, icc=magaza_icc(db, d.store_id))
        d.print_pdf_path = storage_svc.save_design_render(
            d.tenant_id, d.store_id, d.id, pdf, "baski-pdf").removeprefix("/storage/")
    except Exception as e:  # noqa: BLE001 — PNG yine de elde kalsın
        pdf_hata = str(e)[:200]
    db.commit()
    return {
        "print_url": storage_svc.design_render_url(d.print_path),
        "print_pdf_url": storage_svc.design_render_url(d.print_pdf_path),
        "bytes": len(veri),
        "pdf_hata": pdf_hata,
    }


@router.post("/designs/{design_id}/proof", response_model=dict)
async def upload_proof(
    design_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Rötuş/CMYK sonrası numune görselini yükle.

    Müşteri onay ekranında ARTIK BU gösterilir — stüdyo önizlemesi değil.
    Böylece müşteri gerçekte basılacak halini onaylar.
    """
    d = db.scalar(select(CustomerDesign).where(
        CustomerDesign.id == design_id, CustomerDesign.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Tasarım bulunamadı")
    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(422, "Dosya gerekli")
    data = await file.read()
    try:
        url, _prev, _w, _h = await run_in_threadpool(
            storage_svc.save_design_original,
            d.tenant_id, d.store_id, data,
            getattr(file, "filename", None) or "numune.png")
    except ValueError as e:
        raise HTTPException(422, str(e))
    d.proof_path = url.removeprefix("/storage/")
    activity.record(db, user, "numune_yukle", store_id=d.store_id, entity_type="tasarim",
                    entity_id=d.id, entity_label=d.name)
    db.commit()
    return {"proof_url": url}
