"""
Kalıp yerleştirme kural motoru — BERNZ production mantığının birebir kopyası.

DB'den bağımsız, saf fonksiyonlar. Girdi: ürün model adı + varyasyon (kalıp tipi).
Çıktı: kalıp kodu (boyut grubu kimliği) + bin-packing ile optimize edilmiş kalıp listesi.

Kaynak: bernz-web/pipeline.py + siparis_common.py + config.py (IPHONE_GROUPS).
"""
from __future__ import annotations

import re
import unicodedata

# ═══════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════

KALIP_MAX_BOXES = 27   # bir kalıba sığan toplam kılıf
KALIP_COLS = 9         # sütun (her satır en fazla 9 aynı-grup kılıf)
KALIP_ROWS = 3         # satır (bir kalıpta en fazla 3 farklı boyut grubu)

VARIATIONS = ("SİYAH", "BEYAZ", "ŞEFFAF", "PARLAK", "MAGSAFE")

# Hangi iPhone modeli hangi boyut grubuna ait (config.py'den birebir)
IPHONE_GROUPS = {
    "11": ["6", "6s", "6s plus", "6 plus", "7", "7 plus", "8", "8 plus",
           "x", "xs", "xs max", "xr", "11", "11 pro", "11 pro max",
           "12", "12 pro", "12 mini", "13 mini",
           "se", "se 2", "se 2020", "se 2022", "se 3"],
    "13": ["13", "14", "16e"],
    "15": ["15", "16", "17"],
    "13_pro_max": ["12 pro max", "13 pro", "13 pro max",
                   "14 plus", "15 plus", "16 plus"],
    "15_pro": ["14 pro", "15 pro", "16 pro", "17 pro"],
    "15_pro_max": ["14 pro max", "15 pro max", "16 pro max", "17 pro max"],
}

# Boyut grubu öncelik sırası (gruplar bu sırada sıralanır / kontrol edilir)
GROUP_PRIORITY = [
    "11", "13", "15", "13_pro_max", "15_pro", "15_pro_max",
    "SEFFAF", "PARLAK", "REDMI", "XIAOMI", "SAMSUNG_A", "SAMSUNG_S",
    "SAMSUNG_ULTRA", "DIGER_CIN", "MAGSAFE", "UNKNOWN",
]


# ═══════════════════════════════════════════════════════════
# KALIP KODU SİSTEMİ (3-harf, örn A/B/C)
# ═══════════════════════════════════════════════════════════

class KalipKodlari:
    """3-harf kod sistemi: telefon grubu+renk -> kod (A1, A7, B4...)."""
    def __init__(self, h1="A", h2="B", h3="C"):
        self.iphone_11_siyah = f"{h1}1"
        self.iphone_11_beyaz = f"{h1}2"
        self.iphone_13_siyah = f"{h1}3"
        self.iphone_13_beyaz = f"{h1}4"
        self.iphone_15_siyah = f"{h1}5"
        self.iphone_15_beyaz = f"{h1}6"
        self.iphone_13_pro_max_siyah = f"{h1}7"
        self.iphone_13_pro_max_beyaz = f"{h1}8"
        self.iphone_15_pro_siyah = f"{h1}9"
        self.iphone_15_pro_beyaz = f"{h2}1"
        self.iphone_15_pro_max_siyah = f"{h2}2"
        self.iphone_15_pro_max_beyaz = f"{h2}3"
        self.seffaf = f"{h2}4"
        self.parlak = f"{h2}5"
        self.redmi = f"{h2}6"
        self.xiaomi = f"{h2}7"
        self.samsung_a = f"{h2}8"
        self.samsung_s = f"{h2}9"
        self.samsung_ultra = f"{h3}1"
        self.diger_cin = f"{h3}2"
        self.magsafe = f"{h3}3"  # baskıcı eklemesi (BERNZ'de ayrı kod yoktu)


DEFAULT_KODLARI = KalipKodlari()


# ═══════════════════════════════════════════════════════════
# MODEL NORMALİZE + GRUP
# ═══════════════════════════════════════════════════════════

def normalize_iphone_model(phone_model: str) -> str:
    if not phone_model:
        return ""
    model = phone_model.lower()
    model = re.sub(r'i\s*phone\s*', '', model)
    model = model.replace("apple", "").strip()
    model = model.replace("-", " ").replace("_", " ")
    return re.sub(r'\s+', ' ', model).strip()


