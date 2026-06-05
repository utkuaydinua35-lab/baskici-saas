"""
Pipeline yardımcı fonksiyonları.

BERNZ'in siparis_common.py'sinden port edildi. Tenant-bağımsız saf utility'ler.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any


# Telefon markaları — line item property anahtarlarını eşleştirmek için
# (örn "iphone model", "samsung model" property'lerini bulmak için kullanılıyor).
# NOT: Burası kılıf markası değil, telefon markası!
BRAND_NAMES: tuple[str, ...] = (
    "iphone", "apple", "samsung", "galaxy", "xiaomi", "redmi",
    "poco", "huawei", "honor", "oppo", "realme", "vivo",
    "oneplus", "google", "pixel", "tecno", "infinix", "zte",
    "motorola", "nokia", "lg", "sony",
)


# ─── METİN NORMALIZE ────────────────────────────────────────

def normalize_text(text: str | None) -> str:
    """NFC normalize + combining dot temizle + smart quote → normal."""
    if not text:
        return ""
    result = unicodedata.normalize("NFC", text)
    result = result.replace("\u0307", "")  # combining dot above
    result = result.lower().strip()
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201C": '"', "\u201D": '"',
        "\u2014": "-", "\u2013": "-",
    }
    for old, new in replacements.items():
        result = result.replace(old, new)
    return re.sub(r"\s+", " ", result)


def clean_design_name(name: str | None) -> str:
    """Tasarım adının başındaki/sonundaki tırnakları temizle."""
    if not name:
        return name or ""
    name = name.strip()
    quotes = "'\"" + "\u2018\u2019\u201C\u201D"
    while name and name[0] in quotes:
        name = name[1:]
    while name and name[-1] in quotes:
        name = name[:-1]
    return name.strip()


def parse_order_numbers(input_str: str) -> list[str]:
    """'11078, 11082-11085, #11090' → ['11078', '11082'..'11085', '11090']"""
    order_numbers: list[str] = []
    for part in [p.strip() for p in (input_str or "").split(",")]:
        part = part.replace("#", "").strip()
        if "-" in part:
            try:
                s, e = part.split("-")
                s, e = int(s.strip()), int(e.strip())
                if s > e:
                    s, e = e, s
                order_numbers.extend(str(n) for n in range(s, e + 1))
            except ValueError:
                order_numbers.append(part)
        elif part:
            order_numbers.append(part)
    return order_numbers


# ─── KISAYOL UYGULAMA ────────────────────────────────────────

COUPLE_PREFIX = "COUPLE::"
VARIANT_PREFIX = "VARIANT::"


def apply_kisayol_full(
    design_name: str,
    kisayollar: dict[str, str],
    option_value: str = "",
    full_title: str = "",
) -> tuple[str, str] | tuple[str, list[tuple[str, str]]]:
    """BERNZ/505 — COUPLE + VARIANT + Normal hepsi."""
    if not kisayollar or not design_name:
        return design_name, ""

    nd = normalize_text(design_name)
    nt = normalize_text(full_title) if full_title else ""
    matched = kisayollar.get(nd) or (kisayollar.get(nt) if nt else None)

    if not matched:
        return design_name, ""

    upper = matched.upper()

    # COUPLE
    if upper.startswith(COUPLE_PREFIX):
        parts = matched.split("::")
        items: list[tuple[str, str]] = []
        for p in parts[1:]:
            if "|" in p:
                d, r = p.rsplit("|", 1)
                items.append((d.strip(), r.strip().lower()))
            else:
                items.append((p.strip(), ""))
        return "COUPLE", items

    # VARIANT
    if upper.startswith(VARIANT_PREFIX):
        parts = matched.split("::")
        opt = (option_value or "").lower()
        i = 1
        while i < len(parts) - 1:
            if parts[i].lower().strip() in opt:
                tr = parts[i + 1]
                if "|" in tr:
                    d, r = tr.rsplit("|", 1)
                    return d.strip(), r.strip().lower()
                return tr.strip(), ""
            i += 2
        # Eşleşmeyen varyant — ilk değeri al + işaretle
        if len(parts) >= 3:
            tr = parts[2]
            if "|" in tr:
                d, r = tr.rsplit("|", 1)
                return d.strip() + " (VARYANT BELİRSİZ)", r.strip().lower()
            return tr.strip() + " (VARYANT BELİRSİZ)", ""

    # Normal
    if "|" in matched:
        p = matched.rsplit("|", 1)
        return p[0].strip(), p[1].strip().lower() if len(p) > 1 else ""
    return matched, ""


def apply_kisayol_simple(
    design_name: str,
    kisayollar: dict[str, str],
) -> tuple[str, str]:
    """Lunera/Casiva — sadece 'tasarım|renk'."""
    if not kisayollar or not design_name:
        return design_name, ""
    nd = normalize_text(design_name)
    matched = kisayollar.get(nd)
    if not matched:
        return design_name, ""
    if "|" in matched:
        p = matched.rsplit("|", 1)
        return p[0].strip(), p[1].strip().lower() if len(p) > 1 else ""
    return matched, ""


# ─── LINE ITEM YARDIMCILARI ──────────────────────────────────

def extract_phone_model_from_properties(item: dict) -> str | None:
    """BERNZ/505 — Properties'den telefon modeli."""
    props = item.get("properties", []) or []

    # 1. "{phone_brand} model" pattern (örn "iphone model", "samsung model")
    for prop in props:
        pn = (prop.get("name") or "").lower().strip()
        pv = prop.get("value") or ""
        for brand in BRAND_NAMES:
            if f"{brand} model" in pn:
                return pv

    # 2. Direkt marka key'i (telefon markası)
    for prop in props:
        pn = (prop.get("name") or "").lower().strip()
        pv = prop.get("value") or ""
        if pn.startswith("_"):
            continue
        if pn in BRAND_NAMES and pv and len(pv) > 2:
            return pv

    # 3. Genel "model" key
    for prop in props:
        pn = (prop.get("name") or "").lower().strip()
        pv = prop.get("value") or ""
        if pn.startswith("_"):
            continue
        if any(s in pn for s in ["cihaz modeli", "device model", "marka", "brand"]):
            continue
        if "model" in pn and "copy" not in pn:
            return pv
    return None


