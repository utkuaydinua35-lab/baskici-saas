"""Bildirimler + manuel toplu senkronizasyon — /api/notifications/*"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func as sql_func, select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import Notification, User
from app.services.sync_service import sync_all_stores

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _serialize(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "store_id": str(n.store_id) if n.store_id else None,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("", response_model=None)
def list_notifications(
    only_unread: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(Notification).where(Notification.tenant_id == user.tenant_id)
    if only_unread:
        q = q.where(Notification.is_read == False)  # noqa: E712
    q = q.order_by(desc(Notification.created_at)).limit(limit)
    items = db.scalars(q).all()
    unread = db.scalar(
        select(sql_func.count(Notification.id)).where(
            Notification.tenant_id == user.tenant_id,
            Notification.is_read == False,  # noqa: E712
        )
    ) or 0
    return {"items": [_serialize(n) for n in items], "unread_count": unread}


@router.get("/akis", response_model=dict)
def akis(since: str | None = None, user: User = Depends(get_current_user),
         db: Session = Depends(get_db)):
    """Masaüstü uygulamasının sorduğu olay akışı: `since`dan BERİ ne düştü?

    Bayi tarafındaki /api/bayii/bildirimler ile AYNI sözleşme (id, tur, baslik,
    govde, at, link + sunucu_saati) — masaüstü kabuğu iki profilde de aynı kodu
    kullanıyor. Kaynak: panelin kendi bildirim kayıtları.

    since YOKSA olay dönmez, yalnız imleç döner: uygulama ilk açılışta geçmişi
    bildirim yağmuruna çevirmesin.

    ⚠ İMLEÇ 5 SANİYE GERİDEN: Postgres'te now() işlem başlangıç saatidir; o an
    süren bir işlem imlecin gerisinde bir created_at ile yazılıp sonsuza dek
    kaçabilirdi. Tekrar gösterimi uygulama olay kimlikleriyle önler.
    """
    from datetime import UTC, datetime, timedelta

    simdi = datetime.now(UTC)
    imlec = (simdi - timedelta(seconds=5)).isoformat()
    if not since:
        return {"sunucu_saati": imlec, "olaylar": []}
    ham = since.strip().replace("Z", "+00:00")
    baslangic = None
    # "+00:00" sorgu dizesinde boşluğa çözülür — ikinci deneme onu geri çevirir
    for aday in (ham, ham.replace(" ", "+")):
        try:
            baslangic = datetime.fromisoformat(aday)
            break
        except ValueError:
            continue
    if baslangic is None:
        raise HTTPException(400, "Geçersiz 'since' zamanı")
    if baslangic.tzinfo is None:
        baslangic = baslangic.replace(tzinfo=UTC)
    baslangic = max(baslangic, simdi - timedelta(hours=24))

    satirlar = db.scalars(
        select(Notification).where(
            Notification.tenant_id == user.tenant_id,
            Notification.created_at > baslangic,
        ).order_by(Notification.created_at).limit(50)
    ).all()
    return {
        "sunucu_saati": imlec,
        "olaylar": [{
            "id": f"bildirim-{n.id}",
            "tur": n.kind or "bilgi",
            "baslik": n.title,
            "govde": (n.body or "")[:200],
            "at": n.created_at.isoformat() if n.created_at else imlec,
            "link": n.link,
        } for n in satirlar],
    }


@router.post("/sync-all", response_model=None)
def sync_all(
    # TUM magazalarin senkronunu tetikliyor: agir is + Shopify API kotasi.
    # Izin istemiyordu, yani kiracidaki herhangi bir personel (or. yalniz
    # paketleme yetkisi olan) bunu tekrar tekrar calistirip kotayi yakabilir
    # ve isletmenin senkronunu kilitleyebilirdi. Ust bardaki dugme de ayni
    # izne baglandi, yoksa gorunup 403 verirdi.
    user: User = Depends(require_permission("siparisler")),
    db: Session = Depends(get_db),
):
    results = sync_all_stores(db)
    ok = sum(1 for r in results if r.get("success"))
    return {
        "success": True,
        "stores": len(results),
        "ok": ok,
        "new_count": sum(r.get("new_count", 0) for r in results),
        "updated_count": sum(r.get("updated_count", 0) for r in results),
        "results": results,
    }


@router.patch("/{notification_id}/read", response_model=None)
def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.tenant_id == user.tenant_id)
        .values(is_read=True)
    )
    db.commit()
    return {"ok": True}


@router.post("/read-all", response_model=None)
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        update(Notification)
        .where(Notification.tenant_id == user.tenant_id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    db.commit()
    return {"ok": True}
