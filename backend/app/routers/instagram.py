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
from app.config import get_settings
from app.database import get_db
from app.models import Design, InstagramPost, Store, User
from app.services import storage, instagram_content
from app.services import mockup as mockup_svc
from app.services.storage import STORAGE_ROOT

logger = __import__("logging").getLogger("instagram")


def _load_design_art(design: Design):
    """Tasarımdan PIL görüntü yükle (png/jpg/jpeg doğrudan, _thumb.png varsa, PDF ->
    ilk sayfa fitz ile). Bulunamazsa None."""
    from PIL import Image
    fp = design.file_path
    if not fp:
        return None
    fmt = (design.file_format or "").lower()

    # 1) Doğrudan png/jpg + varsa hazır thumbnail
    candidates = []
    if fmt in ("png", "jpg", "jpeg"):
        candidates.append(fp)
    if len(fp) > 4:
        candidates.append(fp[:-4] + "_thumb.png")
    for rel in candidates:
        full = STORAGE_ROOT / rel
        if full.exists():
            try:
                return Image.open(full).convert("RGBA")
            except Exception:  # noqa: BLE001
                pass

    # 2) PDF -> ilk sayfayı render et (PyMuPDF)
    if fmt == "pdf":
        full = STORAGE_ROOT / fp
        if full.exists():
            try:
                import fitz
                doc = fitz.open(str(full))
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=True)
                mode = "RGBA" if pix.alpha else "RGB"
                return Image.frombytes(mode, [pix.width, pix.height], pix.samples).convert("RGBA")
            except Exception:  # noqa: BLE001
                pass
    return None


def _render_post_image(tenant_id, store: Store, design: Design) -> str | None:
    """Tasarımdan Instagram için kılıf mockup'ı üret, JPG kaydet, relative path döndür.
    Mağazanın mockup PSD'si varsa onunla (Ürün Stüdyosu ile aynı), yoksa basit render.
    Başarısızsa None (o zaman _ser thumbnail'e düşer)."""
    try:
        art = _load_design_art(design)
        if art is None:
            return None

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


from fastapi import UploadFile, File, Form


@router.post("/upload", response_model=dict)
async def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Sohbete / gönderiye görsel yükle (UGC örnek görseli, referans vb.).
    Döner: {path, url}."""
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "Dosya çok büyük (max 15 MB)")
    ext = (file.filename or "img.jpg").rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    rel = f"tenants/{user.tenant_id}/instagram/uploads/{uuid.uuid4().hex}.{ext}"
    full = STORAGE_ROOT / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return {"path": rel, "url": f"/storage/{rel}"}


class ChatMsg(BaseModel):
    role: str                      # user | assistant
    text: str = ""
    images: list[str] = []         # storage relative path'leri


class ChatIn(BaseModel):
    store_id: uuid.UUID
    messages: list[ChatMsg]


def _learning(store: Store) -> dict:
    cfg = store.config if isinstance(store.config, dict) else {}
    ig = cfg.get("instagram") if isinstance(cfg.get("instagram"), dict) else {}
    lr = ig.get("learning") if isinstance(ig.get("learning"), dict) else {}
    return {"good": lr.get("good") or [], "bad": lr.get("bad") or []}


def _persona(store: Store) -> str:
    cfg = store.config if isinstance(store.config, dict) else {}
    ig = cfg.get("instagram") if isinstance(cfg.get("instagram"), dict) else {}
    return (ig.get("persona") or "").strip()


class PersonaIn(BaseModel):
    store_id: uuid.UUID
    persona: str


def _ref_image_path(store: Store) -> str | None:
    cfg = store.config if isinstance(store.config, dict) else {}
    ig = cfg.get("instagram") if isinstance(cfg.get("instagram"), dict) else {}
    return (ig.get("reference_image") or "").strip() or None


@router.get("/persona", response_model=dict)
def get_persona(store_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = db.scalar(select(Store).where(Store.id == store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    ref = _ref_image_path(store)
    return {"persona": _persona(store), "reference_image_url": f"/storage/{ref}" if ref else None}


class RefIn(BaseModel):
    store_id: uuid.UUID
    image_path: str | None = None   # /upload'dan gelen relative path; None -> temizle


@router.patch("/reference", response_model=dict)
def set_reference(body: RefIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Karakterin BİREBİR yüzü için referans fotoğraf ayarla (PuLID). None -> kaldır."""
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    cfg = dict(store.config or {})
    ig = dict(cfg.get("instagram") or {})
    ig["reference_image"] = (body.image_path or "").strip() or None
    cfg["instagram"] = ig
    store.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(store, "config")
    db.commit()
    ref = ig["reference_image"]
    return {"ok": True, "reference_image_url": f"/storage/{ref}" if ref else None}


