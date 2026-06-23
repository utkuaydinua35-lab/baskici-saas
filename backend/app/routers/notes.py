"""Siparis notlari API — /api/notes (Apple Notes tarzi).

Her magaza + her bayii icin 2 not: acik + gonderilmis siparisler.
auto_content otomatik uretilir (note_builder), manual_content elle korunur.
Serbest notlar: is_serbest=True, store_id=None.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Note, Store, Dealer, User
from app.services import note_builder

router = APIRouter(prefix="/api/notes", tags=["notes"])


def _ser(n: Note, detay: bool = False) -> dict:
    d = {
        "id": str(n.id),
        "store_id": str(n.store_id) if n.store_id else None,
        "dealer_id": str(n.dealer_id) if n.dealer_id else None,
        "note_type": n.note_type,
        "baslik": n.baslik,
        "is_serbest": n.is_serbest,
        "pinned": n.pinned,
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    }
    if detay:
        d["auto_content"] = n.auto_content or {}
        d["manual_content"] = n.manual_content
        d["auto_text"] = note_builder.render_note_text(n.auto_content or {})
    else:
        # ozet: siparis sayisi
        ac = n.auto_content or {}
        d["siparis_sayisi"] = ac.get("siparis_sayisi", 0)
    return d


@router.get("", response_model=None)
def list_notes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tum notlari listele (pinned once, sonra guncelleme tarihi)."""
    notes = db.scalars(
        select(Note).where(Note.tenant_id == user.tenant_id)
        .order_by(Note.pinned.desc(), Note.updated_at.desc())
    ).all()
    return {"items": [_ser(n) for n in notes]}


@router.get("/{note_id}", response_model=None)
def get_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.scalar(select(Note).where(Note.id == note_id, Note.tenant_id == user.tenant_id))
    if not n:
        raise HTTPException(status_code=404, detail="Not bulunamadi")
    return _ser(n, detay=True)


@router.post("/refresh", response_model=None)
def refresh_notes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tum magaza + bayiiler icin acik/gonderilmis notlarini siparislerden yeniden uret.
    manual_content korunur, sadece auto_content guncellenir."""
    tid = user.tenant_id
    olusturulan = 0
    guncellenen = 0

    def upsert(store_id, dealer_id, note_type, baslik, gonderilmis):
        nonlocal olusturulan, guncellenen
        content = note_builder.build_note_content(
            db, tid, store_id=store_id, dealer_id=dealer_id, gonderilmis=gonderilmis
        )
        q = select(Note).where(Note.tenant_id == tid, Note.note_type == note_type, Note.is_serbest == False)  # noqa: E712
        if store_id:
            q = q.where(Note.store_id == store_id)
        else:
            q = q.where(Note.store_id.is_(None))
        if dealer_id:
            q = q.where(Note.dealer_id == dealer_id)
        else:
            q = q.where(Note.dealer_id.is_(None))
        existing = db.scalar(q)
        if existing:
            existing.auto_content = content
            existing.baslik = baslik
            guncellenen += 1
        else:
            db.add(Note(
                tenant_id=tid, store_id=store_id, dealer_id=dealer_id,
                note_type=note_type, baslik=baslik, auto_content=content, is_serbest=False,
            ))
            olusturulan += 1

    # Ana magazalar (platform != bayii)
    stores = db.scalars(select(Store).where(Store.tenant_id == tid)).all()
    for s in stores:
        if getattr(s, "platform", None) == "bayii":
            continue
        upsert(s.id, None, "acik", f"{s.name} — Acik Siparisler", False)
        upsert(s.id, None, "gonderilmis", f"{s.name} — Gonderilmis Siparisler", True)

    # Bayiiler
    dealers = db.scalars(select(Dealer).where(Dealer.tenant_id == tid)).all()
    for de in dealers:
        upsert(None, de.id, "acik", f"{de.name} (Bayii) — Acik Siparisler", False)
        upsert(None, de.id, "gonderilmis", f"{de.name} (Bayii) — Gonderilmis Siparisler", True)

    db.commit()
    return {"ok": True, "olusturulan": olusturulan, "guncellenen": guncellenen}


class NoteManualIn(BaseModel):
    manual_content: str | None = None
    pinned: bool | None = None


@router.patch("/{note_id}", response_model=None)
def update_note(
    note_id: uuid.UUID,
    body: NoteManualIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Elle duzenle: manual_content ve/veya pinned. auto_content'e dokunmaz."""
    n = db.scalar(select(Note).where(Note.id == note_id, Note.tenant_id == user.tenant_id))
    if not n:
        raise HTTPException(status_code=404, detail="Not bulunamadi")
    if body.manual_content is not None:
        n.manual_content = body.manual_content
    if body.pinned is not None:
        n.pinned = body.pinned
    db.commit()
    return _ser(n, detay=True)


class SerbestNoteIn(BaseModel):
    baslik: str
    manual_content: str | None = None


@router.post("", response_model=None)
def create_serbest_note(
    body: SerbestNoteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serbest (elle) not olustur."""
    n = Note(
        tenant_id=user.tenant_id, store_id=None, dealer_id=None,
        note_type="serbest", baslik=body.baslik.strip() or "Yeni Not",
        manual_content=body.manual_content, is_serbest=True,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return _ser(n, detay=True)


@router.delete("/{note_id}", status_code=204)
def delete_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sadece serbest notlar silinebilir (otomatik notlar refresh ile yonetilir)."""
    n = db.scalar(select(Note).where(Note.id == note_id, Note.tenant_id == user.tenant_id))
    if not n:
        raise HTTPException(status_code=404, detail="Not bulunamadi")
    if not n.is_serbest:
        raise HTTPException(status_code=400, detail="Otomatik notlar silinemez (refresh ile yonetilir)")
    db.delete(n)
    db.commit()
