"""
placement_rules — kalıp grup/kod sistemi (script v5 ile birebir).

12 iPhone grubu + ince android markaları + baskı-sırası priority.
DB'den bağımsız, saf fonksiyonlar.

Dışa açık API (mold_planner vb. tarafından kullanılır, KORUNDU):
  KALIP_MAX_BOXES, KALIP_COLS, KALIP_ROWS, VARIATIONS,
  KalipKodlari, DEFAULT_KODLARI,
  normalize_variation, resolve_kalip_kodu, kod_to_group_priority,
  bin_pack_by_variation, _count_rows, _can_merge, _do_merge

Yeni eklenenler:
  get_model_group, group_priority, is_android_group, effective_variation,
  GROUP_PRIORITY, GROUP_DISPLAY_NAMES, IPHONE_GROUPS, ANDROID_GROUPS
"""
import re
import unicodedata

KALIP_MAX_BOXES = 27
KALIP_COLS = 9
KALIP_ROWS = 3
VARIATIONS = ("SİYAH", "BEYAZ", "ŞEFFAF", "PARLAK", "MAGSAFE")

# ═══════════════════════════════════════════════════════════
# GRUP SİSTEMİ (script v5 birebir)
# ═══════════════════════════════════════════════════════════

IPHONE_GROUPS = {
    "IPHONE-11-GROUP": ["6", "6S", "6S-PLUS", "6-PLUS", "7", "7-PLUS", "8", "8-PLUS",
                        "X", "XS", "XS-MAX", "XR", "11", "11-PRO", "11-PROMAX",
                        "12", "12-PRO", "12-MINI", "13-MINI",
                        "SE", "SE-2", "SE-2020", "SE-2022", "SE-3"],
    "IPHONE-13-GROUP": ["13", "14", "16E"],
    "IPHONE-15-GROUP": ["15", "16", "17"],
    "IPHONE-13-PROMAX-GROUP": ["12-PROMAX", "13-PRO", "13-PROMAX"],
    "IPHONE-14-PLUS-GROUP": ["14-PLUS", "15-PLUS"],
    "IPHONE-16-PLUS-GROUP": ["16-PLUS"],
    "IPHONE-15-PRO-GROUP": ["14-PRO", "15-PRO"],
    "IPHONE-16-PRO-GROUP": ["16-PRO"],
    "IPHONE-17-PRO-GROUP": ["17-PRO"],
    "IPHONE-15-PROMAX-GROUP": ["14-PROMAX", "15-PROMAX"],
    "IPHONE-16-PROMAX-GROUP": ["16-PROMAX"],
    "IPHONE-17-PROMAX-GROUP": ["17-PROMAX"],
}

GROUP_PRIORITY = {
    "IPHONE-11-GROUP": 1, "IPHONE-13-GROUP": 2, "IPHONE-15-GROUP": 3,
    "IPHONE-13-PROMAX-GROUP": 4, "IPHONE-14-PLUS-GROUP": 5, "IPHONE-16-PLUS-GROUP": 6,
    "IPHONE-15-PRO-GROUP": 7, "IPHONE-16-PRO-GROUP": 8, "IPHONE-17-PRO-GROUP": 9,
    "IPHONE-15-PROMAX-GROUP": 10, "IPHONE-16-PROMAX-GROUP": 11, "IPHONE-17-PROMAX-GROUP": 12,
    "SAMSUNG-A-GROUP": 100, "SAMSUNG-S-GROUP": 101, "SAMSUNG-ULTRA-GROUP": 102,
    "SAMSUNG-M-GROUP": 103, "SAMSUNG-OTHER-GROUP": 104,
    "REDMI-GROUP": 110, "XIAOMI-GROUP": 111, "POCO-GROUP": 112, "OPPO-GROUP": 113,
    "VIVO-GROUP": 114, "REALME-GROUP": 115, "TECNO-GROUP": 116,
    "HUAWEI-GROUP": 117, "OMIX-GROUP": 118,
    "IPHONE-UNKNOWN": 50, "UNKNOWN-GROUP": 999,
    # ozel varyasyonlar (markadan bagimsiz tek kalip) — siralamada sona yakin
    "SEFFAF": 200, "PARLAK": 201, "MAGSAFE": 202,
}

