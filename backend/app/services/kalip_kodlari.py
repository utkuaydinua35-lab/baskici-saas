"""
Kalıp kodları - telefon modeli + renk → kalıp kodu eşleme.

BERNZ'in siparis_common.py'sinden port edildi. Tenant-agnostic.

İki strateji:
- "full"   (BERNZ/505): iPhone + Samsung + Xiaomi + diğer Çinli — 3 harf gerekir
- "simple" (Lunera/Casiva): sadece iPhone — 2 harf yeterli

Kalıp kodu örnek (3 harf "ABC" verildiğinde):
    iphone_11_siyah = "A1"
    iphone_11_beyaz = "A2"
    iphone_13_siyah = "A3"
    ...
    samsung_ultra   = "C1"
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ─── iPhone grup tanımları ─────────────────────────────────
# BERNZ config.py'dan port. Her grup aynı kalıbı paylaşır.

IPHONE_GROUPS: dict[str, list[str]] = {
    "11": [
        "6", "6s", "6s plus", "6 plus", "7", "7 plus", "8", "8 plus",
        "x", "xs", "xs max", "xr",
        "11", "11 pro", "11 pro max",
        "12", "12 pro", "12 mini", "13 mini",
        "se", "se 2", "se 2020", "se 2022", "se 3",
    ],
    "13": ["13", "14", "16e"],
    "15": ["15", "16", "17"],
    "13_pro_max": [
        "12 pro max", "13 pro", "13 pro max",
        "14 plus", "15 plus", "16 plus",
    ],
    "15_pro": ["14 pro", "15 pro", "16 pro", "17 pro"],
    "15_pro_max": ["14 pro max", "15 pro max", "16 pro max", "17 pro max"],
}


# ─── KalipKodlari veri sınıfı ──────────────────────────────

@dataclass
class KalipKodlari:
    """Bir pipeline çalışmasındaki tüm kalıp kodlarını taşır."""
    # iPhone — renkli (siyah/beyaz) ayrı kalıp
    iphone_11_siyah: str = ""
    iphone_11_beyaz: str = ""
    iphone_13_siyah: str = ""
    iphone_13_beyaz: str = ""
    iphone_15_siyah: str = ""
    iphone_15_beyaz: str = ""
    iphone_13_pro_max_siyah: str = ""
    iphone_13_pro_max_beyaz: str = ""
    iphone_15_pro_siyah: str = ""
    iphone_15_pro_beyaz: str = ""
    iphone_15_pro_max_siyah: str = ""
    iphone_15_pro_max_beyaz: str = ""

    # Özel tipler
    parlak: str = ""
    seffaf: str = ""

    # Çin
    redmi: str = ""
    xiaomi: str = ""
    diger_cin: str = ""

    # Samsung
    samsung_ultra: str = ""
    samsung_s: str = ""
    samsung_a: str = ""

    def to_dict(self) -> dict:
        """Frontend için sözlüğe dönüştür."""
        return {k: v for k, v in self.__dict__.items() if v}


# ─── Harf → KalipKodlari oluşturma ─────────────────────────

def create_kalip_kodlari_3harf(h1: str, h2: str, h3: str) -> KalipKodlari:
    """
    BERNZ/505 için 3 harfli kalıp kodu üreteci.

    Örnek harf "ABC" → A1, A2, ..., A9, B1, ..., C1, C2
    """
    k = KalipKodlari()
    # 1. harf — iPhone serisi
    k.iphone_11_siyah = f"{h1}1"
    k.iphone_11_beyaz = f"{h1}2"
    k.iphone_13_siyah = f"{h1}3"
    k.iphone_13_beyaz = f"{h1}4"
    k.iphone_15_siyah = f"{h1}5"
    k.iphone_15_beyaz = f"{h1}6"
    k.iphone_13_pro_max_siyah = f"{h1}7"
    k.iphone_13_pro_max_beyaz = f"{h1}8"
    k.iphone_15_pro_siyah = f"{h1}9"
    # 2. harf — iPhone devam + özel + Xiaomi + Samsung
    k.iphone_15_pro_beyaz = f"{h2}1"
    k.iphone_15_pro_max_siyah = f"{h2}2"
    k.iphone_15_pro_max_beyaz = f"{h2}3"
    k.seffaf = f"{h2}4"
    k.parlak = f"{h2}5"
    k.redmi = f"{h2}6"
    k.xiaomi = f"{h2}7"
    k.samsung_a = f"{h2}8"
    k.samsung_s = f"{h2}9"
    # 3. harf — Samsung Ultra + diğer Çin
    k.samsung_ultra = f"{h3}1"
    k.diger_cin = f"{h3}2"
    return k


def create_kalip_kodlari_2harf(h1: str, h2: str) -> KalipKodlari:
    """
    Lunera/Casiva için 2 harfli kalıp kodu üreteci.
    Sadece iPhone — Samsung/Çin kullanılmaz.
    """
    k = KalipKodlari()
    k.iphone_11_siyah = f"{h1}1"
    k.iphone_11_beyaz = f"{h1}2"
    k.iphone_13_siyah = f"{h1}3"
    k.iphone_13_beyaz = f"{h1}4"
    k.iphone_15_siyah = f"{h1}5"
    k.iphone_15_beyaz = f"{h1}6"
    k.iphone_13_pro_max_siyah = f"{h1}7"
    k.iphone_13_pro_max_beyaz = f"{h1}8"
    k.iphone_15_pro_siyah = f"{h1}9"
    k.iphone_15_pro_beyaz = f"{h2}1"
    k.iphone_15_pro_max_siyah = f"{h2}2"
    k.iphone_15_pro_max_beyaz = f"{h2}3"
    return k


def build_kalip_kodlari(letters: str, strategy: str) -> KalipKodlari:
    """
    Letters input'undan strategy'e göre KalipKodlari üret.

    letters: "ABC" / "ABc" / "A,B,C" — tek karakterler ayıklanır
    strategy: "full" → 3 harf gerek / "simple" → 2 harf gerek
    """
    cleaned = [c.upper() for c in letters if c.isalpha()]
    if strategy == "full":
        if len(cleaned) < 3:
            raise ValueError(f"BERNZ/505 stratejisi 3 harf gerektirir, verilen: {len(cleaned)}")
        return create_kalip_kodlari_3harf(cleaned[0], cleaned[1], cleaned[2])
    elif strategy == "simple":
        if len(cleaned) < 2:
            raise ValueError(f"Lunera/Casiva stratejisi 2 harf gerektirir, verilen: {len(cleaned)}")
        return create_kalip_kodlari_2harf(cleaned[0], cleaned[1])
    raise ValueError(f"Bilinmeyen strateji: {strategy}")


# ─── iPhone model normalize + grup tespiti ─────────────────

def normalize_iphone_model(phone_model: str | None) -> str:
    """'iPhone 13 Pro' → '13 pro' formatı."""
    if not phone_model:
        return ""
    model = phone_model.lower()
    model = re.sub(r'i\s*phone\s*', '', model)
    model = model.replace("apple", "").strip()
    model = model.replace("-", " ").replace("_", " ")
    return re.sub(r'\s+', ' ', model).strip()


def get_iphone_group(phone_model: str | None) -> str | None:
    """iPhone modelini grup adına eşle ('15_pro_max' / '11' / vs)."""
    normalized = normalize_iphone_model(phone_model)
    if not normalized:
        return None
    # Önce daha spesifik (pro_max) sonra genel (11)
    for group_name in ["15_pro_max", "13_pro_max", "15_pro", "15", "13", "11"]:
        for model in IPHONE_GROUPS.get(group_name, []):
            if model == normalized or normalized.startswith(model) or model in normalized:
                return group_name
    return None


def get_iphone_kalip_kodu(phone_model: str, renk: str, kk: KalipKodlari) -> str:
    """iPhone modeli + renk → kalıp kodu (örn 'A1')."""
    group = get_iphone_group(phone_model)
    if not group or not renk:
        return ""
    renk_lower = renk.lower().strip()
    kalip_map = {
        ("11", "siyah"): kk.iphone_11_siyah,
        ("11", "beyaz"): kk.iphone_11_beyaz,
        ("13", "siyah"): kk.iphone_13_siyah,
        ("13", "beyaz"): kk.iphone_13_beyaz,
        ("15", "siyah"): kk.iphone_15_siyah,
        ("15", "beyaz"): kk.iphone_15_beyaz,
        ("13_pro_max", "siyah"): kk.iphone_13_pro_max_siyah,
        ("13_pro_max", "beyaz"): kk.iphone_13_pro_max_beyaz,
        ("15_pro", "siyah"): kk.iphone_15_pro_siyah,
        ("15_pro", "beyaz"): kk.iphone_15_pro_beyaz,
        ("15_pro_max", "siyah"): kk.iphone_15_pro_max_siyah,
        ("15_pro_max", "beyaz"): kk.iphone_15_pro_max_beyaz,
    }
    return kalip_map.get((group, renk_lower), "")


# ─── Tam kalıp kodu hesaplama (strategy dispatch) ──────────

def get_kalip_kodu_full(phone_model: str, design_name: str, design_renk: str,
                       kk: KalipKodlari, full_title: str = "") -> str:
    """BERNZ/505 stratejisi — iPhone + Samsung + Xiaomi + Diğer Çinli."""
    phone_lower = (phone_model or "").lower()
    design_lower = (design_name or "").lower()
    title_lower = (full_title or "").lower()
    combined = f"{phone_lower} {design_lower} {title_lower}"

    # Parlak öncelikli
    if any(kw in combined for kw in ["parlak", "glitter", "simli", "sim taşlı", "hologram"]):
        if kk.parlak:
            return kk.parlak

    # Şeffaf (MagSafe değilse)
    seffaf_kw = ["şeffaf", "seffaf", "clear", "transparan", "saydam"]
    exclude_kw = ["magsafe", "mag safe", "halka", "ring", "yüzük"]
    if any(kw in combined for kw in seffaf_kw):
        if not any(kw in title_lower for kw in exclude_kw) and kk.seffaf:
            return kk.seffaf

    # iPhone
    if "iphone" in phone_lower and design_renk:
        kod = get_iphone_kalip_kodu(phone_model, design_renk, kk)
        if kod:
            return kod

    # Samsung
    if "samsung" in phone_lower or "galaxy" in phone_lower:
        if "ultra" in phone_lower:
            return kk.samsung_ultra or ""
        elif any(s in phone_lower for s in ["galaxy s", "samsung s"]):
            return kk.samsung_s or ""
        else:
            return kk.samsung_a or ""

    # Xiaomi grubu
    if "redmi" in phone_lower:
        return kk.redmi or ""
    elif "xiaomi" in phone_lower:
        return kk.xiaomi or ""

    # Diğer Çinli
    if any(m in phone_lower for m in ["vivo", "vıvo", "oppo", "realme", "tecno", "poco"]):
        return kk.diger_cin or ""

    return ""


def get_kalip_kodu_iphone_only(phone_model: str, design_name: str, design_renk: str,
                                kk: KalipKodlari, full_title: str = "") -> str:
    """Lunera/Casiva stratejisi — sadece iPhone."""
    phone_lower = (phone_model or "").lower()
    if "iphone" in phone_lower and design_renk:
        return get_iphone_kalip_kodu(phone_model, design_renk, kk) or ""
    return ""


# ─── Varyasyon (Illustrator header için) ───────────────────

def get_variation_for_code(kod: str, kk: KalipKodlari) -> str:
    """Kalıp kodundan varyasyon: SİYAH/BEYAZ/PARLAK/ŞEFFAF."""
    if not kod or not kk:
        return "SİYAH"
    beyaz_codes = [
        kk.iphone_11_beyaz, kk.iphone_13_beyaz, kk.iphone_15_beyaz,
        kk.iphone_13_pro_max_beyaz, kk.iphone_15_pro_beyaz,
        kk.iphone_15_pro_max_beyaz,
    ]
    if kod in beyaz_codes:
        return "BEYAZ"
    if kod == kk.parlak:
        return "PARLAK"
    if kod == kk.seffaf:
        return "ŞEFFAF"
    return "SİYAH"


def variation_header(variation: str) -> str:
    """Output header'a eklenecek son ek."""
    if variation == "BEYAZ":
        return " (B)"
    if variation == "PARLAK":
        return " (PARLAK)"
    if variation == "ŞEFFAF":
        return " (ŞEFFAF)"
    return ""


