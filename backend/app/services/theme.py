"""
Vitrin tema şeması — Store.config["theme"] (version 1).

Panel PUT ile yazar, vitrin public endpoint'ten okur; defaults ile derin
birleştirilir (eksik alanlar her zaman dolu döner → vitrin null kontrolü yapmaz).
"""
from __future__ import annotations

import copy

DEFAULT_THEME: dict = {
    "version": 1,
    "colors": {
        "primary": "#18181b",   # buton/vurgu (zinc-900)
        "accent": "#f59e0b",    # ikincil vurgu (amber-500)
        "bg": "#fafafa",        # sayfa zemini
    },
    "font": "inter",            # inter | poppins | playfair | dm-sans
    "logo_url": None,
    "favicon_url": None,
    "announcement": {"enabled": False, "text": "", "url": ""},
    "hero": {
        "enabled": False,
        "image": None,
        "title": "",
        "subtitle": "",
        "cta_text": "Tasarımları Keşfet",
        "cta_url": "/urunler",
    },
    "featured_collections": [],       # koleksiyon slug listesi
    "sections_order": ["hero", "featured", "products"],
    "animations": {"reveal": True, "hover_zoom": True, "cart_drawer": True},
    "footer": {"about": "", "instagram": ""},
}

FONT_PRESETS = {"inter", "poppins", "playfair", "dm-sans"}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve_theme(store_config: dict | None) -> dict:
    """Config'teki tema + defaults → tam tema (her alan dolu)."""
    theme = _deep_merge(DEFAULT_THEME, (store_config or {}).get("theme") or {})
    if theme.get("font") not in FONT_PRESETS:
        theme["font"] = DEFAULT_THEME["font"]
    return theme


def validate_theme_patch(patch: dict) -> dict:
    """Panelden gelen temayı temizle: yalnızca bilinen anahtarlar, tip kaba kontrolü."""
    cleaned: dict = {}
    for key in DEFAULT_THEME:
        if key not in patch:
            continue
        value = patch[key]
        default = DEFAULT_THEME[key]
        if isinstance(default, dict):
            if isinstance(value, dict):
                cleaned[key] = {k: v for k, v in value.items() if k in default}
        elif key == "sections_order":
            if isinstance(value, list):
                cleaned[key] = [s for s in value if s in DEFAULT_THEME["sections_order"]]
        elif key == "featured_collections":
            if isinstance(value, list):
                cleaned[key] = [str(s)[:200] for s in value[:12]]
        else:
            cleaned[key] = value
    cleaned["version"] = 1
    return cleaned
