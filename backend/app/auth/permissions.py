"""
Yetki sistemi — esnek panel bazli yetkiler.

Her kullanicinin `permissions` listesi (JSONB) hangi panelleri gorebilecegini belirler.
Yonetici (role='yonetici' veya 'owner') TUM yetkilere sahiptir ve baskalarina atayabilir.
Roller, hazir yetki paketleridir; yonetici kullanici basina serbestce duzenleyebilir.
"""
from __future__ import annotations

# Tum panel yetkileri (tek kaynak)
ALL_PERMISSIONS = [
    "dashboard",
    "siparisler",
    "paketleme",
    "destek",
    "tasarim",
    "kisiye_ozel",
    "aksesuar",
    "couple",
    "kalip",
    "stok",
    "telefon_modelleri",
    "ayarlar",
    "kullanici_yonetimi",
    "bayii",
    "pazarlama",
    "vitrin",
    "musteri",
]

# Hazir rol sablonlari (yonetici kullanici eklerken baslangic noktasi)
ROLE_TEMPLATES = {
    "yonetici": list(ALL_PERMISSIONS),  # her sey
    "baskici": ["dashboard", "kalip", "stok", "tasarim", "kisiye_ozel", "aksesuar", "couple", "telefon_modelleri"],
    "paketlemeci": ["dashboard", "paketleme", "destek", "siparisler"],
    "grafiker": ["kisiye_ozel", "tasarim"],
}

# Yonetici sayilan roller (her zaman tum yetkiler + yonetim)
ADMIN_ROLES = {"yonetici", "owner"}


def is_admin(user) -> bool:
    return (getattr(user, "role", None) or "") in ADMIN_ROLES


def effective_permissions(user) -> list[str]:
    """Kullanicinin gercek yetkileri. Yonetici -> hepsi."""
    if is_admin(user):
        return list(ALL_PERMISSIONS)
    perms = getattr(user, "permissions", None) or []
    if isinstance(perms, list):
        return [p for p in perms if p in ALL_PERMISSIONS]
    return []


def has_permission(user, perm: str) -> bool:
    if is_admin(user):
        return True
    return perm in (getattr(user, "permissions", None) or [])


def has_any_permission(user, perms) -> bool:
    """Kullanicinin verilen yetkilerden EN AZ BIRINE sahip olup olmadigi."""
    if is_admin(user):
        return True
    have = getattr(user, "permissions", None) or []
    return any(p in have for p in perms)
