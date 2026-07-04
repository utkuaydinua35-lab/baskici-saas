"""
Telefon markası çıkarımı — model adından (display name) marka tahmini.

PhoneModel.brand doluysa o kazanır; boşsa/bulunamazsa bu çıkarım kullanılır
(vitrin marka→model seçicisi ve CSV import için).
"""
from __future__ import annotations

# Sıra önemli: daha spesifik önekler önce (örn. "Galaxy" Samsung'a gider)
_PREFIXES: list[tuple[str, str]] = [
    ("iphone", "Apple"),
    ("ipad", "Apple"),
    ("samsung", "Samsung"),
    ("galaxy", "Samsung"),
    ("xiaomi", "Xiaomi"),
    ("redmi", "Xiaomi"),
    ("poco", "Xiaomi"),
    ("mi ", "Xiaomi"),
    ("huawei", "Huawei"),
    ("honor", "Honor"),
    ("oppo", "Oppo"),
    ("reno", "Oppo"),
    ("vivo", "Vivo"),
    ("realme", "Realme"),
    ("oneplus", "OnePlus"),
    ("one plus", "OnePlus"),
    ("google", "Google"),
    ("pixel", "Google"),
    ("tecno", "Tecno"),
    ("infinix", "Infinix"),
    ("nokia", "Nokia"),
    ("motorola", "Motorola"),
    ("moto ", "Motorola"),
    ("casper", "Casper"),
    ("reeder", "Reeder"),
    ("general mobile", "General Mobile"),
    ("gm ", "General Mobile"),
]


def infer_brand(model_display: str | None) -> str | None:
    """'iPhone 15 Pro' → 'Apple'. Eşleşme yoksa None ("Diğer" grubunda kalır)."""
    text = (model_display or "").strip().lower()
    if not text:
        return None
    for prefix, brand in _PREFIXES:
        if text.startswith(prefix) or f" {prefix}" in f" {text}":
            return brand
    return None
