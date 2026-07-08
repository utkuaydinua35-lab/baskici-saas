"""Instagram içerik planlama + AI taslak paneli — /api/instagram/*

Akış: taslak üret (AI caption + görsel) -> panelde onayla/düzenle/reddet ->
onaylananları telefondan paylaş (görseli indir, metni kopyala). Her mağaza
(marka/profil) kendi IG hesabından paylaşır: store.config['instagram']['handle'].
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import Design, InstagramPost, Store, User
from app.services import storage, instagram_content
from app.services import mockup as mockup_svc
from app.services.storage import STORAGE_ROOT

logger = __import__("logging").getLogger("instagram")


def _render_post_image(tenant_id, store: Store, design: Design) -> str | None:
    """Tasarımdan Instagram için kılıf mockup'ı üret, JPG kaydet, relative path döndür.
    Mağazanın mockup PSD'si varsa onunla (Ürün Stüdyosu ile aynı), yoksa basit render.
    Başarısızsa None (o zaman _ser thumbnail'e düşer)."""
    try:
        from PIL import Image
        # Tasarımın görüntülenebilir hâlini bul (thumbnail ya da png/jpg dosyası)
        fmt = (design.file_format or "").lower()
        rel = None
        if fmt in ("png", "jpg", "jpeg"):
            rel = design.file_path
        else:
            turl = storage.get_thumbnail_url(design.file_path, design.file_format)
            if turl:
                rel = turl.replace("/storage/", "", 1)
        if not rel:
            return None
        src = STORAGE_ROOT / rel
        if not src.exists():
            return None
        art = Image.open(src).convert("RGBA")

        # Mockup: mağaza PSD'si varsa onunla, yoksa basit siyah kılıf
        mockup_psd = (store.config or {}).get("mockup_psd") if isinstance(store.config, dict) else None
        mock = None
        if mockup_psd and (STORAGE_ROOT / mockup_psd).exists():
            try:
                mock = mockup_svc.render_psd_mockup(str(STORAGE_ROOT / mockup_psd), art)
            except Exception:  # noqa: BLE001
                mock = None
        if mock is None:
            mock = mockup_svc.render_mockup(art, "siyah")

        out_rel = f"tenants/{tenant_id}/instagram/{uuid.uuid4().hex}.jpg"
        out_full = STORAGE_ROOT / out_rel
        out_full.parent.mkdir(parents=True, exist_ok=True)
        mock.convert("RGB").save(out_full, "JPEG", quality=90)
        return out_rel
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[instagram] mockup gorsel hata: {e}")
        return None

router = APIRouter(prefix="/api/instagram", tags=["instagram"],
    dependencies=[Depends(require_permission("pazarlama"))])


def _ig_handle(store: Store) -> str | None:
    cfg = store.config if isinstance(store.config, dict) else {}
    ig = cfg.get("instagram") if isinstance(cfg.get("instagram"), dict) else {}
    return (ig.get("handle") or "").strip() or None


def _ser(p: InstagramPost, design: Design | None = None) -> dict:
    img = None
    if p.image_path:
        img = storage.get_design_url(p.image_path) if not p.image_path.startswith("http") else p.image_path
    elif design and design.file_path:
        img = storage.get_thumbnail_url(design.file_path, design.file_format)
    return {
        "id": str(p.id),
        "store_id": str(p.store_id),
        "kind": p.kind,
        "style": p.style,
        "status": p.status,
        "caption": p.caption,
        "hashtags": p.hashtags,
        "image_url": img,
        "design_id": str(p.design_id) if p.design_id else None,
        "scheduled_for": p.scheduled_for.isoformat() if p.scheduled_for else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "posted_at": p.posted_at.isoformat() if p.posted_at else None,
    }


# ─── Mağaza / IG hesap ayarı ──────────────────────────────────
@router.get("/stores", response_model=dict)
def list_ig_stores(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Marka/profil mağazaları + IG hesapları (bayii hariç)."""
    stores = db.scalars(select(Store).where(
        Store.tenant_id == user.tenant_id, Store.platform != "bayii").order_by(Store.name)).all()
    return {"items": [
        {"id": str(s.id), "name": s.name, "instagram_handle": _ig_handle(s)}
        for s in stores
    ]}


class HandleIn(BaseModel):
    store_id: uuid.UUID
    handle: str


@router.patch("/stores/handle", response_model=dict)
def set_handle(body: HandleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    cfg = dict(store.config or {})
    ig = dict(cfg.get("instagram") or {})
    ig["handle"] = (body.handle or "").strip().lstrip("@") or None
    cfg["instagram"] = ig
    store.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(store, "config")
    db.commit()
    return {"ok": True, "handle": ig["handle"]}


# ─── Taslak kuyruğu ───────────────────────────────────────────
@router.get("/posts", response_model=dict)
def list_posts(
    store_id: uuid.UUID | None = None,
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(InstagramPost).where(InstagramPost.tenant_id == user.tenant_id)
    if store_id:
        q = q.where(InstagramPost.store_id == store_id)
    if status:
        q = q.where(InstagramPost.status == status)
    posts = db.scalars(q.order_by(desc(InstagramPost.created_at)).limit(200)).all()
    # design cache
    did = {p.design_id for p in posts if p.design_id}
    dmap = {d.id: d for d in db.scalars(select(Design).where(Design.id.in_(did)))} if did else {}
    return {"items": [_ser(p, dmap.get(p.design_id)) for p in posts]}


class GenerateIn(BaseModel):
    store_id: uuid.UUID
    design_id: uuid.UUID | None = None
    kind: str = "post"      # post | story
    style: str = "mockup"   # mockup | ugc


@router.post("/generate", response_model=dict)
def generate_draft(body: GenerateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI ile bir gönderi taslağı üret (caption + görsel) ve kuyruğa 'taslak' ekle."""
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")

    design = None
    if body.design_id:
        design = db.scalar(select(Design).where(
            Design.id == body.design_id, Design.tenant_id == user.tenant_id))
        if not design:
            raise HTTPException(404, "Tasarım bulunamadı")

    # Konu (subject) — tasarım adı + renk/kalıp tipi
    subject_parts = []
    if design:
        if design.name:
            subject_parts.append(design.name)
        if getattr(design, "birincil_renk", None):
            subject_parts.append(f"{design.birincil_renk} tonlar")
    subject = ", ".join(subject_parts) or "yeni telefon kılıfı tasarımı"
    brand = store.name or "markamız"

    # Öğrenme: bu mağazanın onaylanmış/paylaşılmış son gönderileri few-shot
    examples = [
        {"caption": p.caption}
        for p in db.scalars(select(InstagramPost).where(
            InstagramPost.store_id == store.id,
            InstagramPost.status.in_(["onaylandi", "paylasildi"]),
        ).order_by(desc(InstagramPost.created_at)).limit(5))
    ]

    gen = instagram_content.generate_caption(
        brand=brand, subject=subject, kind=body.kind, examples=examples)
    if not gen:
        raise HTTPException(400, "AI metni üretilemedi — ANTHROPIC_API_KEY tanımlı mı?")

    # Görsel: tasarımdan kılıf mockup'ı üret (JPG). UGC lifestyle = Faz 2.
    image_path = _render_post_image(user.tenant_id, store, design) if design else None

    post = InstagramPost(
        tenant_id=user.tenant_id, store_id=store.id,
        kind=body.kind, style=body.style, status="taslak",
        caption=gen["caption"], hashtags=gen.get("hashtags"),
        image_path=image_path, design_id=design.id if design else None,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _ser(post, design)


class PostPatch(BaseModel):
    caption: str | None = None
    hashtags: str | None = None
    status: str | None = None          # onaylandi | red | paylasildi | taslak
    scheduled_for: datetime | None = None


@router.patch("/posts/{post_id}", response_model=dict)
def patch_post(post_id: uuid.UUID, body: PostPatch,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(InstagramPost).where(
        InstagramPost.id == post_id, InstagramPost.tenant_id == user.tenant_id))
    if not p:
        raise HTTPException(404, "Gönderi bulunamadı")

    # Öğrenme sinyali: caption düzenlendiyse orijinali + düzenlenmişi sakla
    if body.caption is not None and body.caption != p.caption:
        fb = dict(p.feedback or {})
        fb.setdefault("orijinal_caption", p.caption)
        fb["duzenlenmis"] = True
        p.feedback = fb
        p.caption = body.caption
    if body.hashtags is not None:
        p.hashtags = body.hashtags
    if body.scheduled_for is not None:
        p.scheduled_for = body.scheduled_for
    if body.status is not None:
        if body.status not in ("taslak", "onaylandi", "red", "paylasildi"):
            raise HTTPException(400, "Geçersiz durum")
        p.status = body.status
        if body.status == "paylasildi" and not p.posted_at:
            p.posted_at = datetime.now(timezone.utc)
        # onay = beğeni sinyali (öğrenme)
        if body.status in ("onaylandi", "paylasildi"):
            fb = dict(p.feedback or {})
            fb["begeni"] = True
            p.feedback = fb
    db.commit()
    db.refresh(p)
    return _ser(p)


@router.delete("/posts/{post_id}", response_model=dict)
def delete_post(post_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(InstagramPost).where(
        InstagramPost.id == post_id, InstagramPost.tenant_id == user.tenant_id))
    if not p:
        raise HTTPException(404, "Gönderi bulunamadı")
    db.delete(p)
    db.commit()
    return {"ok": True}
