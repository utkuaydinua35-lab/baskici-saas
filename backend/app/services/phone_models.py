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


# Ürün adının başına yapışabilen marka sözcükleri. Shopify ürün adlarında sık:
# "Xiaomi Redmi Note 13 Pro 5G" -> katalogda "REDMI-NOTE-13-PRO-5G" olarak duruyor.
_BRAND_TOKENS = {
    "XIAOMI", "REDMI", "POCO", "SAMSUNG", "GALAXY", "APPLE", "IPHONE", "OPPO",
    "REALME", "HUAWEI", "VIVO", "TECNO", "INFINIX", "HONOR", "GENERAL", "OMIX",
    "REEDER", "NOKIA", "MOTOROLA", "ONEPLUS",
}


def key_variants(key: str) -> list[str]:
    """Aynı telefonu gösterebilecek anahtar adayları — spesifikten genele.

    Baştaki marka sözcükleri sırayla soyulur:
      XIAOMI-REDMI-NOTE-13-PRO-5G -> REDMI-NOTE-13-PRO-5G -> NOTE-13-PRO-5G
    Böylece ürün adında fazladan marka geçtiğinde eşleşme kaçmaz.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(k: str) -> None:
        if k and k not in seen:
            seen.add(k)
            out.append(k)

    k = (key or "").upper()
    add(k)
    add(canonical_key(k))
    # Marka sözcüğünü YALNIZCA kalan kısım DA bir markayla başlıyorsa soy.
    # Gerçek dünyadaki fazlalık hep çift marka: "Xiaomi Redmi", "Samsung Galaxy",
    # "Apple iPhone". Bunun ötesine soymak TEHLİKELİ:
    #   REDMI-12 -> 12  ve '12' Apple takma adı -> iPhone 12 ölçüsü (7.35x14.9)
    # Bu şekilde Redmi 12 siparişi iPhone ölçüsüyle basılmıştı.
    parts = [p for p in k.split("-") if p]
    while len(parts) > 2 and parts[0] in _BRAND_TOKENS and parts[1] in _BRAND_TOKENS:
        parts = parts[1:]
        add("-".join(parts))
    return out


def _unique_brand_prefixed(key: str) -> str | None:
    """Ters yön: ürün adında marka YOK ama katalogda VAR ('NOTE-13-PRO-5G' ->
    'REDMI-NOTE-13-PRO-5G'). YALNIZCA tek aday varsa döner; birden fazla marka
    eşleşiyorsa (NOTE-8 hem REDMI hem SAMSUNG) TAHMİN ETMEZ — yanlış ölçüyle
    basmaktansa 'tanınmıyor' demek doğrusu."""
    k = (key or "").upper()
    if not k or k.split("-")[0] in _BRAND_TOKENS:
        return None
    # Çıplak Apple takma adı ('12', 'XR', '15-PRO') marka öneki ALMAZ — o zaten iPhone.
    if is_apple_alias_key(k):
        return None
    base = _baseline_key_set()
    adaylar = [f"{b}-{k}" for b in _BRAND_TOKENS if f"{b}-{k}" in base]
    return adaylar[0] if len(adaylar) == 1 else None


def _db_lookup(db: Session, tenant_id: uuid.UUID, key: str) -> PhoneModel | None:
    """Önce tenant'a özel, yoksa global (tenant_id IS NULL) aktif kayıt.
    Kayıt çıplak Apple alias'ı ('16-PROMAX') ya da kanonik ('IPHONE-16-PROMAX')
    olarak saklanmış olabilir — ikisini de dene (eşleşme kaçmasın)."""
    if not key:
        return None
    k = key.upper()
    variants = {k, canonical_key(k)}
    if k.startswith("IPHONE-"):
        variants.add(k[len("IPHONE-"):])   # kanonik -> çıplak alias ikizi
    row = db.scalar(
        select(PhoneModel).where(
            PhoneModel.tenant_id == tenant_id,
            PhoneModel.spec_key.in_(variants),
            PhoneModel.is_active.is_(True),
        )
    )
    if row:
        return row
    return db.scalar(
        select(PhoneModel).where(
            PhoneModel.tenant_id.is_(None),
            PhoneModel.spec_key.in_(variants),
            PhoneModel.is_active.is_(True),
        )
    )


def get_spec(db: Session, tenant_id: uuid.UUID, model: str):
    """(width_cm, height_cm, radius_cm) tuple döndür; bulunamazsa None.

    case_dimensions.get_spec ile AYNI dönüş tipi — mevcut PDF motoru
    çağrılarını birebir değiştirebilirsin.

    Eşleşme marka önekine TOLERANSLI: ürün adında fazladan marka geçse de
    ("Xiaomi Redmi Note 13 Pro 5G") katalogdaki kayıt bulunur.
    """
    if not model:
        return None
    key = normalize_key(model)
    variants = key_variants(key)
    for k in variants:
        row = _db_lookup(db, tenant_id, k)
        if row is not None:
            return (row.width_cm, row.height_cm, row.radius_cm)
    spec = cd.get_spec(model)
    if spec:
        return spec
    for k in variants:
        spec = cd.get_spec(k)
        if spec:
            return spec
    k2 = _unique_brand_prefixed(key)
    if k2:
        row = _db_lookup(db, tenant_id, k2)
        if row is not None:
            return (row.width_cm, row.height_cm, row.radius_cm)
        return cd.get_spec(k2)
    return None


def has_spec(db: Session, tenant_id: uuid.UUID, model: str) -> bool:
    return get_spec(db, tenant_id, model) is not None


def resolve_source(db: Session, tenant_id: uuid.UUID, model: str) -> str | None:
    """Modelin nereden tanındığını söyle: 'db' | 'baseline' | None.
    Ölçü DÖNDÜRMEZ — baseline gizliliğini korur."""
    if not model:
        return None
    key = normalize_key(model)
    for k in key_variants(key):
        if _db_lookup(db, tenant_id, k) is not None:
            return "db"
    if get_spec(db, tenant_id, model) is not None:
        return "baseline"
    return None


def baseline_keys() -> list[str]:
    """Baseline model adlari (kalip taninan 339 model)."""
    return cd.all_model_keys()


def baseline_count() -> int:
    """Baseline'daki gizli model sayısı (sadece adet, ölçü değil)."""
    return cd.spec_count()


