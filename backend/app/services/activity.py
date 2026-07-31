"""Aktivite günlüğü yazma servisi.

Kural: günlük kaydı ASLA asıl işlemi bozmaz. Her şey try/except içinde;
kayıt atılamazsa sessizce loglanır ve işlem devam eder.

Kayıt commit ETMEZ — çağıranın kendi commit'iyle kalıcılaşır (aynı
transaction: işlem geri alınırsa günlük de geri alınır, yalan kayıt olmaz).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import ActivityLog

log = logging.getLogger("activity")

# action -> Türkçe etiket (panel ile aynı sözlük; bilinmeyen action ham gösterilir)
ACTION_LABELS: dict[str, str] = {
    "urun_ekle": "Ürün eklendi",
    "urun_guncelle": "Ürün güncellendi",
    "urun_sil": "Ürün silindi",
    "urun_toplu": "Ürünlerde toplu işlem",
    "urun_ice_aktar": "CSV içe aktarıldı",
    "koleksiyon_ekle": "Koleksiyon oluşturuldu",
    "koleksiyon_guncelle": "Koleksiyon güncellendi",
    "koleksiyon_sil": "Koleksiyon silindi",
    "kupon_ekle": "İndirim oluşturuldu",
    "kupon_guncelle": "İndirim güncellendi",
    "kupon_sil": "İndirim silindi",
    "ayar_guncelle": "Mağaza ayarı değiştirildi",
    "tema_yayinla": "Tema yayınlandı",
    "iade": "Para iadesi yapıldı",
    "kargo_gonderi": "Kargo gönderisi oluşturuldu",
    "kargo_geri": "Kargo gönderisi geri alındı",
    "siparis_duzenle": "Sipariş düzenlendi",
}


def label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


def _json_safe(value):
    """JSONB'ye yazılabilir hale getir — Decimal/UUID/datetime metne çevrilir.

    (Ham Decimal yazılırsa commit anında TypeError patlar ve ASIL işlemi
    geri alır; günlük hiçbir koşulda işlemi bozmamalı.)"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def record(
    db: Session, user, action: str, *,
    store_id=None, entity_type: str | None = None, entity_id=None,
    entity_label: str | None = None, detail: dict | None = None,
) -> None:
    """Aktivite kaydı ekle (commit etmez)."""
    try:
        detail = _json_safe(detail) if detail else None
        db.add(ActivityLog(
            tenant_id=getattr(user, "tenant_id", None),
            store_id=store_id,
            user_email=getattr(user, "email", None),
            action=action[:40],
            entity_type=(entity_type or None) and entity_type[:30],
            entity_id=str(entity_id)[:60] if entity_id else None,
            entity_label=(entity_label or None) and str(entity_label)[:300],
            detail=detail or None,
        ))
    except Exception:  # noqa: BLE001 — günlük hatası işlemi durdurmaz
        log.exception("aktivite kaydı yazılamadı (action=%s)", action)


def diff(before: dict, after: dict, fields: tuple[str, ...]) -> dict:
    """Değişen alanların {alan: [eski, yeni]} dökümü — kayıt detayı için."""
    out: dict[str, list] = {}
    for f in fields:
        eski, yeni = before.get(f), after.get(f)
        if str(eski) != str(yeni):
            out[f] = [eski, yeni]
    return out