def extract_phone_model_lunera(item: dict) -> str | None:
    """Lunera — variant_title öncelikli."""
    vt = item.get("variant_title")
    if vt:
        return vt

    name = item.get("name") or item.get("title") or ""
    if " - " in name:
        last = name.rsplit(" - ", 1)[-1]
        keywords = [
            "iphone", "samsung", "galaxy", "xiaomi", "redmi", "huawei",
            "oppo", "realme", "poco", "oneplus", "honor", "vivo", "pixel",
        ]
        if any(kw in last.lower() for kw in keywords):
            return last

    return extract_phone_model_from_properties(item)


def extract_option_value(item: dict) -> str:
    """BERNZ/505 — Properties'den opsiyon değeri (renk/varyant)."""
    keywords = [
        "seçim", "secim", "renk", "color", "colour",
        "kılıf rengi", "kilif rengi",
        "opsiyon", "option", "variant", "varyant",
    ]
    for prop in item.get("properties", []) or []:
        pn = (prop.get("name") or "").lower().strip()
        if pn.startswith("_"):
            continue
        if any(kw in pn for kw in keywords):
            return prop.get("value") or ""
    return ""


def extract_phone_models_couple(item: dict) -> tuple[str | None, str | None]:
    """Couple ürünler için iki telefon modeli."""
    m1, m2 = None, None
    for prop in item.get("properties", []) or []:
        pn = (prop.get("name") or "").lower().strip()
        pv = prop.get("value") or ""
        if not pv or pn.startswith("_"):
            continue
        for brand in BRAND_NAMES:
            if f"{brand} model" in pn:
                if "copy" not in pn:
                    m1 = pv
                else:
                    m2 = pv
    return m1, m2


def extract_design_name_from_title(item: dict) -> str:
    """BERNZ/505 — Title'dan tırnak içindeki tasarım adı."""
    title = item.get("title") or ""
    quote_patterns = [
        r"\u2018([^\u2019]+)\u2019",
        r"'([^']+)'",
        r"\u201C([^\u201D]+)\u201D",
        r'"([^"]+)"',
    ]
    for pattern in quote_patterns:
        m = re.search(pattern, title)
        if m:
            return m.group(1)
    return clean_design_name(title)


def extract_design_name_lunera(item: dict) -> str | None:
    """Lunera — properties öncelikli tasarım adı."""
    keywords = ["tasarım", "tasarim", "design", "desen", "model adı", "model adi"]
    for prop in item.get("properties", []) or []:
        pn = (prop.get("name") or "").lower().strip()
        if pn.startswith("_"):
            continue
        if any(kw in pn for kw in keywords):
            return clean_design_name(prop.get("value") or "")
    return item.get("title") or None


# ─── ORDER YARDIMCILARI ──────────────────────────────────────

def get_shipping_method_yurtici(order: dict) -> bool:
    """Yurtiçi kargo mu?"""
    for s in order.get("shipping_lines", []) or []:
        t = (s.get("title") or "").lower()
        if "yurtiçi" in t or "yurtici" in t:
            return True
    return False


def get_order_date_short(order: dict) -> str:
    """ISO timestamp → 'dd.mm'."""
    ca = order.get("created_at") or ""
    if ca:
        try:
            return datetime.fromisoformat(ca.replace("Z", "+00:00")).strftime("%d.%m")
        except (ValueError, AttributeError):
            pass
    return "Tarihsiz"


def get_customer_name_upper(order: dict) -> str:
    """Müşteri adı UPPERCASE."""
    customer = order.get("customer") or {}
    if customer:
        name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip().upper()
        if name:
            return name
    s = order.get("shipping_address") or {}
    name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip().upper()
    return name or "İSİM YOK"


def get_customer_name_lower(order: dict) -> str:
    """Müşteri adı lowercase."""
    sources = [
        order.get("shipping_address") or {},
        order.get("customer") or {},
        order.get("billing_address") or {},
    ]
    for source in sources:
        if not source:
            continue
        name = (
            source.get("name")
            or f"{source.get('first_name', '')} {source.get('last_name', '')}".strip()
        )
        if name:
            return name.lower()
    return "?"


# ─── KISAYOL JSON IMPORT ─────────────────────────────────────

def clean_kisayollar_dict(raw: dict[str, Any]) -> dict[str, str]:
    """JSON'ı temizle — _ prefixleri at, normalize et."""
    clean: dict[str, str] = {}
    for k, v in (raw or {}).items():
        if k.startswith("_") or not v:
            continue
        nk = normalize_text(k)
        if not nk:
            continue
        if isinstance(v, str):
            v = v.replace("\u0307", "")
        clean[nk] = v
    return clean