# ─── Apple takma-ad birlestirme + kanonik gorunen ad ──────────────────────
# Baseline'da ayni telefonun iki anahtari var: 'IPHONE-15' ve cıplak '15'
# (ayni olcu). Cıplak olan bir TAKMA AD'dir; listelerde tek kanonik ('iPhone 15')
# gosterilir. Kural: bir anahtarin 'IPHONE-<anahtar>' ikizi baseline'da varsa
# o cıplak anahtar bir Apple takma adidir.
from functools import lru_cache as _lru_cache


@_lru_cache(maxsize=1)
def _baseline_key_set() -> frozenset:
    return frozenset(cd.all_model_keys())


def is_apple_alias_key(key: str) -> bool:
    """key cıplak Apple takma adi mi (IPHONE- ikizi var)? Orn '15', 'XR', 'SE-2022'."""
    if not key:
        return False
    k = key.upper()
    if k.startswith("IPHONE"):
        return False
    return ("IPHONE-" + k) in _baseline_key_set()


_IPHONE_TOKEN = {
    "PROMAX": "Pro Max", "PRO": "Pro", "PLUS": "Plus", "MINI": "Mini", "MAX": "Max",
    "SE": "SE", "XR": "XR", "XS": "XS", "X": "X",
}


def _prettify_iphone(key: str) -> str:
    """'IPHONE-15-PROMAX' -> 'iPhone 15 Pro Max', 'IPHONE-XS-MAX' -> 'iPhone XS Max'."""
    rest = key.upper()
    if rest.startswith("IPHONE-"):
        rest = rest[len("IPHONE-"):]
    elif rest == "IPHONE":
        rest = ""
    parts = [p for p in rest.split("-") if p]
    words = [_IPHONE_TOKEN.get(p, p) for p in parts]  # bilinmeyen (rakam/yil) aynen
    return ("iPhone " + " ".join(words)).strip()


# Katalog anahtarini okunur ada cevirirken kullanilan sozlukler.
_BRAND_PRETTY = {
    "SAMSUNG": "Samsung", "GALAXY": "Galaxy", "REDMI": "Redmi", "XIAOMI": "Xiaomi",
    "POCO": "POCO", "OPPO": "Oppo", "REALME": "realme", "TECNO": "Tecno",
    "HUAWEI": "Huawei", "VIVO": "vivo", "INFINIX": "Infinix", "HONOR": "Honor",
    "OMIX": "Omix", "REEDER": "Reeder", "GENERAL": "General Mobile",
}
_TOKEN_PRETTY = {
    "PROMAX": "Pro Max", "PRO": "Pro", "MAX": "Max", "PLUS": "Plus", "ULTRA": "Ultra",
    "MINI": "Mini", "LITE": "Lite", "NOTE": "Note", "NEO": "Neo", "PRIME": "Prime",
    "POWER": "Power", "FE": "FE", "SE": "SE",
}


def baseline_display_name(key: str) -> str:
    """Katalog anahtarini okunur ada cevir — YALNIZCA LISTE GORUNUMU icin.

    'SAMSUNG-A15' -> 'Samsung A15', 'REDMI-NOTE-8' -> 'Redmi Note 8',
    'IPHONE-15-PROMAX' -> 'iPhone 15 Pro Max'. Eslesme/kalip mantigini ETKILEMEZ.
    canonical_model_name'den ayri: o fonksiyon kullanicinin yazdigi serbest metni de
    aliyor ve onu yeniden yazmamali; bu ise her zaman bir KATALOG ANAHTARI alir.
    """
    if not key:
        return key
    k = key.upper()
    if k.startswith("IPHONE") or is_apple_alias_key(k):
        return canonical_model_name(k)
    parts = [p for p in k.split("-") if p]
    out = []
    for i, p in enumerate(parts):
        if i == 0 and p in _BRAND_PRETTY:
            out.append(_BRAND_PRETTY[p])
        elif p in _TOKEN_PRETTY:
            out.append(_TOKEN_PRETTY[p])
        elif any(c.isdigit() for c in p):
            out.append(p)          # model numarasi: A15, S24, 12T -> aynen
        else:
            out.append(p.capitalize())
    return " ".join(out)


def canonical_key(key: str) -> str:
    """spec_key'i kanonik forma getir: cıplak Apple takma adi -> IPHONE- ikizi."""
    if not key:
        return key
    k = key.upper()
    if is_apple_alias_key(k):
        return "IPHONE-" + k
    return k


def canonical_model_name(model: str) -> str:
    """Model adini tek kanonik gorunume cevir. Cıplak Apple ('15', '15 Pro Max')
    -> 'iPhone 15' / 'iPhone 15 Pro Max'. Apple olmayan (Samsung, Xiaomi vb.)
    dokunulmaz (kırpma disinda). Eslesme/kalip mantigini ETKILEMEZ — yalniz gorunum."""
    if not model:
        return model
    key = normalize_key(model)
    if is_apple_alias_key(key):
        key = "IPHONE-" + key.upper()
    if key.upper().startswith("IPHONE"):
        return _prettify_iphone(key)
    return model.strip()