GROUP_DISPLAY_NAMES = {
    "IPHONE-11-GROUP": "iPhone 11 Grubu", "IPHONE-13-GROUP": "iPhone 13 Grubu",
    "IPHONE-15-GROUP": "iPhone 15 Grubu", "IPHONE-13-PROMAX-GROUP": "iPhone 13 Pro Max",
    "IPHONE-14-PLUS-GROUP": "iPhone 14 Plus", "IPHONE-16-PLUS-GROUP": "iPhone 16 Plus",
    "IPHONE-15-PRO-GROUP": "iPhone 15 Pro", "IPHONE-16-PRO-GROUP": "iPhone 16 Pro",
    "IPHONE-17-PRO-GROUP": "iPhone 17 Pro", "IPHONE-15-PROMAX-GROUP": "iPhone 15 Pro Max",
    "IPHONE-16-PROMAX-GROUP": "iPhone 16 Pro Max", "IPHONE-17-PROMAX-GROUP": "iPhone 17 Pro Max",
    "SAMSUNG-A-GROUP": "Samsung A", "SAMSUNG-S-GROUP": "Samsung S",
    "SAMSUNG-ULTRA-GROUP": "Samsung Ultra", "SAMSUNG-M-GROUP": "Samsung M",
    "SAMSUNG-OTHER-GROUP": "Samsung", "REDMI-GROUP": "Redmi", "XIAOMI-GROUP": "Xiaomi",
    "POCO-GROUP": "Poco", "OPPO-GROUP": "Oppo", "VIVO-GROUP": "Vivo", "REALME-GROUP": "Realme",
    "TECNO-GROUP": "Tecno", "HUAWEI-GROUP": "Huawei", "OMIX-GROUP": "Omix",
    "IPHONE-UNKNOWN": "iPhone (?)", "UNKNOWN-GROUP": "Bilinmeyen",
    "SEFFAF": "Şeffaf", "PARLAK": "Parlak", "MAGSAFE": "MagSafe",
}

ANDROID_GROUPS = {
    "SAMSUNG-A-GROUP", "SAMSUNG-S-GROUP", "SAMSUNG-ULTRA-GROUP", "SAMSUNG-M-GROUP",
    "SAMSUNG-OTHER-GROUP", "REDMI-GROUP", "XIAOMI-GROUP", "POCO-GROUP", "OPPO-GROUP",
    "VIVO-GROUP", "REALME-GROUP", "TECNO-GROUP", "HUAWEI-GROUP", "OMIX-GROUP",
}


def _norm_key(phone_model: str) -> str:
    if not phone_model:
        return ""
    s = unicodedata.normalize("NFC", phone_model).upper().strip()
    s = s.replace("APPLE", "").strip()
    s = re.sub(r"I\s*PHONE\s*", "IPHONE ", s)
    s = re.sub(r"GALAXY", "SAMSUNG", s)
    s = s.replace("PRO MAX", "PROMAX")
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s


def extract_iphone_model_number(model_key: str) -> str | None:
    m = re.match(r"IPHONE-(.+)", model_key)
    if m:
        return m.group(1)
    if re.match(r"^\d", model_key):
        return model_key
    return None


def get_model_group(phone_model: str) -> str:
    """Model -> grup (script v5 getModelGroup birebir)."""
    mk = _norm_key(phone_model)
    if not mk:
        return "UNKNOWN-GROUP"
    if mk.startswith("IPHONE") or re.match(r"^\d", mk):
        iphone_model = extract_iphone_model_number(mk)
        if not iphone_model and re.match(r"^\d", mk):
            iphone_model = mk
        if iphone_model:
            for group_name, models in IPHONE_GROUPS.items():
                if iphone_model in models:
                    return group_name
        return "IPHONE-UNKNOWN"
    if mk.startswith("SAMSUNG") or re.match(r"^S[12]\d", mk):
        if "ULTRA" in mk:
            return "SAMSUNG-ULTRA-GROUP"
        if re.match(r"^S\d", mk) or re.search(r"SAMSUNG-S\d", mk):
            return "SAMSUNG-S-GROUP"
        if re.match(r"^A\d", mk) or re.search(r"SAMSUNG-A\d", mk):
            return "SAMSUNG-A-GROUP"
        if re.match(r"^M\d", mk) or re.search(r"SAMSUNG-M\d", mk):
            return "SAMSUNG-M-GROUP"
        return "SAMSUNG-OTHER-GROUP"
    for brand, grp in [("REDMI", "REDMI-GROUP"), ("XIAOMI", "XIAOMI-GROUP"),
                       ("POCO", "POCO-GROUP"), ("OPPO", "OPPO-GROUP"),
                       ("VIVO", "VIVO-GROUP"), ("REALME", "REALME-GROUP"),
                       ("TECNO", "TECNO-GROUP"), ("HUAWEI", "HUAWEI-GROUP"),
                       ("OMIX", "OMIX-GROUP")]:
        if brand in mk:
            return grp
    return "UNKNOWN-GROUP"


def group_priority(group: str) -> int:
    return GROUP_PRIORITY.get(group, 999)


def is_android_group(group: str) -> bool:
    return group in ANDROID_GROUPS


# ═══════════════════════════════════════════════════════════
# VARYASYON NORMALİZE (korundu)
# ═══════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    if not text:
        return ""
    result = unicodedata.normalize("NFC", text)
    result = result.replace("\u0307", "")
    return result


def normalize_variation(kalip_tipi: str | None) -> str:
    if not kalip_tipi:
        return "SİYAH"
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


def effective_variation(group: str, variation: str) -> str:
    """Android + BEYAZ -> SİYAH (android'de beyaz kılıf yok)."""
    v = (variation or "SİYAH").upper()
    if v == "BEYAZ" and is_android_group(group):
        return "SİYAH"
    return v


