"""
Telefon modeli ölçü OVERLAY servisi.

Mimari:
  Ölçü aranırken sıra → (1) tenant'a özel DB kaydı
                        (2) global DB kaydı (tenant_id IS NULL)
                        (3) baseline (gizli case_dimensions modülü, 339 model)

Böylece:
  - case_dimensions._MODEL_SPECS (ticari sır) DOSYADA el değmeden kalır.
  - Yeni telefon çıkınca / yanlış ölçü düzeltilince → panelden DB'ye eklenir,
    deploy gerektirmez ve baseline'ı EZER (override).
  - DB'ye eklenen modeller tenant'ın kendi verisidir; API ile ölçüsü dönebilir.
    Baseline ölçüleri ise ASLA serialize edilmez (sadece "tanınıyor mu" testi).

PDF / kalıp motoru ölçü çağrılarını DOĞRUDAN case_dimensions yerine buradan
yapmalı:  spec = phone_models.get_spec(db, tenant_id, model)
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PhoneModel
from app.services._private import case_dimensions as cd

# Baseline'daki normalize + trim sabitini tek noktadan dışa aç
TRIM_AMOUNT_CM = cd.TRIM_AMOUNT_CM


def normalize_key(model: str) -> str:
    """Model adını baseline ile AYNI normalizasyon kuralıyla anahtara çevir."""
    if not model:
        return ""
    return cd._normalize_to_spec_key(model)


def _db_lookup(db: Session, tenant_id: uuid.UUID, key: str) -> PhoneModel | None:
    """Önce tenant'a özel, yoksa global (tenant_id IS NULL) aktif kayıt."""
    if not key:
        return None
    row = db.scalar(
        select(PhoneModel).where(
            PhoneModel.tenant_id == tenant_id,
            PhoneModel.spec_key == key,
            PhoneModel.is_active.is_(True),
        )
    )
    if row:
        return row
    return db.scalar(
        select(PhoneModel).where(
            PhoneModel.tenant_id.is_(None),
            PhoneModel.spec_key == key,
            PhoneModel.is_active.is_(True),
        )
    )


def get_spec(db: Session, tenant_id: uuid.UUID, model: str):
    """(width_cm, height_cm, radius_cm) tuple döndür; bulunamazsa None.

    case_dimensions.get_spec ile AYNI dönüş tipi — mevcut PDF motoru
    çağrılarını birebir değiştirebilirsin.
    """
    if not model:
        return None
    key = normalize_key(model)
    row = _db_lookup(db, tenant_id, key)
    if row is not None:
        return (row.width_cm, row.height_cm, row.radius_cm)
    return cd.get_spec(model)


def has_spec(db: Session, tenant_id: uuid.UUID, model: str) -> bool:
    return get_spec(db, tenant_id, model) is not None


def resolve_source(db: Session, tenant_id: uuid.UUID, model: str) -> str | None:
    """Modelin nereden tanındığını söyle: 'db' | 'baseline' | None.
    Ölçü DÖNDÜRMEZ — baseline gizliliğini korur."""
    if not model:
        return None
    key = normalize_key(model)
    if _db_lookup(db, tenant_id, key) is not None:
        return "db"
    if cd.get_spec(model) is not None:
        return "baseline"
    return None


def baseline_keys() -> list[str]:
    """Baseline model adlari (kalip taninan 339 model)."""
    return cd.all_model_keys()


def baseline_count() -> int:
    """Baseline'daki gizli model sayısı (sadece adet, ölçü değil)."""
    return cd.spec_count()
