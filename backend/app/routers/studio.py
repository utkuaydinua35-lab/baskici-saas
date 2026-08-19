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


def _mockups(s: Store) -> list[dict]:
    """Yüklenen mockup dosyaları: [{id, name, path, type}]. type: standart | seffaf."""
    c = s.config or {}
    lst = c.get("mockups")
    if isinstance(lst, list) and lst:
        return [{**m, "type": m.get("type") or "standart"}
                for m in lst if isinstance(m, dict) and m.get("path")]
    # geriye uyum: eski tekli mockup
    if c.get("mockup_psd"):
        return [{"id": "legacy", "name": "Mockup", "path": c["mockup_psd"], "type": "standart"}]
    return []


def _mockup_transparent(s: Store, path: str | None) -> bool:
    for m in _mockups(s):
        if m["path"] == path:
            return m.get("type") == "seffaf"
    return False


def _cfg(s: Store) -> dict:
    c = s.config or {}
    brand = _brand(s)
    from app.config import get_settings
    _s = get_settings()
    _mks = _mockups(s)
    return {
        "store_id": str(s.id),
        "store_name": s.name,
        "brand": brand,
        "prefix": (c.get("kod_prefix") or ps.default_prefix(brand)).upper(),
        "price": c.get("studio_price"),
        "mockup_ready": bool(c.get("mockup_psd")),
        "mockups": [{"id": m["id"], "name": m.get("name") or "Mockup", "type": m.get("type") or "standart"} for m in _mks],
        "active_mockup_id": next((m["id"] for m in _mks if m["path"] == c.get("mockup_psd")), (_mks[0]["id"] if _mks else None)),
        "ai_expand": bool(c.get("ai_expand")),
        "ai_provider": c.get("ai_provider") or "auto",
        "ai_upscale": bool(c.get("ai_upscale")),
        "cmyk_k_offset": c.get("cmyk_k_offset", 5),
        # hangi outpaint sağlayıcıları anahtarlı (UI'da göster)
        "fal_ready": bool(_s.fal_key),
        "gemini_ready": bool(_s.gemini_api_key),
    }