# ═══════════════════════════════════════════════════════════
# KALIP KODU (yeni format: "GRUP|RENK" — ör IPHONE-15-GROUP|SIYAH)
# ═══════════════════════════════════════════════════════════

# Geriye-uyum: eski kod kullanan yerler icin KalipKodlari sinifi korunur (no-op).
class KalipKodlari:
    """Geriye-uyumluluk için korundu. Yeni sistemde kod = 'GRUP|RENK'."""
    def __init__(self, h1="A", h2="B", h3="C"):
        self.h1, self.h2, self.h3 = h1, h2, h3


DEFAULT_KODLARI = KalipKodlari()


def resolve_kalip_kodu(phone_model: str, variation: str, k: KalipKodlari = DEFAULT_KODLARI) -> str:
    """
    Telefon modeli + varyasyon -> kalıp kodu.
    Yeni format: "GRUP|RENK" (ör. "IPHONE-15-GROUP|SIYAH").
    Özel varyasyonlar (PARLAK/ŞEFFAF/MAGSAFE) markadan bağımsız tek kalıp.
    Android + BEYAZ -> SİYAH. Boş string = model tanınamadı.
    """
    v = (variation or "SİYAH").upper()
    if v == "PARLAK":
        return "PARLAK"
    if v == "ŞEFFAF":
        return "SEFFAF"
    if v == "MAGSAFE":
        return "MAGSAFE"
    group = get_model_group(phone_model)
    if group == "UNKNOWN-GROUP" or group == "IPHONE-UNKNOWN":
        return ""
    eff_v = effective_variation(group, v)
    renk = "BEYAZ" if eff_v == "BEYAZ" else "SIYAH"
    if group.startswith("IPHONE"):
        return f"{group}|{renk}"
    # android: tek renk (siyah)
    return f"{group}|SIYAH"


def _kod_group(kod: str) -> str:
    """Kalıp kodundan grup adını çıkar ('IPHONE-15-GROUP|SIYAH' -> 'IPHONE-15-GROUP')."""
    if not kod:
        return "UNKNOWN-GROUP"
    if kod in ("PARLAK", "SEFFAF", "MAGSAFE"):
        return kod
    return kod.split("|", 1)[0]


def kod_to_group_priority(kod: str, k: KalipKodlari = DEFAULT_KODLARI) -> int:
    """Kalıp kodunun baskı-sırası önceliği (küçük = önce/alt satır)."""
    return group_priority(_kod_group(kod))


# ═══════════════════════════════════════════════════════════
# BİN-PACKING (korundu — imza aynı)
# ═══════════════════════════════════════════════════════════

def _count_rows(items: list[dict]) -> int:
    group_counts: dict[str, int] = {}
    for it in items:
        kod = it.get("kod", "UNKNOWN")
        group_counts[kod] = group_counts.get(kod, 0) + 1
    total = 0
    for count in group_counts.values():
        total += -(-count // KALIP_COLS)
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
    out = []
    for v in VARIATIONS:
        vq = [k for k in queue if k["variation"] == v]
        out.extend(bin_pack(vq))
    out.extend([k for k in queue if k["variation"] not in VARIATIONS])
    return out


# ═══════════════════════════════════════════════════════════
# SLOT YERLEŞİMİ (grid 1-27; 1=alt-sağ, 27=üst-sol)
# ═══════════════════════════════════════════════════════════
# Grid:
#   27 26 25 24 23 22 21 20 19   <- ust satir (en yuksek priority)
#   18 17 16 15 14 13 12 11 10   <- orta satir
#    9  8  7  6  5  4  3  2  1    <- alt satir (en dusuk priority)

def _row_slots(row_idx: int) -> list[int]:
    base = row_idx * KALIP_COLS
    return [base + i + 1 for i in range(KALIP_COLS)]


def assign_slots(items: list[dict]) -> list[dict]:
    """Kalıp içi item'lara grid slot no ata (priority düşük=alt satır, yüksek=üst).
    Her item'a 'slot_no' (1-27) ve 'slot_index' (0-26) ekler. Sıralı liste döner."""
    if not items:
        return items
    by_kod: dict[str, list[dict]] = {}
    for it in items:
        by_kod.setdefault(it.get("kod", "UNKNOWN"), []).append(it)
    sorted_kods = sorted(by_kod.keys(), key=kod_to_group_priority)
    out = []
    row_cursor = 0
    for kod in sorted_kods:
        grp_items = by_kod[kod]
        n = len(grp_items)
        rows_needed = -(-n // KALIP_COLS)
        for r in range(rows_needed):
            if row_cursor >= KALIP_ROWS:
                break
            chunk = grp_items[r * KALIP_COLS:(r + 1) * KALIP_COLS]
            slots = _row_slots(row_cursor)
            for i, it in enumerate(chunk):
                it["slot_no"] = slots[i]
                it["slot_index"] = slots[i] - 1
                out.append(it)
            row_cursor += 1
    return out