def get_iphone_group(phone_model: str) -> str | None:
    """iPhone modelini boyut grubuna çevir (11 / 13 / 15 / 13_pro_max / 15_pro / 15_pro_max)."""
    normalized = normalize_iphone_model(phone_model)
    if not normalized:
        return None
    # En spesifik önce (pro max -> pro -> düz numara)
    for group_name in ["15_pro_max", "13_pro_max", "15_pro", "15", "13", "11"]:
        for model in IPHONE_GROUPS.get(group_name, []):
            if model == normalized or normalized.startswith(model + " ") or f" {model} " in f" {normalized} ":
                return group_name
    return None


# ═══════════════════════════════════════════════════════════
# RENK / VARYASYON NORMALİZE
# ═══════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    if not text:
        return ""
    result = unicodedata.normalize("NFC", text)
    result = result.replace("\u0307", "")  # combining dot (si̇yah -> siyah)
    return result


def normalize_variation(kalip_tipi: str | None) -> str:
    """Design.kalip_tipi -> standart varyasyon (SİYAH/BEYAZ/ŞEFFAF/PARLAK/MAGSAFE)."""
    if not kalip_tipi:
        return "SİYAH"  # varsayılan
    t = normalize_text(kalip_tipi).upper().strip()
    if "BEYAZ" in t or "WHITE" in t:
        return "BEYAZ"
    if "ŞEFFAF" in t or "SEFFAF" in t or "CLEAR" in t or "TRANSPARAN" in t:
        return "ŞEFFAF"
    if "PARLAK" in t or "GLITTER" in t or "SİMLİ" in t or "SIMLI" in t:
        return "PARLAK"
    if "MAGSAFE" in t or "MAG SAFE" in t:
        return "MAGSAFE"
    return "SİYAH"


# ═══════════════════════════════════════════════════════════
# KALIP KODU EŞLEŞMESİ
# ═══════════════════════════════════════════════════════════

def get_iphone_kalip_kodu(phone_model: str, renk: str, k: KalipKodlari) -> str:
    group = get_iphone_group(phone_model)
    if not group or not renk:
        return ""
    renk_lower = renk.lower().strip()
    kalip_map = {
        ("11", "siyah"): k.iphone_11_siyah, ("11", "beyaz"): k.iphone_11_beyaz,
        ("13", "siyah"): k.iphone_13_siyah, ("13", "beyaz"): k.iphone_13_beyaz,
        ("15", "siyah"): k.iphone_15_siyah, ("15", "beyaz"): k.iphone_15_beyaz,
        ("13_pro_max", "siyah"): k.iphone_13_pro_max_siyah,
        ("13_pro_max", "beyaz"): k.iphone_13_pro_max_beyaz,
        ("15_pro", "siyah"): k.iphone_15_pro_siyah,
        ("15_pro", "beyaz"): k.iphone_15_pro_beyaz,
        ("15_pro_max", "siyah"): k.iphone_15_pro_max_siyah,
        ("15_pro_max", "beyaz"): k.iphone_15_pro_max_beyaz,
    }
    # renk siyah/beyaz değilse (ör. şeffaf iPhone) siyah kalıbına düş
    if renk_lower not in ("siyah", "beyaz"):
        renk_lower = "siyah"
    return kalip_map.get((group, renk_lower), "")


def resolve_kalip_kodu(phone_model: str, variation: str, k: KalipKodlari = DEFAULT_KODLARI) -> str:
    """
    Telefon modeli + varyasyon -> kalıp kodu (boyut grubu kimliği).
    variation: normalize edilmiş (SİYAH/BEYAZ/ŞEFFAF/PARLAK/MAGSAFE).
    Boş string dönerse model tanınamadı (kod atanamaz).
    """
    phone_lower = (phone_model or "").lower()
    v = (variation or "SİYAH").upper()

    # Özel varyasyonlar markadan bağımsız tek kalıba gider
    if v == "PARLAK":
        return k.parlak
    if v == "ŞEFFAF":
        return k.seffaf
    if v == "MAGSAFE":
        return k.magsafe

    # iPhone: grup + renk (siyah/beyaz)
    if "iphone" in phone_lower:
        renk = "beyaz" if v == "BEYAZ" else "siyah"
        kod = get_iphone_kalip_kodu(phone_model, renk, k)
        if kod:
            return kod

    # Samsung
    if "samsung" in phone_lower or "galaxy" in phone_lower:
        if "ultra" in phone_lower:
            return k.samsung_ultra
        if "galaxy s" in phone_lower or "samsung s" in phone_lower or re.search(r'\bs\d', phone_lower):
            return k.samsung_s
        return k.samsung_a

    # Xiaomi ailesi
    if "redmi" in phone_lower:
        return k.redmi
    if "xiaomi" in phone_lower or "poco" in phone_lower:
        return k.xiaomi

    # Diğer Çin markaları
    if any(m in phone_lower for m in ["vivo", "vıvo", "oppo", "realme", "tecno", "honor", "huawei", "omix"]):
        return k.diger_cin

    return ""