@router.get("/config", response_model=dict)
def studio_config(store_id: uuid.UUID, user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    return _cfg(_get_store(db, store_id, user.tenant_id))


class ConfigIn(BaseModel):
    store_id: uuid.UUID
    price: str | None = None
    prefix: str | None = None
    marka_adi: str | None = None
    ai_expand: bool | None = None
    ai_provider: str | None = None
    ai_upscale: bool | None = None
    cmyk_k_offset: int | None = None


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
    if req.ai_expand is not None:
        cfg["ai_expand"] = bool(req.ai_expand)
    if req.ai_provider is not None:
        cfg["ai_provider"] = req.ai_provider if req.ai_provider in ("auto", "fal", "gemini") else "auto"
    if req.ai_upscale is not None:
        cfg["ai_upscale"] = bool(req.ai_upscale)
    if req.cmyk_k_offset is not None:
        cfg["cmyk_k_offset"] = max(-50, min(50, int(req.cmyk_k_offset)))
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
    """Mağazaya marka mockup PSD'si yükle (birden fazla olabilir; yüklenen aktif olur)."""
    import uuid as _uuid
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
    mid = _uuid.uuid4().hex[:8]
    rel = f"tenants/{user.tenant_id}/studio/{store_id}/mockup-{mid}{ext}"
    (STORAGE_ROOT / rel).write_bytes(data)
    cfg = dict(s.config or {})
    lst = list(_mockups(s))
    lst.append({"id": mid, "name": (file.filename or f"Mockup {len(lst)+1}")[:60], "path": rel})
    cfg["mockups"] = lst
    cfg["mockup_psd"] = rel  # yeni yüklenen aktif
    s.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(s, "config")
    db.commit()
    return {"ok": True, **_cfg(s)}


class MockupSelectIn(BaseModel):
    store_id: uuid.UUID
    mockup_id: str


@router.get("/mockups", response_model=dict)
def list_mockups(store_id: uuid.UUID, user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    s = _get_store(db, store_id, user.tenant_id)
    return {"mockups": [{"id": m["id"], "name": m.get("name") or "Mockup"} for m in _mockups(s)],
            "active_mockup_id": _cfg(s)["active_mockup_id"]}


@router.post("/mockups/select", response_model=dict)
def select_mockup(body: MockupSelectIn, user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    s = _get_store(db, body.store_id, user.tenant_id)
    m = next((x for x in _mockups(s) if x["id"] == body.mockup_id), None)
    if not m:
        raise HTTPException(404, "Mockup bulunamadı")
    cfg = dict(s.config or {})
    cfg["mockup_psd"] = m["path"]
    s.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(s, "config")
    db.commit()
    return {"ok": True, **_cfg(s)}


class MockupTypeIn(BaseModel):
    store_id: uuid.UUID
    mockup_id: str
    type: str   # standart | seffaf


@router.post("/mockups/type", response_model=dict)
def set_mockup_type(body: MockupTypeIn, user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    s = _get_store(db, body.store_id, user.tenant_id)
    if body.type not in ("standart", "seffaf"):
        raise HTTPException(400, "Geçersiz tür")
    lst = list(_mockups(s))
    found = False
    for m in lst:
        if m["id"] == body.mockup_id:
            m["type"] = body.type
            found = True
    if not found:
        raise HTTPException(404, "Mockup bulunamadı")
    cfg = dict(s.config or {})
    cfg["mockups"] = lst
    s.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(s, "config")
    db.commit()
    return {"ok": True, **_cfg(s)}


@router.delete("/mockups/{mockup_id}", response_model=dict)
def delete_mockup(mockup_id: str, store_id: uuid.UUID, user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    s = _get_store(db, store_id, user.tenant_id)
    lst = list(_mockups(s))
    m = next((x for x in lst if x["id"] == mockup_id), None)
    if not m:
        raise HTTPException(404, "Mockup bulunamadı")
    try:
        (STORAGE_ROOT / m["path"]).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    lst = [x for x in lst if x["id"] != mockup_id]
    cfg = dict(s.config or {})
    cfg["mockups"] = lst
    # aktif silindiyse ilk kalanı aktif yap
    if cfg.get("mockup_psd") == m["path"]:
        cfg["mockup_psd"] = lst[0]["path"] if lst else None
    s.config = cfg
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(s, "config")
    db.commit()
    return {"ok": True, **_cfg(s)}


@router.post("/mockup-test", response_model=dict)
async def mockup_test(store_id: uuid.UUID = Form(...), mockup_id: str | None = Form(None),
                      design: UploadFile | None = File(None),
                      user: User = Depends(require_permission("tasarim")), db: Session = Depends(get_db)):
    """Seçili (ya da verilen) mockup'ı bir tasarımla derler — AI harcamadan çalışıp
    çalışmadığını gösterir. design yüklenirse onu, yoksa deneme desenini kılıfa oturtur.
    Döner: {ok, image_url, info}."""
    from PIL import Image, ImageDraw
    s = _get_store(db, store_id, user.tenant_id)
    mks = _mockups(s)
    m = next((x for x in mks if x["id"] == mockup_id), None) if mockup_id else \
        next((x for x in mks if x["path"] == (s.config or {}).get("mockup_psd")), (mks[0] if mks else None))
    if not m:
        raise HTTPException(400, "Önce bir mockup yükleyin")
    psd_path = STORAGE_ROOT / m["path"]
    if not psd_path.exists():
        raise HTTPException(404, "Mockup dosyası bulunamadı")

    # Tasarım: yüklendiyse onu kullan, yoksa deneme deseni
    test = None
    if design is not None:
        try:
            _raw = await design.read()
            if _raw:
                test = Image.open(io.BytesIO(_raw)).convert("RGB")
        except Exception:  # noqa: BLE001
            test = None
    if test is None:
        tw, th = 1100, 2162
        test = Image.new("RGB", (tw, th), (240, 240, 245))
        dr = ImageDraw.Draw(test)
        cols = [(255, 90, 120), (90, 160, 255), (255, 205, 90), (120, 220, 160)]
        sq = 180
        for yy in range(0, th, sq):
            for xx in range(0, tw, sq):
                dr.rectangle([xx, yy, xx + sq, yy + sq], fill=cols[((xx // sq) + (yy // sq)) % len(cols)])
        dr.rectangle([60, th // 2 - 120, tw - 60, th // 2 + 120], fill=(0, 0, 0))
        dr.text((tw // 2 - 120, th // 2 - 40), "MOCKUP TEST", fill=(255, 255, 255))

    # PSD tanı: smart object'leri incele
    info = {"mockup_name": m.get("name"), "smart_objects": [], "patched": None}
    try:
        from psd_tools import PSDImage
        psd = PSDImage.open(str(psd_path))
        for l in psd.descendants():
            if getattr(l, "kind", None) == "smartobject":
                so = getattr(l, "smart_object", None)
                info["smart_objects"].append({"name": getattr(l, "name", ""), "file": getattr(so, "filename", "")})
    except Exception as e:  # noqa: BLE001
        info["psd_error"] = str(e)[:200]

    try:
        mock = mockup_svc.render_psd_mockup(str(psd_path), test, transparent=(m.get("type") == "seffaf"))
        cdir = _studio_dir(user.tenant_id, store_id) / "_test"
        cdir.mkdir(parents=True, exist_ok=True)
        out = cdir / f"{m['id']}.jpg"
        mock.convert("RGB").save(str(out), "JPEG", quality=88)
        rel = f"tenants/{user.tenant_id}/studio/{store_id}/_test/{m['id']}.jpg"
        return {"ok": True, "image_url": f"/storage/{rel}?t={int(__import__('time').time())}", "info": info}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Mockup derlenemedi: {str(e)[:200]}")


def _prune_dir(d: Path, max_age_sec: int = 86400) -> None:
    """Geçici klasördeki eski dosyaları temizle (CMYK aracı ara dosyaları)."""
    import time as _t
    if not d.exists():
        return
    now = _t.time()
    for p in d.iterdir():
        try:
            if p.is_file() and now - p.stat().st_mtime > max_age_sec:
                p.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass


@router.post("/cmyk-tool", response_model=dict)
async def cmyk_tool(
    store_id: uuid.UUID = Form(...),
    file: UploadFile | None = File(None),
    token: str | None = Form(None),
    offset: int | None = Form(None),
    user: User = Depends(require_permission("tasarim")),
    db: Session = Depends(get_db),
):
    """CMYK beyaz-koruma önizlemesi (öncesi/sonrası karşılaştırma).
    İlk çağrıda 'file' yollanır -> token döner; slider ile 'offset' değişince aynı
    token + yeni offset yollanır (dosya tekrar yüklenmez). Ayrıca görselin daha önce
    CMYK ayarından geçip geçmediğini bildirir (already_adjusted)."""
    import time as _t
    s = _get_store(db, store_id, user.tenant_id)
    cdir = _studio_dir(user.tenant_id, store_id) / "_cmyk"
    cdir.mkdir(parents=True, exist_ok=True)
    _prune_dir(cdir)
    default_off = int((s.config or {}).get("cmyk_k_offset", 5) or 0)
    off = default_off if offset is None else max(-50, min(50, int(offset)))
    if file is not None:
        raw = await file.read()
        if not raw:
            raise HTTPException(400, "Boş dosya")
        from app.services import storage as _st
        if len(raw) > _st.MAX_FILE_SIZE:
            raise HTTPException(
                413, f"Dosya çok büyük (max {_st.MAX_FILE_SIZE // 1024 // 1024} MB)")
        token = uuid.uuid4().hex[:12]
        (cdir / f"{token}.src").write_bytes(raw)
        (cdir / f"{token}.name").write_text((file.filename or "tasarim")[:80])
    elif token:
        srcp = cdir / f"{token}.src"
        if not srcp.exists():
            raise HTTPException(404, "Oturum bulunamadı — görseli tekrar yükleyin")
        raw = srcp.read_bytes()
    else:
        raise HTTPException(400, "Görsel gerekli")
    already = ps.is_cmyk_adjusted(raw)
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Görsel okunamadı")
    prev = img.copy()
    prev.thumbnail((1400, 1400))
    prev.save(str(cdir / f"{token}_before.png"), "PNG")
    ps.cmyk_adjust_rgb(prev, off).save(str(cdir / f"{token}_after.png"), "PNG")
    rel = f"tenants/{user.tenant_id}/studio/{store_id}/_cmyk"
    t = int(_t.time())
    return {
        "ok": True, "token": token, "offset": off, "already_adjusted": already,
        "width": img.width, "height": img.height,
        "before_url": f"/storage/{rel}/{token}_before.png?t={t}",
        "after_url": f"/storage/{rel}/{token}_after.png?t={t}",
    }


@router.post("/cmyk-apply", response_model=dict)
async def cmyk_apply(
    store_id: uuid.UUID = Form(...),
    token: str = Form(...),
    offset: int | None = Form(None),
    user: User = Depends(require_permission("tasarim")),
    db: Session = Depends(get_db),
):
    """Tam çözünürlükte baskı dosyalarını üret: CMYK PDF + işaretli PNG (indirilebilir)."""
    import time as _t
    s = _get_store(db, store_id, user.tenant_id)
    cdir = _studio_dir(user.tenant_id, store_id) / "_cmyk"
    srcp = cdir / f"{token}.src"
    if not srcp.exists():
        raise HTTPException(404, "Oturum bulunamadı — görseli tekrar yükleyin")
    raw = srcp.read_bytes()
    default_off = int((s.config or {}).get("cmyk_k_offset", 5) or 0)
    off = default_off if offset is None else max(-50, min(50, int(offset)))
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Görsel okunamadı")
    stem = "tasarim"
    np_ = cdir / f"{token}.name"
    if np_.exists():
        stem = (np_.read_text().rsplit(".", 1)[0] or "tasarim")[:60]
    (cdir / f"{token}_cmyk.pdf").write_bytes(ps.make_print_pdf(img, k_offset_pct=off))
    (cdir / f"{token}_cmyk.png").write_bytes(ps.cmyk_png_marked(img, off))
    rel = f"tenants/{user.tenant_id}/studio/{store_id}/_cmyk"
    t = int(_t.time())
    return {
        "ok": True, "offset": off, "stem": stem,
        "pdf_url": f"/storage/{rel}/{token}_cmyk.pdf?t={t}",
        "png_url": f"/storage/{rel}/{token}_cmyk.png?t={t}",
    }


def _existing_studio_codes(tenant_id, store_id) -> set:
    d = _studio_dir(tenant_id, store_id)
    if not d.exists():
        return set()
    return {p.name for p in d.iterdir() if p.is_dir()}


@router.post("/analyze", response_model=dict)
async def analyze(
    store_id: uuid.UUID = Form(...),
    files: list[UploadFile] = File(...),
    ready_mockup: bool = Form(False),   # görsel zaten mockup'a oturtulmuş -> render etme
    user: User = Depends(require_permission("tasarim")),
    db: Session = Depends(get_db),
):
    """Tasarım görsellerini işle: AI analiz + (render ya da hazır mockup) + kod + içerik.
    ready_mockup=True ise görsel zaten mockup'lı kabul edilir; PSD render/oran/upscale
    yapılmaz, görsel doğrudan mockup olarak kullanılır."""
    s = _get_store(db, store_id, user.tenant_id)
    cfg = _cfg(s)
    psd_path = None
    _mock_transparent = False
    if not ready_mockup:
        mockup_rel = (s.config or {}).get("mockup_psd")
        if not mockup_rel:
            raise HTTPException(400, "Önce bu mağazaya mockup PSD'si yükleyin")
        psd_path = STORAGE_ROOT / mockup_rel
        if not psd_path.exists():
            raise HTTPException(400, "Mockup dosyası bulunamadı, yeniden yükleyin")
        _mock_transparent = _mockup_transparent(s, mockup_rel)
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
        ai_expanded = False

        # ── HAZIR MOCKUP: görsel zaten mockup'lı; render/oran/upscale yok ──
        if ready_mockup:
            media = "image/png" if (f.filename or "").lower().endswith("png") else "image/jpeg"
            analysis = ps.analyze_design(raw, media_type=media) or {}
            content = ps.build_content(analysis, brand)
            code = ps.next_design_code(db, store_id, prefix, reserved=reserved)
            reserved.add(code)
            cdir = _studio_dir(user.tenant_id, store_id) / code
            cdir.mkdir(parents=True, exist_ok=True)
            # Şeffaflığı KORU: alfası varsa PNG (jpg şeffaf arkaplanı doldurur), yoksa JPG
            _pim = Image.open(io.BytesIO(raw))
            _has_alpha = ("A" in _pim.getbands()) or (_pim.mode == "P" and "transparency" in _pim.info)
            mext = "png" if _has_alpha else "jpg"
            if _has_alpha:
                _pim.convert("RGBA").save(str(cdir / "mockup.png"), "PNG")
                _pim.convert("RGBA").save(str(cdir / "baski.png"), "PNG")
            else:
                _pim.convert("RGB").save(str(cdir / "mockup.jpg"), "JPEG", quality=92)
                _pim.convert("RGB").save(str(cdir / "baski.jpg"), "JPEG", quality=95)
            rel = f"tenants/{user.tenant_id}/studio/{store_id}/{code}"
            results.append({
                "ok": True, "code": code, "title": content["title"],
                "body_html": content["body_html"], "tags": content["tags"],
                "design_name": content["design_name"], "analysis": analysis,
                "seo_title": content["seo_title"], "seo_description": content["seo_description"],
                "mockup_url": f"/storage/{rel}/mockup.{mext}",
                "baski_url": f"/storage/{rel}/baski.{mext}",
                "baski_pdf_url": None, "ai_expanded": False, "ready_mockup": True,
            })
            continue

        # En-boy oranı telefon kılıfına (~1:2) uygun değilse:
        # - ai_expand açıksa: alta yaslayıp üstünü AI ile genişlet (1:2)
        # - değilse / başarısızsa: KENARA AL
        if not ps.aspect_ok(img.width, img.height):
            _exp = None
            _exp_reason = None
            if (s.config or {}).get("ai_expand"):
                from app.services import outpaint
                _exp, _exp_reason = outpaint.expand_to_aspect(raw, ps.CASE_RATIO, provider=cfg.get("ai_provider") or "auto")
            if _exp:
                raw = _exp
                img = Image.open(io.BytesIO(_exp)).convert("RGB")
                ai_expanded = True
            else:
                base = f"En-boy oranı uygun değil ({img.width}×{img.height}) — telefon kılıfı ~1:2 olmalı"
                if (s.config or {}).get("ai_expand"):
                    detail = f" · AI genişletme başarısız — {_exp_reason}" if _exp_reason else " · AI genişletme başarısız"
                else:
                    detail = " — AI genişletmeyi açabilir ya da düzeltip tekrar yükleyebilirsin"
                results.append({
                    "ok": False, "skipped": True, "filename": f.filename,
                    "error": base + detail,
                })
                continue
        media = "image/png" if (f.filename or "").lower().endswith("png") else "image/jpeg"
        analysis = ps.analyze_design(raw, media_type=media) or {}
        content = ps.build_content(analysis, brand)
        code = ps.next_design_code(db, store_id, prefix, reserved=reserved)
        reserved.add(code)
        # Baskı çözünürlüğü düşükse AI upscale (analiz sonrası; mockup+baskı için)
        if (s.config or {}).get("ai_upscale") and max(img.width, img.height) < 2000:
            from app.services import outpaint
            _up = outpaint.upscale_image(raw, scale=2)
            if _up:
                try:
                    img = Image.open(io.BytesIO(_up)).convert("RGB")
                    raw = _up
                except Exception:  # noqa: BLE001
                    pass
        # Mockup render + kaydet
        cdir = _studio_dir(user.tenant_id, store_id) / code
        cdir.mkdir(parents=True, exist_ok=True)
        try:
            mock = mockup_svc.render_psd_mockup(str(psd_path), img, transparent=_mock_transparent)
            mock.convert("RGB").save(str(cdir / "mockup.jpg"), "JPEG", quality=92)
        except Exception as e:  # noqa: BLE001
            results.append({"ok": False, "filename": f.filename, "error": f"Mockup üretilemedi: {str(e)[:120]}"})
            continue
        img.save(str(cdir / "baski.jpg"), "JPEG", quality=95)
        # Üretim için CMYK PDF (mold akışı PDF bekler; JPG üretimde kullanılmaz)
        _has_pdf = False
        try:
            _koff = int((s.config or {}).get("cmyk_k_offset", 5) or 0)
            (cdir / "baski.pdf").write_bytes(ps.make_print_pdf(img, k_offset_pct=_koff))
            _has_pdf = True
        except Exception:  # noqa: BLE001
            _has_pdf = False
        rel = f"tenants/{user.tenant_id}/studio/{store_id}/{code}"
        results.append({
            "ok": True,
            "code": code,
            "title": content["title"],
            "body_html": content["body_html"],
            "tags": content["tags"],
            "design_name": content["design_name"],
            "seo_title": content["seo_title"],
            "seo_description": content["seo_description"],
            "analysis": analysis,
            "mockup_url": f"/storage/{rel}/mockup.jpg",
            "baski_url": f"/storage/{rel}/baski.jpg",
            "baski_pdf_url": f"/storage/{rel}/baski.pdf" if _has_pdf else None,
            "ai_expanded": ai_expanded,
        })
    return {"ok": True, "store_id": str(store_id), "items": results}


class PublishItem(BaseModel):
    code: str
    title: str
    body_html: str = ""
    tags: list[str] = []
    seo_title: str | None = None
    seo_description: str | None = None


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

        def _find(stem):  # uzantı bağımsız: png/jpg (şeffaf hazır mockup png olabilir)
            for e in ("png", "jpg", "jpeg"):
                p = cdir / f"{stem}.{e}"
                if p.exists():
                    return p, e
            return None, None
        mock, mext = _find("mockup")
        pdf = cdir / "baski.pdf"
        baski_img, bext = _find("baski")
        if not mock or not (pdf.exists() or baski_img):
            out.append({"code": code, "ok": False, "error": "Dosyalar bulunamadı (önce analiz)"})
            continue

        # 1) Design kaydı (üretim tasarımı = CMYK PDF varsa o, yoksa görsel). Kod çakışırsa atla.
        if pdf.exists():
            _rel = f"tenants/{user.tenant_id}/studio/{req.store_id}/{code}/baski.pdf"
            _fmt, _sz = "pdf", pdf.stat().st_size
        else:
            _rel = f"tenants/{user.tenant_id}/studio/{req.store_id}/{code}/baski.{bext}"
            _fmt, _sz = bext, baski_img.stat().st_size
        exists = db.scalar(select(Design).where(Design.store_id == s.id, Design.code == code))
        if exists:
            design = exists
        else:
            design = Design(
                tenant_id=user.tenant_id, store_id=s.id, code=code,
                name=it.title[:200], file_path=_rel, file_format=_fmt,
                file_size_bytes=_sz,
                # PDF yoksa (hazır mockup / kılıflı görsel) baskı dosyası yok -> kalıba girmesin
                baski_dosyasi_yok=(_fmt != "pdf"),
            )
            db.add(design)
            db.flush()

        # 2) Shopify ürünü (mockup görseli)
        shop = {"ok": False}
        if adapter is not None:
            import base64
            img_b64 = base64.standard_b64encode(mock.read_bytes()).decode()
            # SEO: gönderilmediyse başlıktan üret (İngilizce harf, düz metin)
            _seo = ps.seo_fields(it.title)
            _seo_t = (it.seo_title or _seo["seo_title"])
            _seo_d = (it.seo_description or _seo["seo_description"])
            shop = adapter.create_product(
                title=it.title, body_html=it.body_html or "",
                tags=it.tags or [], image_b64=img_b64, image_filename=f"{code}.{mext}",
                seo_title=_seo_t, seo_description=_seo_d,
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
