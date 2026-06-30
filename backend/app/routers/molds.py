
"""Kalıp planlama + oluşturma — /api/molds/* (15b: plan önizleme)"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from sqlalchemy import desc, func as sql_func, or_ as sa_or, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, require_any_permission

from app.database import get_db

from app.models import Design, LineItem, Mold, MoldItem, MoldStatusHistory, MoldTemplate, Order, User

from app.services import mold_planner, mold_pdf, storage, kisa_kod
from app.services import placement_rules as pr

router = APIRouter(prefix="/api/molds", tags=["molds"],
    dependencies=[Depends(require_any_permission("kalip", "tasarim"))],
)

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


@router.post("/create-empty", response_model=None)
def create_empty_mold(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bos kalip olustur. Varyasyon ve kod ilk eklenen kilif/tasarim ile belirlenir."""
    mold = Mold(
        tenant_id=user.tenant_id, store_id=store_id,
        kod="BOS", variation="", kalip_kodlari=[],
        kilif_sayisi=0, rows_used=0, status="olusturuldu",
    )
    db.add(mold)
    db.commit()
    db.refresh(mold)
    return {"success": True, "id": str(mold.id), "kod": mold.kod}


@router.post("/create", response_model=None)
def create_molds(
    store_id: uuid.UUID | None = Query(None),
    skip_missing: bool = Query(False),
    harfler: str = Query("GHJ"),
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
        kod = "-".join(kisa_kod.kisa_kodlar(m["kodlar"], harfler)) or "KALIP"
        mold = Mold(
            tenant_id=user.tenant_id, store_id=store_id,
            kod=kod, variation=m["variation"],
            kalip_kodlari=m["kodlar"], kilif_sayisi=m["count"], rows_used=m["rows_used"],
            status="olusturuldu", current_stage=2,  # hazir -> Baskici Paneli'ne duser
        )
        db.add(mold)
        db.flush()
        # Grid slot ataması (priority düşük=alt satır 1-9, yüksek=üst satır 19-27)
        placed_items = mold_planner.pr.assign_slots(list(m["items"]))
        for it in placed_items:
            db.add(MoldItem(
                tenant_id=user.tenant_id, mold_id=mold.id,
                line_item_id=uuid.UUID(it["line_item_id"]),
                design_id=uuid.UUID(it["design_id"]) if it.get("design_id") else None,
                store_id=uuid.UUID(it["store_id"]) if it.get("store_id") else None,
                slot_index=it["slot_index"], kalip_kodu=it["kod"],
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
    archived: bool | None = Query(None),  # None=hepsi, False=aktif(24s ici), True=eski(24s gecmis)
    date_from: str | None = Query(None),  # YYYY-MM-DD (eski liste tarih filtresi)
    date_to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime as _dtl, timezone as _tzl, timedelta as _tdl
    q = select(Mold).where(Mold.tenant_id == user.tenant_id)
    if store_id:
        q = q.where(Mold.store_id == store_id)
    if archived is not None:
        _esik = _dtl.now(_tzl.utc) - _tdl(hours=24)
        if archived:
            # Eski: tamamlanmis (stage 5) VE tamamlandi_at 24 saatten eski
            q = q.where(Mold.current_stage == 5, Mold.tamamlandi_at.isnot(None), Mold.tamamlandi_at < _esik)
            if date_from:
                try: q = q.where(Mold.tamamlandi_at >= _dtl.fromisoformat(date_from).replace(tzinfo=_tzl.utc))
                except Exception: pass
            if date_to:
                try: q = q.where(Mold.tamamlandi_at < (_dtl.fromisoformat(date_to).replace(tzinfo=_tzl.utc) + _tdl(days=1)))
                except Exception: pass
        else:
            # Aktif: tamamlanmamis VEYA (tamamlanmis ama 24 saat gecmemis)
            q = q.where(sa_or(Mold.current_stage != 5, Mold.tamamlandi_at.is_(None), Mold.tamamlandi_at >= _esik))
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
                "print_status": mo.print_status,
                "print_note": mo.print_note,
                "print_analysis": mo.print_analysis,
                "print_analyzed_at": mo.print_analyzed_at.isoformat() if mo.print_analyzed_at else None,
                "tamamlandi_at": mo.tamamlandi_at.isoformat() if mo.tamamlandi_at else None,
                "current_stage": mo.current_stage,
                "is_hatali": mo.is_hatali,
                "created_at": mo.created_at.isoformat() if mo.created_at else None,
                "items": [
                    {
                        "id": str(it.id), "slot_index": it.slot_index, "kalip_kodu": it.kalip_kodu, "kilif_rengi": mold_planner.pr.kod_to_renk(it.kalip_kodu),
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


def _replan_mold_item(db: Session, tenant_id, mi) -> None:
    """Kalip slot'unu plana geri dondur: kaynak line item'in is_kaliba_eklendi=False yap.
    line_item_id varsa onu; YOKSA (cogu MoldItem'da None) order_number + design_code ile esle.
    Aksi halde item kalici olarak planlamadan dislanir (uretilemez)."""
    if mi.line_item_id:
        li = db.scalar(select(LineItem).where(LineItem.id == mi.line_item_id))
        if li:
            li.is_kaliba_eklendi = False
        return
    # Fallback: line_item_id yok -> order_number + design_code ile esle
    if not (mi.order_number and mi.design_code):
        return
    cands = db.scalars(
        select(LineItem)
        .join(Order, LineItem.order_id == Order.id)
        .join(Design, LineItem.assigned_design_id == Design.id)
        .where(
            Order.tenant_id == tenant_id,
            Order.order_number == str(mi.order_number),
            Design.code == str(mi.design_code),
            LineItem.is_kaliba_eklendi == True,  # noqa: E712
        )
    ).all()
    if not cands:
        return
    # KRITIK: Ayni siparis + ayni tasarim (orn. 3 urun de SEFFAF) birden cok line item
    # dondurebilir. Bir slot = bir line item oldugu icin TUMUNU geri planlamak, ayni
    # siparisteki (zaten basilmis olabilecek) kardes urunleri yanlislikla plana dondurur
    # ve tekrar basilmalarina yol acar. Bu yuzden yalnizca bu slot'un modeline uyan TEK
    # line item'i geri planla.
    if len(cands) > 1 and mi.model:
        from app.services.phone_models import normalize_key
        _target = normalize_key(mi.model)
        _matched = [c for c in cands if normalize_key(mold_planner.extract_phone_model(c) or "") == _target]
        if _matched:
            cands = _matched
    cands[0].is_kaliba_eklendi = False


def _serialize_mold_detail(mo, db):
    design_ids = {it.design_id for it in mo.items if it.design_id}
    dmap = {}
    if design_ids:
        for d in db.scalars(select(Design).where(Design.id.in_(design_ids))).all():
            dmap[d.id] = d
    # Telafi siparis numaralarini isaretle (kalip olusturucu rozeti)
    onums = {it.order_number for it in mo.items if it.order_number}
    telafi_onums = set()
    if onums:
        telafi_onums = set(db.scalars(
            select(Order.order_number).where(
                Order.order_number.in_(onums), Order.is_telafi == True  # noqa: E712
            )
        ).all())
    items = []
    for it in sorted(mo.items, key=lambda x: x.slot_index):
        d = dmap.get(it.design_id)
        items.append({
            "id": str(it.id), "slot_index": it.slot_index, "kalip_kodu": it.kalip_kodu, "kilif_rengi": mold_planner.pr.kod_to_renk(it.kalip_kodu),
            "design_code": it.design_code, "model": it.model, "order_number": it.order_number,
            "is_hazir": it.is_hazir,
            "is_telafi": it.order_number in telafi_onums,
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


class MoldRenameIn(BaseModel):
    kod: str
    set_ready: bool = True  # isimlendirince taslaktan cikar (stage 2 hazir)


@router.patch("/{mold_id}/rename", response_model=None)
def rename_mold(mold_id: uuid.UUID, payload: MoldRenameIn,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Kalip adini (kod) guncelle. Bos kalip isimlendirilince hazir(stage2) yapilir."""
    mo = _get_mold(db, mold_id, user.tenant_id)
    yeni = (payload.kod or "").strip()
    if not yeni:
        raise HTTPException(400, "Kalip adi bos olamaz")
    eski = mo.kod
    mo.kod = yeni
    if payload.set_ready and (mo.current_stage is None or mo.current_stage < 2):
        mo.current_stage = 2  # hazir -> Baskici Paneli'ne duser
        mo.status = "olusturuldu"
    _log_mold(db, mo, user, action="rename", note=f"'{eski}' -> '{yeni}'")
    db.commit()
    mo = _get_mold(db, mold_id, user.tenant_id)
    return _serialize_mold_detail(mo, db)


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
        if payload.stage == 5:
            from datetime import datetime as _dt5, timezone as _tz5
            mo.tamamlandi_at = _dt5.now(_tz5.utc)
        elif old == 5:
            mo.tamamlandi_at = None  # tamamlanmadan geri alindi
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


@router.post("/_resync-flags", response_model=None)
def resync_kalip_flags(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Bakim: hicbir aktif kalipta OLMAYAN ama is_kaliba_eklendi=True isaretli line item'lari
    sifirla (plana geri dondur). Gecmiste line_item_id'siz MoldItem silinince takili kalanlari kurtarir."""
    tid = user.tenant_id
    # Aktif kaliplardaki line item kimlikleri (id + order_number/design_code cifti)
    mis = db.scalars(
        select(MoldItem).join(Mold, Mold.id == MoldItem.mold_id).where(Mold.tenant_id == tid)
    ).all()
    in_mold_ids = {mi.line_item_id for mi in mis if mi.line_item_id}
    in_mold_pairs = {
        (str(mi.order_number), str(mi.design_code))
        for mi in mis if not mi.line_item_id and mi.order_number and mi.design_code
    }
    # is_kaliba_eklendi=True olan tum line item'lar
    lis = db.scalars(
        select(LineItem)
        .join(Order, LineItem.order_id == Order.id)
        .where(Order.tenant_id == tid, LineItem.is_kaliba_eklendi == True)  # noqa: E712
        .options(selectinload(LineItem.order), selectinload(LineItem.assigned_design))
    ).all()
    fixed = 0
    for li in lis:
        if li.id in in_mold_ids:
            continue
        code = li.assigned_design.code if li.assigned_design else None
        onum = li.order.order_number if li.order else None
        if code and onum and (str(onum), str(code)) in in_mold_pairs:
            continue
        li.is_kaliba_eklendi = False
        fixed += 1
    db.commit()
    return {"ok": True, "fixed": fixed}


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
        # (line_item_id yoksa order_number+design_code fallback'i ile esle)
        _replan_mold_item(db, user.tenant_id, it)
        _log_mold(db, mo, user, action="item_replan", note=note)
    elif payload.action == "cancel":
        # line item kalıba eklendi kalır ama plana dönmez (iptal)
        _log_mold(db, mo, user, action="item_cancel", note=note)
    else:
        raise HTTPException(status_code=400, detail="Geçersiz işlem")

    db.delete(it)
    db.flush()
    # Kalan item'lari yeniden yerlestir (slot bosluklarini doldur, grup/priority duzenini koru)
    _kalanlar = [x for x in mo.items if x.id != it.id]
    if _kalanlar:
        _dicts = [{"kod": x.kalip_kodu, "model": x.model, "_ref": x} for x in _kalanlar]
        _yeni = mold_planner.pr.assign_slots(_dicts)
        for _d in _yeni:
            _d["_ref"].slot_index = _d["slot_index"]
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
            "slot_index": it.slot_index,
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

    # === Asama otomasyonu: PDF indirilince ===
    # 1) Onceki acik kaliplari (baskiya_gonderildi=3 veya baskida=4, bu kalip haric) tamamla
    from datetime import datetime as _dt, timezone as _tz
    _onceki = db.scalars(
        select(Mold).where(
            Mold.tenant_id == user.tenant_id,
            Mold.id != mo.id,
            Mold.current_stage.in_([3, 4]),
        )
    ).all()
    for _prev in _onceki:
        _old_stage = _prev.current_stage
        _prev.current_stage = 5  # tamamlandi
        _prev.status = "tamamlandi"
        from datetime import datetime as _dtp, timezone as _tzp
        _prev.tamamlandi_at = _dtp.now(_tzp.utc)
        _log_mold(db, _prev, user, action="stage_change", from_stage=_old_stage, to_stage=5,
                  note="Yeni kalip baskiya gonderildi (otomatik tamamlandi)")
        try:
            from app.services import stock as stock_svc
            stock_svc.deduct_for_mold(db, user.tenant_id, _prev, user)
        except Exception:
            pass
    # 2) Bu kalibi baskiya_gonderildi yap + indirme zamanini kaydet
    if mo.current_stage < 3:
        _old = mo.current_stage
        mo.current_stage = 3  # baskiya_gonderildi
        _log_mold(db, mo, user, action="stage_change", from_stage=_old, to_stage=3,
                  note="PDF indirildi")
    mo.pdf_indirilme_zamani = _dt.now(_tz.utc)
    db.commit()

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

    kalip_kodu, items_count = _delete_mold_inner(db, mold, user)
    db.commit()
    return {"ok": True, "deleted_mold": kalip_kodu, "released_items": items_count}


def _delete_mold_inner(db: Session, mold, user) -> tuple[str, int]:
    """Kalip silme cekirdek mantigi (commit yapMAZ). delete_mold + toplu silme paylasir."""
    kalip_kodu = mold.kod
    stage_at_delete = mold.current_stage
    items_count = len(mold.items)
    for mi in list(mold.items):
        _replan_mold_item(db, user.tenant_id, mi)
    db.add(MoldStatusHistory(
        tenant_id=user.tenant_id, mold_id=mold.id,
        from_stage=stage_at_delete, to_stage=None, action="deleted",
        note=f"Kalip '{kalip_kodu}' silindi ({items_count} slot geri planlandi)",
        created_by=user.email if hasattr(user, "email") else None,
    ))
    db.flush()
    db.delete(mold)
    db.flush()
    return kalip_kodu, items_count


class BulkDeleteIn(BaseModel):
    ids: list[uuid.UUID] | None = None
    only_printed: bool = False


@router.post("/print/bulk-delete")
def bulk_delete_molds(
    body: BulkDeleteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toplu kalip sil. ids verilirse o kaliplari; only_printed=True ise
    print_status='basildi' olan TUM kaliplari siler."""
    q = select(Mold).where(Mold.tenant_id == user.tenant_id)
    if body.only_printed:
        q = q.where(Mold.print_status == "basildi")
    elif body.ids:
        q = q.where(Mold.id.in_(body.ids))
    else:
        raise HTTPException(400, "ids veya only_printed gerekli")
    molds = db.scalars(q.options(selectinload(Mold.items))).all()
    deleted = []
    for mo in molds:
        kod, _ = _delete_mold_inner(db, mo, user)
        deleted.append(kod)
    db.commit()
    return {"ok": True, "deleted_count": len(deleted), "deleted": deleted}

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

    _conds = [Order.tenant_id == user.tenant_id, LineItem.is_kaliba_eklendi == False]
    if mo.store_id:
        _conds.append(Order.store_id == mo.store_id)
    rows = db.scalars(
        select(LineItem)
        .join(Order, LineItem.order_id == Order.id)
        .where(*_conds)
        .options(selectinload(LineItem.order), selectinload(LineItem.assigned_design))
        .order_by(desc(Order.created_at_platform))
        .limit(500)
    ).all()

    out = []
    for li in rows:
        variation = _extract_variation_for_assign(li)
        if mo.variation and variation and variation != mo.variation:
            continue  # uyumsuz (bos kalipta mo.variation bos -> filtreleme yok)

        design = li.assigned_design
        if not design and li.product_id:
            _dq = select(Design).where(Design.product_id == li.product_id)
            if mo.store_id:
                _dq = _dq.where(Design.store_id == mo.store_id)
            design = db.scalar(_dq.limit(1))
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
    if hasattr(cd, "_MODEL_SPECS"):
        keys = list(cd._MODEL_SPECS.keys())

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
    kalip_kodu: str | None = None  # bos kalipta None — backend modelden hesaplar
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

    # Bos kalip mi? (henuz hic kilif yok) -> ilk eklenen kilif/tasarim duzeni belirler
    _is_empty_mold = not (mo.kalip_kodlari or []) and len(mo.items) == 0
    # kalip_kodu kontrolu: dolu kalipta var olmali; bos kalipta sonra hesaplanacak
    if not _is_empty_mold and body.kalip_kodu and body.kalip_kodu not in (mo.kalip_kodlari or []):
        # Kod kalipta yok ama varyasyon uyumlu olabilir -> ekle (asagida varyasyon kontrolu yapilir)
        pass

    # Bos kalipta kalip_kodu None — slot hesabi asagida (kod hesaplandiktan sonra) yapilir
    next_slot_index = 0
    if body.kalip_kodu:
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
        # Varyasyon uyum kontrolu asagida ortak blokta (bos kalip destegi)

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

    # === Bos kalip + ilk-ekleme + varyasyon uyum kontrolu ===
    # Eklenen kilifin gercek kalip kodunu modelinden hesapla
    if body.source == "order":
        _var = _extract_variation_for_assign(li) or "SİYAH"
    else:
        _var = pr.normalize_variation(getattr(design, "kalip_tipi", None)) or "SİYAH"
    _hesap_kod = pr.resolve_kalip_kodu(model, _var)
    if not _hesap_kod:
        raise HTTPException(400, f"Model '{model}' icin kalip kodu hesaplanamadi")

    if _is_empty_mold:
        # Ilk ekleme: kalibin varyasyonunu ve ilk kodunu belirle
        mo.variation = pr.kod_to_renk(_hesap_kod, _var)
        mo.kalip_kodlari = [_hesap_kod]
        body.kalip_kodu = _hesap_kod
    else:
        # Dolu kalip: varyasyon/kod uyumlu olmali
        _kalip_renk = (mo.variation or "").upper()
        _yeni_renk = pr.kod_to_renk(_hesap_kod, _var).upper()
        if _kalip_renk and _yeni_renk and _kalip_renk != _yeni_renk:
            raise HTTPException(400, f"Varyasyon uyumsuz: kalip={mo.variation}, eklenen={_yeni_renk}")
        # Ozel varyasyonlar (SEFFAF/PARLAK/MAGSAFE) tek kalip — farkli ozel tip karismasin
        _ozel = {"SEFFAF", "PARLAK", "MAGSAFE"}
        _mevcut_ozel = {pr._kod_group(k) for k in (mo.kalip_kodlari or [])} & _ozel if hasattr(pr, "_kod_group") else set()
        # Kod kalipta yoksa ekle
        if _hesap_kod not in (mo.kalip_kodlari or []):
            mo.kalip_kodlari = list(mo.kalip_kodlari or []) + [_hesap_kod]
        body.kalip_kodu = _hesap_kod

    # body.kalip_kodu artik hesaplanan kod -> same_kod/next_slot_index'i yeniden hesapla
    _same = [it for it in mo.items if it.kalip_kodu == body.kalip_kodu]
    if len(_same) >= 9:
        raise HTTPException(400, f"'{body.kalip_kodu}' satiri dolu (9/9)")
    next_slot_index = max((it.slot_index for it in _same), default=-1) + 1

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


# ─── Baskici Paneli: analiz + durum ──────────────────────────
from datetime import datetime as _dt, UTC as _UTC

_PRINT_STATUSES = {"bekliyor", "basildi", "eksik_var", "hatali_basildi"}


@router.get("/print/total-missing")
def total_missing(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tum (basilmamis) kaliplarin stok eksiklerini model bazinda topla."""
    from app.services import stock as stock_svc
    from collections import defaultdict

    molds = db.scalars(
        select(Mold).where(Mold.tenant_id == user.tenant_id).options(selectinload(Mold.items))
    ).all()

    agg = defaultdict(lambda: {"total_missing": 0, "mold_count": 0, "not_in_system": False})
    mold_set = defaultdict(set)
    for mo in molds:
        if mo.print_status == "basildi":
            continue
        res = stock_svc.analyze_mold_stock(db, user.tenant_id, mo)
        for ms in res["missing_stock"]:
            key = (ms["variation"], ms["model"])
            agg[key]["total_missing"] += ms["missing"]
            if ms.get("not_in_system"):
                agg[key]["not_in_system"] = True
            mold_set[key].add(str(mo.id))

    items = []
    for (var, model), v in agg.items():
        items.append({
            "variation": var, "model": model,
            "total_missing": v["total_missing"],
            "mold_count": len(mold_set[(var, model)]),
            "not_in_system": v["not_in_system"],
        })
    items.sort(key=lambda x: (-x["total_missing"], x["model"] or ""))
    return {"items": items, "total_models": len(items), "total_missing": sum(i["total_missing"] for i in items)}


@router.get("/print/required-models")
def required_models(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stok bakmadan: panel (üretim) kalıplarında gereken telefon modelleri + adet.
    Basılmış kalıplar ve panel dışı (taslak/teslim) aşamalar hariç."""
    from collections import defaultdict

    molds = db.scalars(
        select(Mold).where(Mold.tenant_id == user.tenant_id).options(selectinload(Mold.items))
    ).all()

    agg: dict = defaultdict(lambda: {"count": 0, "molds": set()})
    for mo in molds:
        if mo.print_status == "basildi":
            continue
        st = mo.current_stage
        # Baskıcı panelindeki ile aynı aralık: taslak(1) ve teslim(>=5) hariç
        if not (st is None or (1 < st < 5)):
            continue
        for it in mo.items:
            model = (it.model or "").strip() or "(model belirtilmemiş)"
            var = mold_planner.pr.kod_to_renk(it.kalip_kodu) or (mo.variation or "")
            key = (var, model)
            agg[key]["count"] += 1
            agg[key]["molds"].add(str(mo.id))

    items = [
        {"variation": var, "model": model, "count": v["count"], "mold_count": len(v["molds"])}
        for (var, model), v in agg.items()
    ]
    items.sort(key=lambda x: (-x["count"], x["model"] or ""))
    return {"items": items, "total_models": len(items), "total_count": sum(i["count"] for i in items)}


@router.get("/{mold_id}/analyze")
def analyze_mold(
    mold_id: uuid.UUID,
    force: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kalibi stok acisindan analiz et (dusmeden). Sonucu cache'ler.
    Stok yetersizse print_status'u otomatik 'eksik_var' yapar;
    yeterliyse ve mevcut durum 'eksik_var' ise 'bekliyor'a geri alir."""
    from app.services import stock as stock_svc

    mold = db.scalar(select(Mold).where(Mold.id == mold_id, Mold.tenant_id == user.tenant_id))
    if not mold:
        raise HTTPException(404, "Kalip bulunamadi")

    if not force and mold.print_analysis:
        return mold.print_analysis

    result = stock_svc.analyze_mold_stock(db, user.tenant_id, mold)
    mold.print_analysis = result
    mold.print_analyzed_at = _dt.now(_UTC)

    # Otomatik durum: basilmamis kaliplar icin stok durumuna gore
    if mold.print_status in ("bekliyor", "eksik_var"):
        mold.print_status = "eksik_var" if result["has_stock_issues"] else "bekliyor"

    db.commit()
    return result


class PrintStatusIn(BaseModel):
    status: str | None = None
    note: str | None = None


@router.patch("/{mold_id}/print-status")
def set_print_status(
    mold_id: uuid.UUID,
    body: PrintStatusIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kalibin baski durumunu / notunu guncelle."""
    mold = db.scalar(select(Mold).where(Mold.id == mold_id, Mold.tenant_id == user.tenant_id))
    if not mold:
        raise HTTPException(404, "Kalip bulunamadi")

    if body.status is not None:
        if body.status not in _PRINT_STATUSES:
            raise HTTPException(400, f"Gecersiz durum. Izinli: {', '.join(sorted(_PRINT_STATUSES))}")
        mold.print_status = body.status
    if body.note is not None:
        mold.print_note = body.note.strip() or None

    db.commit()
    return {
        "ok": True,
        "id": str(mold.id),
        "print_status": mold.print_status,
        "print_note": mold.print_note,
    }
