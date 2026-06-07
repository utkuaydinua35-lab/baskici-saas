
"""Kalıp planlama + oluşturma — /api/molds/* (15b: plan önizleme)"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from sqlalchemy import desc, func as sql_func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user

from app.database import get_db

from app.models import Design, LineItem, Mold, MoldItem, MoldStatusHistory, MoldTemplate, Order, User

from app.services import mold_planner, mold_pdf, storage

router = APIRouter(prefix="/api/molds", tags=["molds"])

@router.get("/plan", response_model=None)

def plan(

    store_id: uuid.UUID | None = Query(None),  # tum magazalar (multi-store)

    user: User = Depends(get_current_user),

    db: Session = Depends(get_db),

):

    """Bekleyen siparişlerden kalıp planını hesapla (önizleme, DB'ye yazmaz)."""

    return mold_planner.plan_molds(db, tenant_id=user.tenant_id, store_id=store_id)



def _next_kod_number(db: Session, tenant_id) -> int:
    """Tenant için sıradaki G kod numarası."""
    last = db.scalar(
        select(Mold.kod).where(Mold.tenant_id == tenant_id).order_by(desc(Mold.created_at)).limit(1)
    )
    mx = 0
    rows = db.execute(select(Mold.kod).where(Mold.tenant_id == tenant_id)).all()
    for (kod,) in rows:
        if kod and kod[1:].isdigit():
            mx = max(mx, int(kod[1:]))
    return mx + 1


@router.post("/create", response_model=None)
def create_molds(
    store_id: uuid.UUID | None = Query(None),
    skip_missing: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Planı hesapla ve kalıpları DB'ye yaz. Eksik varsa reddeder."""
    plan = mold_planner.plan_molds(db, tenant_id=user.tenant_id, store_id=store_id)
    if plan["eksik_count"] > 0 and not skip_missing:
        return {
            "success": False,
            "reason": "eksik_var",
            "message": f"{plan['eksik_count']} kalem için tasarım eksik. Önce eksikleri tamamlayın.",
            "eksik_count": plan["eksik_count"],
            "eksikler": plan["eksikler"],
        }
    if plan["mold_count"] == 0:
        return {"success": False, "reason": "bos", "message": "Oluşturulacak kalıp yok."}

    created = []
    li_ids_done: set = set()

    for m in plan["molds"]:
        kod = "-".join(m["kodlar"]) or "KALIP"
        mold = Mold(
            tenant_id=user.tenant_id, store_id=store_id,
            kod=kod, variation=m["variation"],
            kalip_kodlari=m["kodlar"], kilif_sayisi=m["count"], rows_used=m["rows_used"],
            status="olusturuldu",
        )
        db.add(mold)
        db.flush()
        for slot, it in enumerate(m["items"]):
            db.add(MoldItem(
                tenant_id=user.tenant_id, mold_id=mold.id,
                line_item_id=uuid.UUID(it["line_item_id"]),
                design_id=uuid.UUID(it["design_id"]) if it.get("design_id") else None,
                store_id=uuid.UUID(it["store_id"]) if it.get("store_id") else None,
                slot_index=slot, kalip_kodu=it["kod"],
                design_code=it.get("design_code"), model=it.get("model"),
                order_number=it.get("order_number"),
            ))
            li_ids_done.add(it["line_item_id"])
        created.append({"kod": kod, "variation": m["variation"], "count": m["count"]})

    # İlgili line item'ları kalıba eklendi işaretle
    if li_ids_done:
        db.execute(
            LineItem.__table__.update()
            .where(LineItem.id.in_([uuid.UUID(x) for x in li_ids_done]))
            .values(is_kaliba_eklendi=True)
        )

    db.commit()
    return {
        "success": True,
        "created_count": len(created),
        "molds": created,
        "total_units": plan["total_units"],
        "message": f"{len(created)} kalıp oluşturuldu ({plan['total_units']} kılıf).",
    }


@router.get("", response_model=None)
def list_molds(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(Mold).where(Mold.tenant_id == user.tenant_id)
    if store_id:
        q = q.where(Mold.store_id == store_id)
    molds = db.scalars(
        q.order_by(desc(Mold.created_at)).options(selectinload(Mold.items))
    ).all()
    design_ids = {it.design_id for mo in molds for it in mo.items if it.design_id}
    dmap = {}
    if design_ids:
        for d in db.scalars(select(Design).where(Design.id.in_(design_ids))).all():
            dmap[d.id] = d
    return {
        "items": [
            {
                "id": str(mo.id), "kod": mo.kod, "variation": mo.variation,
                "store_id": str(mo.store_id) if mo.store_id else None,
                "is_multi_store": mo.store_id is None,
                "kalip_kodlari": mo.kalip_kodlari, "kilif_sayisi": mo.kilif_sayisi,
                "rows_used": mo.rows_used, "status": mo.status,
                "created_at": mo.created_at.isoformat() if mo.created_at else None,
                "items": [
                    {
                        "slot_index": it.slot_index, "kalip_kodu": it.kalip_kodu,
                        "design_code": it.design_code, "model": it.model,
                        "order_number": it.order_number,
                        "design_id": str(it.design_id) if it.design_id else None,
                        "thumbnail_url": storage.get_thumbnail_url(dmap[it.design_id].file_path, dmap[it.design_id].file_format) if it.design_id in dmap else None,
                        "birincil_renk": dmap[it.design_id].birincil_renk if it.design_id in dmap else None,
                        "kalip_tipi": dmap[it.design_id].kalip_tipi if it.design_id in dmap else None,
                    }
                    for it in sorted(mo.items, key=lambda x: x.slot_index)
                ],
            }
            for mo in molds
        ]
    }


# ─── Kalıp aşamaları ────────────────────────────────────────
MOLD_STAGES = [
    {"no": 1, "key": "taslak", "label": "Taslak", "icon": "edit"},
    {"no": 2, "key": "hazir", "label": "Hazır", "icon": "check"},
    {"no": 3, "key": "baskiya_gonderildi", "label": "Baskıya Gönderildi", "icon": "send"},
    {"no": 4, "key": "baskida", "label": "Baskıda", "icon": "printer"},
    {"no": 5, "key": "tamamlandi", "label": "Tamamlandı", "icon": "check-circle"},
]
_STAGE_BY_NO = {x["no"]: x for x in MOLD_STAGES}


def _stage_info(no):
    return _STAGE_BY_NO.get(no, {"no": no, "key": "?", "label": "?", "icon": "circle"})


def _mold_progress(stage):
    return round((max(0, min(stage, 5)) / 5) * 100)


def _log_mold(db, mold, user, action, from_stage=None, to_stage=None, note=None):
    db.add(MoldStatusHistory(
        tenant_id=mold.tenant_id, mold_id=mold.id,
        from_stage=from_stage, to_stage=to_stage, action=action, note=note,
        created_by=user.full_name or user.email,
    ))


def _get_mold(db, mold_id, tenant_id):
    mo = db.scalar(
        select(Mold).where(Mold.id == mold_id, Mold.tenant_id == tenant_id)
        .options(selectinload(Mold.items))
    )
    if not mo:
        raise HTTPException(status_code=404, detail="Kalıp bulunamadı")
    return mo


def _serialize_mold_detail(mo, db):
    design_ids = {it.design_id for it in mo.items if it.design_id}
    dmap = {}
    if design_ids:
        for d in db.scalars(select(Design).where(Design.id.in_(design_ids))).all():
            dmap[d.id] = d
    items = []
    for it in sorted(mo.items, key=lambda x: x.slot_index):
        d = dmap.get(it.design_id)
        items.append({
            "id": str(it.id), "slot_index": it.slot_index, "kalip_kodu": it.kalip_kodu,
            "design_code": it.design_code, "model": it.model, "order_number": it.order_number,
            "is_hazir": it.is_hazir,
            "design_id": str(it.design_id) if it.design_id else None,
            "thumbnail_url": storage.get_thumbnail_url(d.file_path, d.file_format) if d else None,
            "birincil_renk": d.birincil_renk if d else None,
            "kalip_tipi": d.kalip_tipi if d else None,
        })
    hazir_count = sum(1 for it in mo.items if it.is_hazir)
    return {
        "id": str(mo.id), "kod": mo.kod, "variation": mo.variation,
        "kalip_kodlari": mo.kalip_kodlari, "kilif_sayisi": mo.kilif_sayisi,
        "rows_used": mo.rows_used, "status": mo.status,
        "current_stage": mo.current_stage, "is_hatali": mo.is_hatali,
        "current_stage_info": _stage_info(mo.current_stage),
        "progress_percent": _mold_progress(mo.current_stage),
        "hazir_count": hazir_count,
        "created_at": mo.created_at.isoformat() if mo.created_at else None,
        "updated_at": mo.updated_at.isoformat() if getattr(mo, "updated_at", None) else None,
        "items": items,
    }


@router.get("/_meta/stages", response_model=None)
def mold_stages(user: User = Depends(get_current_user)):
    return {"stages": MOLD_STAGES}


@router.get("/{mold_id}/detail", response_model=None)
def mold_detail(mold_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mo = _get_mold(db, mold_id, user.tenant_id)
    return _serialize_mold_detail(mo, db)


class MoldStageUpdate(BaseModel):
    stage: int | None = None
    is_hatali: bool | None = None
    note: str | None = None


@router.patch("/{mold_id}/stage", response_model=None)
def update_mold_stage(mold_id: uuid.UUID, payload: MoldStageUpdate,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mo = _get_mold(db, mold_id, user.tenant_id)
    _stock_result = None
    if payload.is_hatali is not None:
        mo.is_hatali = payload.is_hatali
        _log_mold(db, mo, user, action="hatali" if payload.is_hatali else "hatali_geri", note=payload.note)
    if payload.stage is not None:
        if payload.stage not in _STAGE_BY_NO:
            raise HTTPException(status_code=400, detail="Geçersiz aşama")
        old = mo.current_stage
        mo.current_stage = payload.stage
        mo.status = "tamamlandi" if payload.stage == 5 else "olusturuldu"
        _log_mold(db, mo, user, action="stage_change", from_stage=old, to_stage=payload.stage, note=payload.note)
        if payload.stage == 5 and old != 5:
            from app.services import stock as stock_svc
            _stock_result = stock_svc.deduct_for_mold(db, user.tenant_id, mo, user)
    db.commit()
    mo = _get_mold(db, mold_id, user.tenant_id)
    _detail = _serialize_mold_detail(mo, db)
    if _stock_result is not None:
        _detail["stock_deduction"] = _stock_result
    return _detail


class MoldItemPatch(BaseModel):
    is_hazir: bool


@router.patch("/{mold_id}/items/{item_id}", response_model=None)
def update_mold_item(mold_id: uuid.UUID, item_id: uuid.UUID, payload: MoldItemPatch,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    it = db.scalar(select(MoldItem).where(
        MoldItem.id == item_id, MoldItem.mold_id == mold_id, MoldItem.tenant_id == user.tenant_id))
    if not it:
        raise HTTPException(status_code=404, detail="Slot bulunamadı")
    it.is_hazir = payload.is_hazir
    db.commit()
    return {"ok": True, "id": str(it.id), "is_hazir": it.is_hazir}


@router.get("/{mold_id}/history", response_model=None)
def mold_history(mold_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_mold(db, mold_id, user.tenant_id)
    rows = db.scalars(
        select(MoldStatusHistory).where(MoldStatusHistory.mold_id == mold_id)
        .order_by(desc(MoldStatusHistory.created_at))
    ).all()
    return {"items": [
        {
            "id": str(h.id), "action": h.action, "note": h.note, "created_by": h.created_by,
            "from_stage": h.from_stage, "to_stage": h.to_stage,
            "from_label": _stage_info(h.from_stage)["label"] if h.from_stage else None,
            "to_label": _stage_info(h.to_stage)["label"] if h.to_stage else None,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        } for h in rows
    ]}


class RemoveItemRequest(BaseModel):
    action: str  # "replan" (geri planla) | "cancel" (iptal et)


@router.post("/{mold_id}/items/{item_id}/remove", response_model=None)
def remove_mold_item(mold_id: uuid.UUID, item_id: uuid.UUID, payload: RemoveItemRequest,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mo = _get_mold(db, mold_id, user.tenant_id)
    it = db.scalar(select(MoldItem).where(
        MoldItem.id == item_id, MoldItem.mold_id == mold_id, MoldItem.tenant_id == user.tenant_id))
    if not it:
        raise HTTPException(status_code=404, detail="Slot bulunamadı")

    li = db.scalar(select(LineItem).where(LineItem.id == it.line_item_id)) if it.line_item_id else None
    note = f"slot #{it.slot_index} · {it.kalip_kodu} · {it.design_code or ''}"

    if payload.action == "replan":
        # line item tekrar kalıba eklenmemiş -> sonraki planda çıkar
        if li:
            li.is_kaliba_eklendi = False
        _log_mold(db, mo, user, action="item_replan", note=note)
    elif payload.action == "cancel":
        # line item kalıba eklendi kalır ama plana dönmez (iptal)
        _log_mold(db, mo, user, action="item_cancel", note=note)
    else:
        raise HTTPException(status_code=400, detail="Geçersiz işlem")

    db.delete(it)
    # kalıp boşaldıysa kilif_sayisi güncelle
    mo.kilif_sayisi = max(0, mo.kilif_sayisi - 1)
    db.commit()
    mo = _get_mold(db, mold_id, user.tenant_id)
    return _serialize_mold_detail(mo, db)


@router.get("/{mold_id}/pdf", response_model=None)
def mold_pdf_download(mold_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Kalıp için baskıya hazır PDF üret ve indir."""
    mo = _get_mold(db, mold_id, user.tenant_id)
    # slot verisini tasarım dosya yollarıyla hazırla
    design_ids = {it.design_id for it in mo.items if it.design_id}
    dmap = {}
    if design_ids:
        for d in db.scalars(select(Design).where(Design.id.in_(design_ids))).all():
            dmap[d.id] = d
    slot_items = []
    for it in mo.items:
        d = dmap.get(it.design_id)
        slot_items.append({
            "kalip_kodu": it.kalip_kodu,
            "model": it.model,
            "design_file_path": d.file_path if d else None,
            "design_format": d.file_format if d else None,
        })
    # Tenant'ın aktif kalıp şablonu
    tpl = db.scalar(
        select(MoldTemplate).where(
            MoldTemplate.tenant_id == user.tenant_id,
            MoldTemplate.is_active == True,  # noqa: E712
        ).order_by(MoldTemplate.created_at.desc())
    )
    if not tpl or not tpl.boxes:
        raise HTTPException(
            status_code=400,
            detail="Önce Kalıp Şablonu yükleyin (Kalıp Şablonu sayfası).",
        )
    template_data = {
        "page_w_pt": tpl.page_w_pt, "page_h_pt": tpl.page_h_pt,
        "cols": tpl.cols, "rows": tpl.rows, "boxes": tpl.boxes,
    }
    pdf_bytes, report = mold_pdf.render_mold_pdf(slot_items, template=template_data)
    filename = f"kalip_{mo.kod}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Render-Placed": str(report["placed"]),
            "X-Render-Skipped": str(report["skipped_count"]),
        },
    )

# === BU BLOĞU molds.py'NİN EN SONUNA EKLE ===

@router.delete("/{mold_id}")
def delete_mold(
    mold_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kalıbı sil. İçindeki line item'ların is_kaliba_eklendi=False yapılır,
    design.kilif_sayisi düşülür, MoldItem'lar cascade ile silinir, history audit
    kaydı yazılır (history korunur — mold_id NULL'a düşer)."""
    mold = db.query(Mold).filter(
        Mold.id == mold_id, Mold.tenant_id == user.tenant_id
    ).first()
    if not mold:
        raise HTTPException(404, "Kalıp bulunamadı")

    kalip_kodu = mold.kod
    stage_at_delete = mold.current_stage
    items_count = len(mold.items)

    # her item için: line item'ı geri çevir + design.kilif_sayisi düş
    for mi in list(mold.items):
        if mi.line_item_id:
            li = db.query(LineItem).filter(LineItem.id == mi.line_item_id).first()
            if li:
                li.is_kaliba_eklendi = False

    # audit kaydı (mold_id artık nullable + SET NULL — silmeden ÖNCE log at,
    # sonra mold silinince mold_id NULL'a düşer ama log korunur)
    db.add(MoldStatusHistory(
        tenant_id=user.tenant_id,
        mold_id=mold.id,
        from_stage=stage_at_delete,
        to_stage=None,
        action="deleted",
        note=f"Kalıp '{kalip_kodu}' silindi ({items_count} slot geri planlandı)",
        created_by=user.email if hasattr(user, "email") else None,
    ))
    db.flush()

    db.delete(mold)  # cascade: MoldItem'lar silinir; history mold_id -> NULL
    db.commit()
    return {"ok": True, "deleted_mold": kalip_kodu, "released_items": items_count}

# ═════════════════════════════════════════════════════════════════════
# Paket 17/sonrası — Slot Ataması (manuel ve siparişten)
# ═════════════════════════════════════════════════════════════════════

def _extract_model_for_assign(li):
    """Line item'tan telefon modeli çıkar (gevşek heuristic)."""
    if li.device_model_override:
        return li.device_model_override
    for p in (li.properties or []):
        if isinstance(p, dict):
            name = (p.get("name") or "").lower()
            val = p.get("value")
            if val and any(k in name for k in ("model", "telefon", "phone", "cihaz")):
                return val
    if li.variant_title:
        return li.variant_title.split("/")[0].strip()
    return None


def _extract_variation_for_assign(li):
    """Line item'tan kasa varyasyonu çıkar (SİYAH/BEYAZ/ŞEFFAF/PARLAK/MAGSAFE)."""
    def normalize(val):
        v = (val or "").upper().replace("İ", "I").replace("Ş", "S")
        if "MAGSAFE" in v: return "MAGSAFE"
        if "SIYAH" in v or "BLACK" in v: return "SİYAH"
        if "BEYAZ" in v or "WHITE" in v: return "BEYAZ"
        if "SEFFAF" in v or "TRANSPARENT" in v or "CLEAR" in v: return "ŞEFFAF"
        if "PARLAK" in v or "GLOSSY" in v: return "PARLAK"
        return None

    for p in (li.properties or []):
        if isinstance(p, dict):
            name = (p.get("name") or "").lower()
            val = p.get("value")
            if val and any(k in name for k in ("renk", "color", "kasa", "tip", "kilif")):
                v = normalize(val)
                if v:
                    return v
    if li.variant_title:
        v = normalize(li.variant_title)
        if v:
            return v
    if li.birincil_renk:
        v = normalize(li.birincil_renk)
        if v:
            return v
    return None


@router.get("/{mold_id}/assignable/line-items", response_model=None)
def assignable_line_items(
    mold_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bu kalıba (variation uyumlu, kalıba eklenmemiş) atanabilir line item'lar."""
    mo = _get_mold(db, mold_id, user.tenant_id)

    rows = db.scalars(
        select(LineItem)
        .join(Order, LineItem.order_id == Order.id)
        .where(
            Order.store_id == mo.store_id,
            Order.tenant_id == user.tenant_id,
            LineItem.is_kaliba_eklendi == False,
        )
        .options(selectinload(LineItem.order), selectinload(LineItem.assigned_design))
        .order_by(desc(Order.created_at_platform))
        .limit(500)
    ).all()

    out = []
    for li in rows:
        variation = _extract_variation_for_assign(li)
        if variation and variation != mo.variation:
            continue  # uyumsuz

        design = li.assigned_design
        if not design and li.product_id:
            design = db.scalar(
                select(Design).where(
                    Design.store_id == mo.store_id,
                    Design.product_id == li.product_id,
                ).limit(1)
            )
        if not design:
            continue

        model = _extract_model_for_assign(li)
        if not model:
            continue

        out.append({
            "line_item_id": str(li.id),
            "order_id": str(li.order_id),
            "order_number": li.order.order_number if li.order else "",
            "customer_name": li.order.customer_name if li.order else None,
            "title": li.title,
            "variant_title": li.variant_title,
            "model": model,
            "design_id": str(design.id),
            "design_code": design.code,
            "quantity": li.quantity,
            "variation": variation,
        })

    return {"items": out, "total": len(out), "mold_variation": mo.variation}


@router.get("/{mold_id}/assignable/designs", response_model=None)
def assignable_designs(
    mold_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bu kalıba atanabilir tasarımlar (manuel sekme için, store'daki tüm tasarımlar)."""
    mo = _get_mold(db, mold_id, user.tenant_id)
    d_q = select(Design).where(Design.tenant_id == user.tenant_id).order_by(Design.code)
    if mo.store_id:
        d_q = d_q.where(Design.store_id == mo.store_id)
    designs = db.scalars(d_q).all()
    return {
        "items": [
            {
                "id": str(d.id),
                "code": d.code,
                "name": d.name,
                "store_id": str(d.store_id),
                "kalip_tipi": d.kalip_tipi,
                "birincil_renk": d.birincil_renk,
                "is_kisiye_ozel": d.is_kisiye_ozel,
                "thumbnail_url": storage.get_thumbnail_url(d.file_path, d.file_format) if d.file_path else None,
            }
            for d in designs
        ]
    }


@router.get("/{mold_id}/assignable/models", response_model=None)
def assignable_models(
    mold_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atanabilir telefon modelleri — case_dimensions'tan kullanıcı-dostu isimlerle."""
    from app.services._private import case_dimensions as cd

    def display_name(key):
        parts = key.replace("_", " ").split("-")
        if parts and parts[0].upper() == "APPLE":
            parts = parts[1:]
        out = []
        for p in parts:
            pl = p.lower()
            if pl == "iphone":
                out.append("iPhone")
            elif pl == "promax":
                out.append("Pro Max")
            elif pl in ("se", "fe", "5g", "4g", "lte"):
                out.append(p.upper())
            elif pl in ("plus", "ultra", "pro", "mini", "air", "lite"):
                out.append(p.capitalize())
            else:
                out.append(p.capitalize())
        return " ".join(out)

    keys = []
    if hasattr(cd, "MODEL_SPECS"):
        keys = list(cd.MODEL_SPECS.keys())

    seen = set()
    names = []
    for k in keys:
        name = display_name(k)
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    names.sort()
    return {"items": names}


class AssignSlotRequest(BaseModel):
    kalip_kodu: str
    source: str  # "order" veya "manual"
    line_item_id: uuid.UUID | None = None
    design_id: uuid.UUID | None = None
    model: str | None = None


@router.post("/{mold_id}/slots/assign", response_model=None)
def assign_slot(
    mold_id: uuid.UUID,
    body: AssignSlotRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Boş bir slota tasarım/sipariş ata. Sırada gelen slot_index'i otomatik hesaplar."""
    mo = _get_mold(db, mold_id, user.tenant_id)

    if body.kalip_kodu not in (mo.kalip_kodlari or []):
        raise HTTPException(400, f"Bu kalıpta '{body.kalip_kodu}' kalıp kodu yok")

    same_kod = [it for it in mo.items if it.kalip_kodu == body.kalip_kodu]
    if len(same_kod) >= 9:
        raise HTTPException(400, f"'{body.kalip_kodu}' satırı dolu (9/9)")
    next_slot_index = max((it.slot_index for it in same_kod), default=-1) + 1

    line_item_id = None
    design_id = None
    design_code = None
    model = None
    order_number = None
    src_label = ""

    if body.source == "order":
        if not body.line_item_id:
            raise HTTPException(400, "Sipariş seçilmedi")
        li_q = (
            select(LineItem)
            .join(Order, LineItem.order_id == Order.id)
            .where(
                LineItem.id == body.line_item_id,
                Order.tenant_id == user.tenant_id,
            )
            .options(selectinload(LineItem.order), selectinload(LineItem.assigned_design))
        )
        if mo.store_id:
            li_q = li_q.where(Order.store_id == mo.store_id)
        li = db.scalar(li_q)
        if not li:
            raise HTTPException(404, "Sipariş kalemi bulunamadı")
        if li.is_kaliba_eklendi:
            raise HTTPException(400, "Bu kalem zaten kalıba eklenmiş")

        variation = _extract_variation_for_assign(li)
        if variation and variation != mo.variation:
            raise HTTPException(400, f"Varyasyon uyumsuz: kalıp={mo.variation}, kalem={variation}")

        design = li.assigned_design
        if not design and li.product_id:
            d_q = select(Design).where(Design.product_id == li.product_id).limit(1)
            # mo.store_id varsa kalıbın store'una bağla, yoksa siparişin store'una
            target_store = mo.store_id or (li.order.store_id if li.order else None)
            if target_store:
                d_q = d_q.where(Design.store_id == target_store)
            design = db.scalar(d_q)
        if not design:
            raise HTTPException(400, "Bu kalem için tasarım bulunamadı")

        m = _extract_model_for_assign(li)
        if not m:
            raise HTTPException(400, "Bu kalem için model belirlenemedi")

        from app.services._private import case_dimensions as cd
        if not cd.has_spec(m):
            raise HTTPException(400, f"Model '{m}' tanınmadı (ölçü kayıtlı değil)")

        line_item_id = li.id
        design_id = design.id
        design_code = design.code
        model = m
        order_number = li.order.order_number if li.order else None
        src_label = f"sipariş #{order_number or '?'}"

        li.is_kaliba_eklendi = True

    elif body.source == "manual":
        if not body.design_id or not body.model:
            raise HTTPException(400, "Tasarım ve model seçilmedi")

        d_q = select(Design).where(
            Design.id == body.design_id,
            Design.tenant_id == user.tenant_id,
        )
        if mo.store_id:
            d_q = d_q.where(Design.store_id == mo.store_id)
        design = db.scalar(d_q)
        if not design:
            raise HTTPException(404, "Tasarım bulunamadı")

        from app.services._private import case_dimensions as cd
        if not cd.has_spec(body.model):
            raise HTTPException(400, f"Model '{body.model}' tanınmadı (ölçü kayıtlı değil)")

        design_id = design.id
        design_code = design.code
        model = body.model
        src_label = "manuel"

    else:
        raise HTTPException(400, f"Geçersiz source: {body.source}")

    # Slot'un store_id'sini belirle: order source → line item'ın store'u; manual → design'ın store'u
    slot_store_id = None
    if body.source == "order" and 'li' in locals() and li and li.order:
        slot_store_id = li.order.store_id
    elif body.source == "manual" and 'design' in locals() and design:
        slot_store_id = design.store_id

    new_item = MoldItem(
        tenant_id=user.tenant_id,
        mold_id=mo.id,
        line_item_id=line_item_id,
        design_id=design_id,
        store_id=slot_store_id,
        slot_index=next_slot_index,
        kalip_kodu=body.kalip_kodu,
        design_code=design_code,
        model=model,
        order_number=order_number,
        is_hazir=False,
    )
    db.add(new_item)
    mo.kilif_sayisi = (mo.kilif_sayisi or 0) + 1

    _log_mold(
        db, mo, user, "slot_assigned",
        from_stage=mo.current_stage, to_stage=mo.current_stage,
        note=f"Slot ataması: {body.kalip_kodu} · {design_code or '?'} · {model or '?'} · {src_label}",
    )

    db.commit()
    return {"ok": True, "mold_id": str(mo.id), "slot_index": next_slot_index}
