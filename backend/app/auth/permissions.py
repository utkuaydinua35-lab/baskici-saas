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
    # DIKKAT: bayinin KENDI portali. Yonetim tarafindaki bayi ekranlarinin
    # izni "bayii"; ayni ad verilseydi bayi kullanicisi
    # require_any_permission("siparisler", "bayii") ile korunan yonetim
    # uclarina da girerdi. Bu yuzden AYRI izin.
    "bayii_portal",
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
    # Bayi hesabi: SADECE kendi portali. Baska hicbir izin eklenmemeli.
    "bayii_portal": ["bayii_portal"],
}

# Yonetici sayilan roller (her zaman tum yetkiler + yonetim)
ADMIN_ROLES = {"yonetici", "owner"}


def is_admin(user) -> bool:
    return (getattr(user, "role", None) or "") in ADMIN_ROLES


# ── Plan kısıtı ───────────────────────────────────────────────
# Kiralama: kullanıcının yetkisi, KİRACININ PLANININ açtığıyla kesişir.
# Yönetici/owner eskiden "her şey" demekti; kiracı kendi mağazasının owner'ı
# olduğu için bu, Basic planla baskı, kalıp ve bayi modüllerine girmek
# demekti. Artık owner da planın sınırını aşamaz.
#
# `_plan_yetkileri` get_current_user tarafından istek başına yazılır:
#   frozenset → bu yetkilerle sınırlı
#   None      → sınırsız (platform yöneticisi, ya da istek bağlamı dışı —
#               zamanlayıcı/betik gibi kiracı bağlamı olmayan kod yolları)

def _plan_izni(user, perm: str) -> bool:
    izinli = getattr(user, "_plan_yetkileri", None)
    return izinli is None or perm in izinli


def effective_permissions(user) -> list[str]:
    """Kullanicinin gercek yetkileri: kendi yetkisi ∩ planin actigi."""
    if is_admin(user):
        adaylar = list(ALL_PERMISSIONS)
    else:
        perms = getattr(user, "permissions", None) or []
        adaylar = [p for p in perms if p in ALL_PERMISSIONS] if isinstance(perms, list) else []
    return [p for p in adaylar if _plan_izni(user, p)]


def has_permission(user, perm: str) -> bool:
    if not _plan_izni(user, perm):
        return False
    if is_admin(user):
        return True
    return perm in (getattr(user, "permissions", None) or [])


def has_any_permission(user, perms) -> bool:
    """Kullanicinin verilen yetkilerden EN AZ BIRINE sahip olup olmadigi."""
    return any(has_permission(user, p) for p in perms)