@router.patch("/persona", response_model=dict)
def set_persona(body: PersonaIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    cfg = dict(store.config or {})
    ig = dict(cfg.get("instagram") or {})
    ig["persona"] = (body.persona or "").strip()[:8000]
    cfg["instagram"] = ig
    store.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(store, "config")
    db.commit()
    return {"ok": True, "has_persona": bool(ig["persona"])}


def _save_learning(db, store: Store, rating: str, caption: str):
    cfg = dict(store.config or {})
    ig = dict(cfg.get("instagram") or {})
    lr = dict(ig.get("learning") or {})
    key = "good" if rating == "iyi" else "bad"
    arr = list(lr.get(key) or [])
    cap = (caption or "").strip()[:400]
    if cap and cap not in arr:
        arr.insert(0, cap)
    lr[key] = arr[:12]
    ig["learning"] = lr
    cfg["instagram"] = ig
    store.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(store, "config")
    db.commit()


@router.post("/chat", response_model=dict)
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Agentik AI editör: kullanıcıyla sohbet eder, gerektiğinde GERÇEK bir gönderi
    önerisi (caption + tasarım mockup görseli) ÜRETİR (tool-use). Tasarım kataloğunu
    ve öğrenilen iyi/kötü örnekleri bilir. Döner: {reply, proposal?}."""
    s = get_settings()
    if not s.anthropic_api_key:
        raise HTTPException(400, "AI kapalı — .env ANTHROPIC_API_KEY tanımlı değil")
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")

    import base64
    try:
        # Tasarım kataloğu (AI görsel için kod seçsin)
        designs = db.scalars(select(Design).where(
            Design.store_id == store.id, Design.tenant_id == user.tenant_id).order_by(Design.code).limit(80)).all()
        by_code = {(d.code or "").upper(): d for d in designs if d.code}
        katalog = "\n".join(f"- {d.code}: {d.name or ''}".strip() for d in designs[:80]) or "(katalog boş)"
        lr = _learning(store)

        import anthropic
        from app.services.ai_reply import MODEL_MAP
        client = anthropic.Anthropic(api_key=s.anthropic_api_key)

        persona = _persona(store)
        if persona:
            # Marka sahibinin tanımladığı KALICI karakter (örn. "Lara") = asistanın kimliği
            system = (
                persona
                + "\n\n[SİSTEM — bu senin kalıcı kimliğin; her yanıtta bu karakter olarak davran]\n"
                "Bu markanın Instagram'ını yönetiyorsun. Marka sahibiyle sohbet et; uygun olduğunda "
                "PROAKTİF olarak somut gönderi öner. Somut bir gönderi hazırlarken `onerilecek_gonderi` "
                "aracını çağır:\n"
                "- caption: SENİN sesinle (post ise açıklama, story ise tek kısa cümle)\n"
                "- hashtags: 8-15 alakalı hashtag\n"
                "- image_prompt: sahneyi üreten İNGİLİZCE Flux/SD promptu. Karakterinin fiziksel "
                "özelliklerini HER promptta AYNI şekilde ekle (tutarlı yüz/stil). Foto stili: "
                "'shot on 35mm film, analog photography style, aesthetic, highly detailed'. Marka/ürün "
                "kurallarına (ör. yalnızca iPhone) İSTİSNASIZ uy.\n"
                "- design_code (ops.): bir ürün/kılıf gösterilecekse katalogdan kod\n"
                "Ürün kataloğu:\n" + katalog + "\n"
            )
        else:
            system = (
                f"Sen {store.name} markasının CANLI Instagram sosyal medya asistanısın — telefon "
                "kılıfı satıyoruz. PROAKTİF davran: uygun olduğunda somut gönderi önerisi üret. "
                "Ton: enerjik, samimi, kısa. Caption sonunda 8-15 hashtag.\n"
                "Somut öneri için `onerilecek_gonderi` aracını çağır (caption + hashtags + "
                "design_code ya da image_prompt). Görsel: design_code verirsen kılıf mockup'ı; "
                "image_prompt (İngilizce sahne) verirsen AI görsel üretilir.\n"
                "Ürün kataloğu:\n" + katalog + "\n"
            )
        if lr["good"]:
            system += "\nBEĞENİLEN örnekler (bu tonu yakala):\n" + "\n".join(f"- {c}" for c in lr["good"][:6])
        if lr["bad"]:
            system += "\nBEĞENİLMEYEN örnekler (bunlardan KAÇIN):\n" + "\n".join(f"- {c}" for c in lr["bad"][:6])

        cmsgs = []
        for m in body.messages[-20:]:
            content = []
            for rel in (m.images or [])[:4]:
                full = STORAGE_ROOT / rel
                if not full.exists():
                    continue
                mt = "image/png" if str(rel).lower().endswith("png") else "image/jpeg"
                b64 = base64.standard_b64encode(full.read_bytes()).decode()
                content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}})
            if m.text:
                content.append({"type": "text", "text": m.text})
            if content:
                cmsgs.append({"role": "assistant" if m.role == "assistant" else "user", "content": content})
        if not cmsgs:
            raise HTTPException(400, "Boş mesaj")

        tools = [{
            "name": "onerilecek_gonderi",
            "description": "Somut bir Instagram gönderi önerisi üret (caption + görsel).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "caption": {"type": "string", "description": "Gönderi metni (senin sesinle)"},
                    "hashtags": {"type": "string", "description": "8-15 hashtag, boşlukla ayrık"},
                    "image_prompt": {"type": "string", "description": "İNGİLİZCE sahne promptu (AI görsel üretimi için; karakterin sabit fiziksel özellikleri + film stili)"},
                    "design_code": {"type": "string", "description": "Ürün gösterilecekse katalogdan tasarım kodu (kılıf mockup'ı)"},
                },
                "required": ["caption"],
            },
        }]

        # Model: tenant AI modeli varsa onu kullan, yoksa sonnet (opus bazı hesaplarda kapalı olabilir)
        _mk = getattr(store, "ai_reply_model", None) or "sonnet"
        _model = MODEL_MAP.get(_mk) or MODEL_MAP.get("sonnet", "claude-sonnet-4-6")
        try:
            resp = client.messages.create(
                model=_model, max_tokens=1200, temperature=0.85,
                system=system, messages=cmsgs, tools=tools,
            )
        except Exception as _te:  # noqa: BLE001
            # tool-use ya da model sorunuysa tool'suz yeniden dene (en azından sohbet çalışsın)
            logger.warning(f"[instagram] tool'lu çağrı başarısız, tool'suz deneniyor: {type(_te).__name__}: {_te}")
            resp = client.messages.create(
                model=_model, max_tokens=1200, temperature=0.85,
                system=system, messages=cmsgs,
            )
        reply = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
        proposal = None
        for b in resp.content:
            if getattr(b, "type", None) == "tool_use" and getattr(b, "name", "") == "onerilecek_gonderi":
                inp = b.input or {}
                image_prompt = (inp.get("image_prompt") or "").strip()
                d = by_code.get(str(inp.get("design_code") or "").upper())
                rel = None
                img_reason = None
                # 1) Persona sahnesi: image_prompt varsa fal.ai ile ÜRET (tutarlı karakter).
                #    Referans yüz fotoğrafı varsa BİREBİR aynı yüz (PuLID).
                if image_prompt:
                    from app.services import outpaint
                    ref_bytes = None
                    _refp = _ref_image_path(store)
                    if _refp and (STORAGE_ROOT / _refp).exists():
                        try:
                            ref_bytes = (STORAGE_ROOT / _refp).read_bytes()
                        except Exception:  # noqa: BLE001
                            ref_bytes = None
                    raw, img_reason = outpaint.text_to_image(image_prompt, ref_image=ref_bytes)
                    if raw:
                        rel = f"tenants/{user.tenant_id}/instagram/{uuid.uuid4().hex}.jpg"
                        (STORAGE_ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
                        (STORAGE_ROOT / rel).write_bytes(raw)
                # 2) Yoksa ürün mockup'ı
                if not rel and d:
                    rel = _render_post_image(user.tenant_id, store, d)
                proposal = {
                    "caption": inp.get("caption") or "",
                    "hashtags": inp.get("hashtags") or "",
                    "image_prompt": image_prompt or None,
                    "image_reason": img_reason if (image_prompt and not rel) else None,
                    "design_id": str(d.id) if d else None,
                    "design_code": d.code if d else None,
                    "image_path": rel,
                    "image_url": f"/storage/{rel}" if rel else None,
                }
                break
        if not reply and proposal:
            reply = "İşte bir öneri hazırladım 👇"
        return {"reply": reply.strip() or "…", "proposal": proposal}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        import traceback
        logger.warning(f"[instagram] chat hata: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise HTTPException(502, f"AI yanıtı alınamadı: {type(e).__name__}: {str(e)[:200]}")


class FeedbackIn(BaseModel):
    store_id: uuid.UUID
    rating: str                 # iyi | kotu
    caption: str


@router.post("/feedback", response_model=dict)
def chat_feedback(body: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Öneriye 👍/👎 — beğenilen/beğenilmeyen örnek olarak saklanır, sonraki
    üretimlerde AI'a few-shot beslenir (zamanla markanın tonunu öğrenir)."""
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    if body.rating not in ("iyi", "kotu"):
        raise HTTPException(400, "Geçersiz")
    _save_learning(db, store, body.rating, body.caption)
    return {"ok": True}


class DraftIn(BaseModel):
    store_id: uuid.UUID
    caption: str
    hashtags: str | None = None
    image_path: str | None = None    # yüklenen görsel path'i
    design_id: uuid.UUID | None = None
    kind: str = "post"


@router.post("/draft", response_model=dict)
def create_draft(body: DraftIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sohbetten/elle bir taslak oluştur: verilen caption + görsel (yüklenen ya da
    tasarım mockup'ı) ile kuyruğa 'taslak' ekle."""
    store = db.scalar(select(Store).where(Store.id == body.store_id, Store.tenant_id == user.tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    image_path = body.image_path
    design = None
    if body.design_id:
        design = db.scalar(select(Design).where(Design.id == body.design_id, Design.tenant_id == user.tenant_id))
        if design and not image_path:
            image_path = _render_post_image(user.tenant_id, store, design)
    post = InstagramPost(
        tenant_id=user.tenant_id, store_id=store.id, kind=body.kind,
        style="ugc" if body.image_path else "mockup", status="taslak",
        caption=body.caption.strip(), hashtags=(body.hashtags or "").strip() or None,
        image_path=image_path, design_id=design.id if design else None,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _ser(post, design)


@router.delete("/posts/{post_id}", response_model=dict)
def delete_post(post_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(InstagramPost).where(
        InstagramPost.id == post_id, InstagramPost.tenant_id == user.tenant_id))
    if not p:
        raise HTTPException(404, "Gönderi bulunamadı")
    db.delete(p)
    db.commit()
    return {"ok": True}
