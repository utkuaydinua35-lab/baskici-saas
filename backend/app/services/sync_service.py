"""
Ortak senkronizasyon servisi — hem /fetch endpoint'i hem saatlik scheduler kullanır.
Tek bir mağazayı senkronize eder, Notification üretir.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.models import Notification, Store


def sync_store(db: Session, store: Store, *, create_notification: bool = True) -> dict:
    """
    Bir mağazayı senkronize et. orders.py'deki _upsert_order'ı kullanır.
    Dönüş: {success, fetched_count, new_count, updated_count, duration_seconds, message}
    """
    # Geç import — döngüsel bağımlılığı önle
    from app.routers.orders import _upsert_order

    start = datetime.now(UTC)
    result = {
        "success": False,
        "store_id": str(store.id),
        "store_name": store.name,
        "fetched_count": 0,
        "new_count": 0,
        "updated_count": 0,
        "duration_seconds": 0.0,
        "message": "",
    }

    try:
        adapter = get_adapter(store)
        orders_raw = adapter.get_all_active_orders(limit=250)
    except Exception as e:
        result["message"] = f"Veri alınamadı: {str(e)[:200]}"
        if create_notification:
            db.add(Notification(
                tenant_id=store.tenant_id, store_id=store.id, kind="error",
                title=f"{store.name}: senkronizasyon hatası",
                body=result["message"],
            ))
            db.commit()
        return result

    new_count = updated_count = 0
    errors = 0
    for raw in orders_raw:
        try:
            _, is_new, was_updated = _upsert_order(
                db, tenant_id=store.tenant_id, store_id=store.id, raw=raw,
            )
            if is_new:
                new_count += 1
            elif was_updated:
                updated_count += 1
        except Exception:
            errors += 1

    store.last_fetched_at = datetime.now(UTC)

    duration = (datetime.now(UTC) - start).total_seconds()
    parts = [f"{len(orders_raw)} sipariş"]
    if new_count: parts.append(f"{new_count} yeni")
    if updated_count: parts.append(f"{updated_count} güncellendi")
    if errors: parts.append(f"{errors} hata")
    msg = " · ".join(parts)

    result.update({
        "success": True,
        "fetched_count": len(orders_raw),
        "new_count": new_count,
        "updated_count": updated_count,
        "duration_seconds": round(duration, 2),
        "message": msg,
    })

    # Sadece anlamlı değişiklikte bildirim
    if create_notification and (new_count or updated_count):
        db.add(Notification(
            tenant_id=store.tenant_id, store_id=store.id, kind="sync",
            title=f"{store.name}: {new_count} yeni, {updated_count} güncellendi",
            body=msg,
        ))

    db.commit()
    return result


def sync_all_stores(db: Session) -> list[dict]:
    """Tüm aktif mağazaları senkronize et (scheduler için)."""
    stores = db.scalars(select(Store).where(Store.is_active == True)).all()  # noqa: E712
    results = []
    for store in stores:
        try:
            results.append(sync_store(db, store, create_notification=True))
        except Exception as e:
            results.append({"success": False, "store_name": store.name, "message": str(e)[:200]})
    return results