def kod_to_group_priority(kod: str, k: KalipKodlari = DEFAULT_KODLARI) -> int:
    """Kalıp kodunun sıralama önceliği (küçük = önce). Kod -> grup adı -> GROUP_PRIORITY index."""
    rev = {
        k.iphone_11_siyah: "11", k.iphone_11_beyaz: "11",
        k.iphone_13_siyah: "13", k.iphone_13_beyaz: "13",
        k.iphone_15_siyah: "15", k.iphone_15_beyaz: "15",
        k.iphone_13_pro_max_siyah: "13_pro_max", k.iphone_13_pro_max_beyaz: "13_pro_max",
        k.iphone_15_pro_siyah: "15_pro", k.iphone_15_pro_beyaz: "15_pro",
        k.iphone_15_pro_max_siyah: "15_pro_max", k.iphone_15_pro_max_beyaz: "15_pro_max",
        k.seffaf: "SEFFAF", k.parlak: "PARLAK", k.redmi: "REDMI", k.xiaomi: "XIAOMI",
        k.samsung_a: "SAMSUNG_A", k.samsung_s: "SAMSUNG_S",
        k.samsung_ultra: "SAMSUNG_ULTRA", k.diger_cin: "DIGER_CIN", k.magsafe: "MAGSAFE",
    }
    grp = rev.get(kod, "UNKNOWN")
    try:
        return GROUP_PRIORITY.index(grp)
    except ValueError:
        return len(GROUP_PRIORITY)


# ═══════════════════════════════════════════════════════════
# BİN-PACKING (kalıpları optimize et)
# ═══════════════════════════════════════════════════════════

def _count_rows(items: list[dict]) -> int:
    """Item listesinin kaç satır kaplayacağı (her kalıp kodu/grup ayrı satır(lar))."""
    group_counts: dict[str, int] = {}
    for it in items:
        kod = it.get("kod", "UNKNOWN")
        group_counts[kod] = group_counts.get(kod, 0) + 1
    total = 0
    for count in group_counts.values():
        total += -(-count // KALIP_COLS)  # ceil(count/9)
    return total


def _can_merge(a: dict, b: dict) -> bool:
    if a["variation"] != b["variation"]:
        return False
    if a["count"] + b["count"] > KALIP_MAX_BOXES:
        return False
    if _count_rows(a["items"] + b["items"]) > KALIP_ROWS:
        return False
    return True


def _do_merge(a: dict, b: dict) -> None:
    a["items"].extend(b["items"])
    a["count"] = len(a["items"])
    a["kodlar"] = sorted(set(a["kodlar"]) | set(b["kodlar"]))
    a["is_merged"] = True


def bin_pack(queue: list[dict]) -> list[dict]:
    """First-Fit-Decreasing: aynı varyasyondaki kalıpları 27/3-satır limitine kadar birleştir."""
    if len(queue) <= 1:
        return queue
    queue = sorted(queue, key=lambda x: x["count"], reverse=True)
    bins: list[dict] = []
    for item in queue:
        placed = False
        for b in bins:
            if _can_merge(b, item):
                _do_merge(b, item)
                placed = True
                break
        if not placed:
            bins.append({
                "items": list(item["items"]),
                "count": item["count"],
                "variation": item["variation"],
                "kodlar": list(item["kodlar"]),
                "is_merged": False,
            })
    return bins


def bin_pack_by_variation(queue: list[dict]) -> list[dict]:
    """Varyasyona göre ayır, her varyasyonu ayrı bin-pack et (farklı varyasyon birleşmez)."""
    out = []
    for v in VARIATIONS:
        vq = [k for k in queue if k["variation"] == v]
        out.extend(bin_pack(vq))
    # bilinmeyen varyasyonlar
    out.extend([k for k in queue if k["variation"] not in VARIATIONS])
    return out