# ─── Model grup (bin-pack için satır hesabı) ───────────────

def get_model_group_simple(phone: str | None) -> str:
    """Telefon modelinden kompakt grup adı (satır hesabı için)."""
    if not phone:
        return "UNKNOWN"
    p = phone.lower()
    if "iphone" in p:
        if any(x in p for x in ["pro max", "promax"]):
            return "IPHONE-PROMAX"
        if "pro" in p:
            return "IPHONE-PRO"
        if "plus" in p:
            return "IPHONE-PLUS"
        m = re.search(r'(\d+)', p)
        if m:
            num = int(m.group(1))
            if num <= 12:
                return "IPHONE-11"
            elif num <= 14:
                return "IPHONE-13"
            else:
                return "IPHONE-15"
        return "IPHONE-OTHER"
    if "samsung" in p or "galaxy" in p:
        if "ultra" in p:
            return "SAMSUNG-ULTRA"
        if any(x in p for x in ["s2", "s3"]):
            return "SAMSUNG-S"
        if any(x in p for x in ["a1", "a2", "a3", "a5"]):
            return "SAMSUNG-A"
        return "SAMSUNG-OTHER"
    if "redmi" in p:
        return "REDMI"
    if "xiaomi" in p:
        return "XIAOMI"
    if "poco" in p:
        return "POCO"
    return "OTHER"
