"""
Telefon Modelleri — /api/phone-models/*

Panelden telefon modeli ekle / düzenle / sil. DB'ye eklenen modeller baseline'ı
(gizli case_dimensions, 339 model) EZER. Yeni telefon çıkınca deploy gerektirmez.

GÜVENLİK: Baseline ölçüleri ASLA dönülmez. Sadece DB kayıtlarının (tenant'ın
kendi eklediği) ölçüsü gösterilir. /check endpoint'i baseline için yalnızca
"tanınıyor" der, ölçü vermez.

Endpoint'ler:
- GET    /api/phone-models            → DB modelleri + baseline adedi
- POST   /api/phone-models            → ekle (baseline override veya yeni model)
- PATCH  /api/phone-models/{id}       → güncelle
- DELETE /api/phone-models/{id}       → sil
- POST   /api/phone-models/check      → model tanınıyor mu? (kaynak: db/baseline)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import PhoneModel, User
from app.services import phone_models as pm
from app.services._private import case_dimensions as cd

router = APIRouter(prefix="/api/phone-models", tags=["phone-models"])


# ─── Schemas ─────────────────────────────────────────────────
class PhoneModelCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    brand: str | None = Field(None, max_length=40)
    # Ölçüler OPSİYONEL: boş bırakılırsa ve model baseline'da tanınıyorsa oradan
    # (gizli kalarak) alınır — sadece mockup eklemek için ölçü bilmeye gerek yok.
    width_cm: float | None = Field(None, gt=0, lt=40)
    height_cm: float | None = Field(None, gt=0, lt=40)
    radius_cm: float | None = Field(None, ge=0, lt=10)
    spec_key: str | None = Field(None, max_length=60)  # boşsa display_name'den türetilir
    notes: str | None = None


class PhoneModelUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=120)
    brand: str | None = Field(None, max_length=40)
    width_cm: float | None = Field(None, gt=0, lt=40)
    height_cm: float | None = Field(None, gt=0, lt=40)
    radius_cm: float | None = Field(None, ge=0, lt=10)
    is_active: bool | None = None
    notes: str | None = None
    mockup_rect: dict | None = None  # {x,y,w,h} kesirsel (0..1)
    mockup_variation: str | None = None  # boş/SİYAH=varsayılan; aksi halde mockup_variants[VAR].rect


class CheckRequest(BaseModel):
    model: str


# ─── Helpers ─────────────────────────────────────────────────
def _var_key(variation: str | None) -> str | None:
    """Varyasyon -> mockup_variants anahtarı. Boş/SİYAH -> None (varsayılan şablon)."""
    if not variation or not str(variation).strip():
        return None
    from app.services.mockup import canon_variation
    vk = canon_variation(variation)
    return None if vk == "SİYAH" else vk


def _varsayilan_var_mi(db: Session, tenant_id, var_key: str, haric_id=None) -> bool:
    """Bu varyasyon için başka bir modelde geçerli şablon var mı.

    Varsa yeni yüklenen şablon varsayılan YAPILMAZ; yalnızca kendi modelinde
    geçerli olur. Böylece modele özel bir şablon yüklemek, herkes için kullanılan
    varsayılanı kaçırmıyor.
    """
    from app.services.mockup import _gecerli_varyant
    for x in db.scalars(select(PhoneModel).where(
            PhoneModel.tenant_id == tenant_id,
            PhoneModel.mockup_variants.isnot(None))).all():
        if haric_id is not None and x.id == haric_id:
            continue
        if _gecerli_varyant((x.mockup_variants or {}).get(var_key)):
            return True
    return False


def _serialize(m: PhoneModel) -> dict:
    return {
        "id": str(m.id),
        "spec_key": m.spec_key,
        "display_name": m.display_name,
        "brand": m.brand,
        "width_cm": m.width_cm,
        "height_cm": m.height_cm,
        "radius_cm": m.radius_cm,
        "is_active": m.is_active,
        "notes": m.notes,
        "mockup_template_url": m.mockup_template_url,
        "mockup_rect": m.mockup_rect,
        "mockup_variants": m.mockup_variants or {},
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


# ─── Endpoints ───────────────────────────────────────────────
@router.get("", response_model=dict)
def list_models(
    search: str | None = Query(None),
    include_baseline: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(PhoneModel)
        .where(PhoneModel.tenant_id == user.tenant_id)
        .order_by(desc(PhoneModel.created_at))
    ).all()

    out = []
    for m in rows:
        if search:
            q = search.lower()
            hay = " ".join(filter(None, [
                m.display_name, m.brand, m.spec_key, m.notes,
            ])).lower()
            if q not in hay:
                continue
        out.append(_serialize(m))

    # Baseline modelleri de ekle (manuel eklenmemis ama kalip taninan 339 model)
    if include_baseline:
        # Kanonik anahtara gore tekille: DB'de '15' ya da 'IPHONE-15' varsa baseline ikizi eklenmez.
        _existing_canon = {pm.canonical_key(m.get("spec_key") or "") for m in out}
        for bkey in pm.baseline_keys():
            # Cıplak Apple takma adlarini ('15', 'XR' ...) listede GOSTERME — 'IPHONE-15' kalir.
            if pm.is_apple_alias_key(bkey):
                continue
            if pm.canonical_key(bkey) in _existing_canon:
                continue
            disp = pm.baseline_display_name(bkey)  # 'SAMSUNG-A15' -> 'Samsung A15'
            if search:
                s = search.lower()
                if s not in bkey.lower() and s not in disp.lower():
                    continue
            row = {
                "id": f"baseline:{bkey}",
                "spec_key": bkey,
                "display_name": disp,
                "brand": None,
                "is_baseline": True,
            }
            # Baseline ölçüleri ticari değerimiz — KİRACIYA gösterilmez. Ama platform
            # sahibi kendi kataloğunu görmeli ve gerektiğinde düzeltebilmeli.
            if user.is_platform_admin:
                _spec = cd.get_spec(bkey)
                if _spec:
                    row["width_cm"], row["height_cm"], row["radius_cm"] = (
                        _spec[0], _spec[1], _spec[2],
                    )
            out.append(row)

    return {
        "items": out,
        "total": len(out),
        "db_total": len(rows),
        "baseline_count": pm.baseline_count(),
    }


class OlcuTanimlaIn(BaseModel):
    """Kalıp PDF hatasından doğrudan ölçü tanımlama."""
    model: str = Field(..., min_length=1, max_length=160)
    width_cm: float = Field(..., gt=0, lt=40)
    height_cm: float = Field(..., gt=0, lt=40)
    radius_cm: float = Field(0, ge=0, lt=10)


@router.post("/olcu-tanimla", response_model=dict)
def olcu_tanimla(
    body: OlcuTanimlaIn,
    user: User = Depends(require_permission("telefon_modelleri")),
    db: Session = Depends(get_db),
):
    """Model adindan olcu tanimla — VARSA gunceller, YOKSA olusturur.

    Kalip PDF'i "olcusu tanimli degil" diyerek durdugunda panel dogrudan bunu
    cagirir; kullanicinin Telefon Modelleri ekranina gidip kaydi aramasi
    gerekmez.

    Anahtar, PDF motorunun ARADIGI anahtarla ayni fonksiyondan uretilir
    (pm.normalize_key). Baska turlu uretirsek kullanici olcuyu girer ama hata
    devam eder — en can sikici hata turu.
    """
    key = pm.normalize_key(body.model)
    if not key:
        raise HTTPException(400, "Model adindan anahtar uretilemedi")

    mevcut = db.scalar(select(PhoneModel).where(
        PhoneModel.tenant_id == user.tenant_id, PhoneModel.spec_key == key))
    if mevcut is None:
        mevcut = PhoneModel(
            tenant_id=user.tenant_id, spec_key=key,
            display_name=body.model.strip()[:120], is_active=True,
            width_cm=body.width_cm, height_cm=body.height_cm,
            radius_cm=body.radius_cm)
        db.add(mevcut)
        olusturuldu = True
    else:
        mevcut.width_cm = body.width_cm
        mevcut.height_cm = body.height_cm
        mevcut.radius_cm = body.radius_cm
        if not mevcut.is_active:
            mevcut.is_active = True
        olusturuldu = False
    db.commit()
    db.refresh(mevcut)

    # Kaydettik ama PDF motoru gercekten bulabiliyor mu? Soylemeden once SOR.
    bulunan = pm.get_spec(db, user.tenant_id, body.model)
    return {
        "ok": True,
        "olusturuldu": olusturuldu,
        "id": str(mevcut.id),
        "spec_key": mevcut.spec_key,
        "display_name": mevcut.display_name,
        "olcu": {"width_cm": mevcut.width_cm, "height_cm": mevcut.height_cm,
                 "radius_cm": mevcut.radius_cm},
        "dogrulandi": bool(bulunan and bulunan[0] and bulunan[1]),
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_model(
    body: PhoneModelCreate,
    user: User = Depends(require_permission("telefon_modelleri")),
    db: Session = Depends(get_db),
):
    key = (body.spec_key or "").strip().upper() or pm.normalize_key(body.display_name)
    if not key:
        raise HTTPException(400, "Geçerli bir model adı gir (anahtar üretilemedi)")

    existing = db.scalar(
        select(PhoneModel).where(
            PhoneModel.tenant_id == user.tenant_id,
            PhoneModel.spec_key == key,
        )
    )
    if existing:
        raise HTTPException(
            409,
            f"Bu model anahtarı zaten var: '{key}'. Düzenlemek için mevcut kaydı kullan.",
        )

    # Ölçü girilmediyse baseline'dan (gizli) al — böylece tanınan modele sadece
    # mockup eklemek için ölçü bilmeye gerek kalmaz.
    w, h, r = body.width_cm, body.height_cm, body.radius_cm
    if w is None or h is None:
        spec = cd.get_spec(body.spec_key or body.display_name)
        if spec:
            w = w if w is not None else spec[0]
            h = h if h is not None else spec[1]
            r = r if r is not None else spec[2]
        else:
            raise HTTPException(
                400,
                "Bu model baseline kataloğunda tanınmıyor — genişlik ve yükseklik (cm) girmelisin.",
            )

    m = PhoneModel(
        tenant_id=user.tenant_id,
        spec_key=key,
        display_name=body.display_name.strip(),
        brand=(body.brand or "").strip() or None,
        width_cm=w,
        height_cm=h,
        radius_cm=r or 0,
        notes=body.notes,
        is_active=True,
    )
    db.add(m)
    db.commit()
    db.refresh(m)

    # baseline'da da var mıydı → override bilgisi
    overrides_baseline = cd.get_spec(body.display_name) is not None

    res = _serialize(m)
    res["overrides_baseline"] = overrides_baseline
    return res


@router.patch("/{model_id}", response_model=dict)
def update_model(
    model_id: uuid.UUID,
    body: PhoneModelUpdate,
    user: User = Depends(require_permission("telefon_modelleri")),
    db: Session = Depends(get_db),
):
    m = db.scalar(
        select(PhoneModel).where(
            PhoneModel.id == model_id,
            PhoneModel.tenant_id == user.tenant_id,
        )
    )
    if not m:
        raise HTTPException(404, "Model bulunamadı")

    if body.display_name is not None:
        m.display_name = body.display_name.strip()
    if body.brand is not None:
        m.brand = body.brand.strip() or None
    if body.width_cm is not None:
        m.width_cm = body.width_cm
    if body.height_cm is not None:
        m.height_cm = body.height_cm
    if body.radius_cm is not None:
        m.radius_cm = body.radius_cm
    if body.is_active is not None:
        m.is_active = body.is_active
    if body.notes is not None:
        m.notes = body.notes
    if body.mockup_rect is not None:
        r = body.mockup_rect or {}
        rect = None
        _q = r.get("quad")
        _q_ok = (isinstance(_q, (list, tuple)) and len(_q) == 4
                 and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in _q))
        if _q_ok:
            # Perspektif quad (4 nokta TL,TR,BR,BL) — kesirsel, 0..1 kıstır
            try:
                rect = {"quad": [[min(1.0, max(0.0, round(float(p[0]), 5))),
                                  min(1.0, max(0.0, round(float(p[1]), 5)))] for p in _q]}
                if r.get("overlay"):
                    rect["overlay"] = True
            except (TypeError, ValueError):
                rect = None
        elif all(k in r for k in ("x", "y", "w", "h")):
            rect = {k: round(float(r[k]), 5) for k in ("x", "y", "w", "h")}
            try:
                if "radius" in r:
                    rect["radius"] = min(0.5, max(0.0, round(float(r["radius"]), 5)))
            except (TypeError, ValueError):
                pass
            try:
                if "shadow" in r:
                    rect["shadow"] = min(1.0, max(0.0, round(float(r["shadow"]), 3)))
            except (TypeError, ValueError):
                pass
            cuts = r.get("cutouts")
            if isinstance(cuts, list):
                out_cuts = []
                for c in cuts[:10]:
                    if isinstance(c, dict) and all(k in c for k in ("x", "y", "w", "h")):
                        item = {k: round(float(c[k]), 5) for k in ("x", "y", "w", "h")}
                        try:
                            item["radius"] = min(0.5, max(0.0, round(float(c.get("radius", 0.2)), 5)))
                        except (TypeError, ValueError):
                            item["radius"] = 0.2
                        out_cuts.append(item)
                if out_cuts:
                    rect["cutouts"] = out_cuts
            else:
                # Geriye dönük: tek 'camera' alanı → cutouts
                cam = r.get("camera")
                if isinstance(cam, dict) and all(k in cam for k in ("x", "y", "w", "h")):
                    rect["cutouts"] = [{**{k: round(float(cam[k]), 5) for k in ("x", "y", "w", "h")}, "radius": 0.18}]
            if r.get("overlay"):
                rect["overlay"] = True
        # Persist — quad ya da x/y/w/h rect'i (varyasyona ya da varsayilana)
        if rect is not None:
            vk = _var_key(body.mockup_variation)
            if vk:
                variants = dict(m.mockup_variants or {})
                entry = dict(variants.get(vk) or {})
                entry["rect"] = rect
                variants[vk] = entry
                m.mockup_variants = variants
            else:
                m.mockup_rect = rect
        elif not r:
            vk = _var_key(body.mockup_variation)
            if vk:
                variants = dict(m.mockup_variants or {})
                if vk in variants:
                    variants[vk] = {**variants[vk], "rect": None}
                    m.mockup_variants = variants
            else:
                m.mockup_rect = None

    db.commit()
    db.refresh(m)
    return _serialize(m)


@router.post("/{model_id}/mockup-template", response_model=dict)
def upload_mockup_template(
    model_id: uuid.UUID,
    file: UploadFile = File(...),
    variation: str | None = Query(None),  # boş/SİYAH=varsayılan; BEYAZ/ŞEFFAF/PARLAK/MAGSAFE
    user: User = Depends(require_permission("telefon_modelleri")),
    db: Session = Depends(get_db),
):
    """Telefon modeli için gerçek ürün fotoğrafı (mockup şablonu) yükle.
    variation verilirse o varyasyona özel şablon (mockup_variants) olarak saklanır."""
    m = db.scalar(select(PhoneModel).where(
        PhoneModel.id == model_id, PhoneModel.tenant_id == user.tenant_id))
    if not m:
        raise HTTPException(404, "Model bulunamadı")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise HTTPException(400, "İzin verilen formatlar: png, jpg, webp")
    data = file.file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Görsel çok büyük (max 5 MB)")
    from app.services import storage
    vk = _var_key(variation)
    if vk:
        url = storage.save_logo(user.tenant_id, f"mockup-{model_id}-{vk}", data, ext)
        variants = dict(m.mockup_variants or {})
        entry = dict(variants.get(vk) or {})
        entry["template_url"] = url
        # Bu varyasyonun İLK şablonuysa tüm modeller için varsayılan olsun —
        # parlak/magsafe fotoğrafı modelden modele değişmiyor. Sonradan başka bir
        # modele şablon yüklenirse o YALNIZCA kendi modelinde geçerli olur.
        if not entry.get("varsayilan") and not _varsayilan_var_mi(db, user.tenant_id, vk, m.id):
            entry["varsayilan"] = True
        variants[vk] = entry
        m.mockup_variants = variants
    else:
        m.mockup_template_url = storage.save_logo(user.tenant_id, f"mockup-{model_id}", data, ext)
    db.commit()
    db.refresh(m)
    return _serialize(m)


@router.post("/{model_id}/mockup-varsayilan", response_model=dict)
def set_mockup_varsayilan(
    model_id: uuid.UUID,
    variation: str = Query(...),
    aktif: bool = Query(True),
    user: User = Depends(require_permission("telefon_modelleri")),
    db: Session = Depends(get_db),
):
    """Bu modelin varyasyon şablonunu TÜM modeller için varsayılan yap/kaldır.

    Varyasyon başına tek varsayılan olur; işaretlenince diğer modellerdeki
    işaret temizlenir. Kendi şablonu olan model her zaman kendininkini kullanır,
    varsayılan yalnızca şablonu OLMAYAN modelleri etkiler.
    """
    vk = _var_key(variation)
    if not vk:
        raise HTTPException(400, "Varsayılan yalnızca varyasyon şablonları için geçerli")
    m = db.scalar(select(PhoneModel).where(
        PhoneModel.id == model_id, PhoneModel.tenant_id == user.tenant_id))
    if not m:
        raise HTTPException(404, "Model bulunamadı")
    variants = dict(m.mockup_variants or {})
    entry = dict(variants.get(vk) or {})
    if not entry.get("template_url"):
        raise HTTPException(400, "Bu modelde bu varyasyon için şablon yok")

    if aktif:
        # Varyasyon başına TEK varsayılan — diğerlerini temizle.
        for x in db.scalars(select(PhoneModel).where(
                PhoneModel.tenant_id == user.tenant_id,
                PhoneModel.id != m.id,
                PhoneModel.mockup_variants.isnot(None))).all():
            xv = dict(x.mockup_variants or {})
            e = xv.get(vk)
            if isinstance(e, dict) and e.get("varsayilan"):
                xv[vk] = {**e, "varsayilan": False}
                x.mockup_variants = xv
        entry["varsayilan"] = True
    else:
        entry["varsayilan"] = False
    variants[vk] = entry
    m.mockup_variants = variants
    db.commit()
    db.refresh(m)
    return _serialize(m)


@router.delete("/{model_id}/mockup-template", response_model=dict)
def delete_mockup_template(
    model_id: uuid.UUID,
    variation: str | None = Query(None),
    user: User = Depends(require_permission("telefon_modelleri")),
    db: Session = Depends(get_db),
):
    m = db.scalar(select(PhoneModel).where(
        PhoneModel.id == model_id, PhoneModel.tenant_id == user.tenant_id))
    if not m:
        raise HTTPException(404, "Model bulunamadı")
    vk = _var_key(variation)
    if vk:
        variants = dict(m.mockup_variants or {})
        variants.pop(vk, None)
        m.mockup_variants = variants or None
    else:
        m.mockup_template_url = None
        m.mockup_rect = None
    db.commit()
    db.refresh(m)
    return _serialize(m)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: uuid.UUID,
    user: User = Depends(require_permission("telefon_modelleri")),
    db: Session = Depends(get_db),
):
    m = db.scalar(
        select(PhoneModel).where(
            PhoneModel.id == model_id,
            PhoneModel.tenant_id == user.tenant_id,
        )
    )
    if not m:
        raise HTTPException(404, "Model bulunamadı")
    db.delete(m)
    db.commit()
    return None


@router.post("/check", response_model=dict)
def check_model(
    body: CheckRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Model tanınıyor mu? Kaynağı söyler ama BASELINE ölçüsünü vermez."""
    source = pm.resolve_source(db, user.tenant_id, body.model)
    res = {
        "model": body.model,
        "normalized_key": pm.normalize_key(body.model),
        "recognized": source is not None,
        "source": source,  # 'db' | 'baseline' | None
    }
    # Sadece DB kaynaklıysa ölçü göster (tenant'ın kendi verisi)
    if source == "db":
        spec = pm.get_spec(db, user.tenant_id, body.model)
        if spec:
            res["width_cm"], res["height_cm"], res["radius_cm"] = spec
    return res
