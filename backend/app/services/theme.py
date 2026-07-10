"""
Vitrin tema şeması — Store.config["theme"].

v2: anasayfa `sections` LİSTESİDİR — [{id, type, settings}]. Tipler:
  hero_slider          {slides:[{image,title,subtitle,cta_text,cta_url}], autoplay_sec}
  featured_collections {title, slugs:[]}
  products_grid        {title, collection, limit}
  featured_products    {title, slugs:[]}   ← elle seçilen ürünler (sıralı)
  rich_text            {title, body}
  banner               {image, url}

GERİYE UYUMLULUK: eski v1 alanları (hero/featured_collections/sections_order)
resolve_theme OKURKEN v2 sections listesine çevrilir; panel kaydettiğinde
v2 yazılır. Vitrin daima tam (defaults ile birleşik) tema alır.
"""
from __future__ import annotations

import copy
import uuid

MAX_SECTIONS = 12
MAX_SLIDES = 6

SECTION_DEFAULTS: dict[str, dict] = {
    "hero_slider": {
        "slides": [],   # [{image,title,subtitle,cta_text,cta_url}]
        "autoplay_sec": 5,
    },
    "featured_collections": {"title": "Koleksiyonlar", "slugs": []},
    "products_grid": {"title": "Öne Çıkanlar", "collection": None, "limit": 8},
    "featured_products": {"title": "Öne Çıkan Ürünler", "slugs": []},
    "rich_text": {"title": "", "body": ""},
    "banner": {"image": None, "url": ""},
    # Görsel + metin (Shopify "Image with text")
    "image_with_text": {"image": None, "title": "", "body": "",
                        "cta_text": "", "cta_url": "", "image_side": "left"},
    # SSS akordeonu (Shopify "Collapsible content")
    "faq": {"title": "Sıkça Sorulan Sorular", "items": []},  # [{q, a}]
    # Bülten kayıt bölümü (footer'daki formun büyük hali)
    "newsletter": {"title": "Kampanyalardan haberdar olun",
                   "subtitle": "İndirim ve yeni tasarımlar e-postanıza gelsin."},
}

MAX_FAQ_ITEMS = 12

_SLIDE_KEYS = {"image", "title", "subtitle", "cta_text", "cta_url"}

DEFAULT_THEME: dict = {
    "version": 2,
    "colors": {
        "primary": "#18181b",   # buton/vurgu (zinc-900)
        "accent": "#f59e0b",    # ikincil vurgu (amber-500)
        "bg": "#fafafa",        # sayfa zemini
    },
    "font": "inter",            # inter | poppins | playfair | dm-sans
    "logo_url": None,
    "favicon_url": None,
    "announcement": {"enabled": False, "text": "", "url": ""},
    "sections": [
        {"id": "varsayilan-hero", "type": "hero_slider",
         "settings": dict(SECTION_DEFAULTS["hero_slider"])},
        {"id": "varsayilan-koleksiyonlar", "type": "featured_collections",
         "settings": dict(SECTION_DEFAULTS["featured_collections"])},
        {"id": "varsayilan-urunler", "type": "products_grid",
         "settings": dict(SECTION_DEFAULTS["products_grid"])},
    ],
    "animations": {"reveal": True, "hover_zoom": True, "cart_drawer": True},
    "footer": {"about": "", "instagram": ""},
    # WhatsApp yüzen butonu (TR e-ticareti standardı) — boşsa görünmez
    "whatsapp": {"enabled": False, "number": "", "message": "Merhaba, sipariş hakkında bilgi almak istiyorum."},
    # Ürün sayfası + checkout güven şeridi
    "trust_badges": {"enabled": True},
}

FONT_PRESETS = {"inter", "poppins", "playfair", "dm-sans"}

# ─── Hazır tema şablonları (Shopify theme library karşılığı) ─────
# Uygulanınca renk/font/duyuru/bölümler değişir; logo, favicon, WhatsApp,
# özel kod ve mağazaya özel ayarlar KORUNUR (panel tarafı merge eder).
THEME_PRESETS: dict[str, dict] = {
    "bernz-modern": {
        "label": "Bernz Modern",
        "description": "Sade ve çağdaş varsayılan tasarım — Inter yazı tipi, "
                       "koyu butonlar, amber vurgu.",
        "theme": {
            "colors": {"primary": "#18181b", "accent": "#f59e0b", "bg": "#fafafa"},
            "font": "inter",
            "announcement": {"enabled": False, "text": "", "url": ""},
            "animations": {"reveal": True, "hover_zoom": True, "cart_drawer": True},
            "sections": [
                {"id": "bm-hero", "type": "hero_slider",
                 "settings": {"slides": [], "autoplay_sec": 5}},
                {"id": "bm-kolek", "type": "featured_collections",
                 "settings": {"title": "Koleksiyonlar", "slugs": []}},
                {"id": "bm-urun", "type": "products_grid",
                 "settings": {"title": "Öne Çıkanlar", "collection": None, "limit": 8}},
            ],
        },
    },
    # luneracase.com ShinePro 1.3.0 Shopify dışa aktarımından türetildi:
    # Poppins başlık, koyu butonlar (#121212), mor vurgu (#6d388b),
    # anasayfa: slayt → çok satanlar → neden biz → SSS → bülten.
    "shinepro": {
        "label": "ShinePro (Lunera)",
        "description": "Lunera Case temasından uyarlandı — Poppins yazı tipi, "
                       "mor vurgu, kampanya şeridi ve zengin anasayfa akışı.",
        "theme": {
            "colors": {"primary": "#121212", "accent": "#6d388b", "bg": "#ffffff"},
            "font": "poppins",
            "announcement": {"enabled": True,
                             "text": "🚚 Tüm siparişlerde hızlı kargo — bugün sipariş ver, hemen üretelim!",
                             "url": "/urunler"},
            "animations": {"reveal": True, "hover_zoom": True, "cart_drawer": True},
            "sections": [
                {"id": "sp-hero", "type": "hero_slider",
                 "settings": {"slides": [], "autoplay_sec": 5}},
                {"id": "sp-cok-satan", "type": "products_grid",
                 "settings": {"title": "ÇOK SATANLAR", "collection": None, "limit": 8}},
                {"id": "sp-neden", "type": "image_with_text",
                 "settings": {"image": None, "title": "Neden Biz?",
                              "body": "Kişiye özel baskı, darbelere dayanıklı malzeme ve "
                                      "1-3 iş gününde kargo. Tasarımını seç, gerisini bize bırak.",
                              "cta_text": "Ürünlere Göz At", "cta_url": "/urunler",
                              "image_side": "left"}},
                {"id": "sp-kolek", "type": "featured_collections",
                 "settings": {"title": "Koleksiyonlar", "slugs": []}},
                {"id": "sp-sss", "type": "faq",
                 "settings": {"title": "Sıkça Sorulan Sorular", "items": [
                     {"q": "Kargoya ne zaman verilir?",
                      "a": "Siparişiniz kişiye özel üretilir ve 1-3 iş günü içinde kargoya verilir."},
                     {"q": "İade edebilir miyim?",
                      "a": "Kişiye özel üretimlerde iade koşulları için İade ve Değişim sayfamıza göz atın."},
                     {"q": "Hangi telefon modelleri destekleniyor?",
                      "a": "Ürün sayfasındaki model seçiciden telefonunuzu bulabilirsiniz — "
                           "yüzlerce model için üretim yapıyoruz."},
                 ]}},
                {"id": "sp-bulten", "type": "newsletter",
                 "settings": {"title": "Kampanyalardan haberdar olun",
                              "subtitle": "İndirim ve yeni tasarımlar e-postanıza gelsin."}},
            ],
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _migrate_v1(theme: dict) -> dict:
    """Eski hero/featured_collections/sections_order alanlarını v2 sections'a çevir.

    Config'e YAZMAZ — yalnızca okuma yolunda dönüştürür (panel kaydedince v2 kalıcılaşır).
    """
    hero = theme.get("hero") or {}
    featured = theme.get("featured_collections") or []
    order = theme.get("sections_order") or ["hero", "featured", "products"]

    sections = []
    for key in order:
        if key == "hero":
            slides = []
            if hero.get("enabled"):
                slides = [{
                    "image": hero.get("image"),
                    "title": hero.get("title") or "",
                    "subtitle": hero.get("subtitle") or "",
                    "cta_text": hero.get("cta_text") or "",
                    "cta_url": hero.get("cta_url") or "/urunler",
                }]
            sections.append({"id": "v1-hero", "type": "hero_slider",
                             "settings": {"slides": slides, "autoplay_sec": 5}})
        elif key == "featured":
            sections.append({"id": "v1-koleksiyonlar", "type": "featured_collections",
                             "settings": {"title": "Koleksiyonlar", "slugs": list(featured)}})
        elif key == "products":
            sections.append({"id": "v1-urunler", "type": "products_grid",
                             "settings": dict(SECTION_DEFAULTS["products_grid"])})

    out = dict(theme)
    out["sections"] = sections
    out["version"] = 2
    for old in ("hero", "featured_collections", "sections_order"):
        out.pop(old, None)
    return out


def _normalize_sections(sections: list) -> list:
    """Bölüm listesini temizle: bilinen tipler, ayar whitelist'i, limitler."""
    cleaned: list[dict] = []
    for sec in (sections or [])[:MAX_SECTIONS]:
        if not isinstance(sec, dict):
            continue
        stype = sec.get("type")
        if stype not in SECTION_DEFAULTS:
            continue
        defaults = SECTION_DEFAULTS[stype]
        raw = sec.get("settings") or {}
        settings = copy.deepcopy(defaults)
        for k in defaults:
            if k in raw:
                settings[k] = raw[k]
        if stype == "hero_slider":
            settings["slides"] = [
                {k: (s.get(k) if isinstance(s, dict) else None) for k in _SLIDE_KEYS}
                for s in (settings.get("slides") or [])[:MAX_SLIDES]
            ]
            try:
                settings["autoplay_sec"] = min(30, max(0, int(settings.get("autoplay_sec") or 5)))
            except (TypeError, ValueError):
                settings["autoplay_sec"] = 5
        elif stype in ("featured_collections", "featured_products"):
            settings["slugs"] = [str(s)[:200] for s in (settings.get("slugs") or [])[:12]]
        elif stype == "products_grid":
            try:
                settings["limit"] = min(24, max(1, int(settings.get("limit") or 8)))
            except (TypeError, ValueError):
                settings["limit"] = 8
        elif stype == "image_with_text":
            if settings.get("image_side") not in ("left", "right"):
                settings["image_side"] = "left"
        elif stype == "faq":
            settings["items"] = [
                {"q": str((i or {}).get("q") or "")[:300],
                 "a": str((i or {}).get("a") or "")[:2000]}
                for i in (settings.get("items") or [])[:MAX_FAQ_ITEMS]
                if isinstance(i, dict) and (i.get("q") or i.get("a"))
            ]
        cleaned.append({
            "id": str(sec.get("id") or uuid.uuid4().hex[:8])[:40],
            "type": stype,
            "settings": settings,
        })
    return cleaned


def resolve_theme(store_config: dict | None) -> dict:
    """Config'teki tema + defaults → tam tema (her alan dolu, daima v2)."""
    raw = (store_config or {}).get("theme") or {}
    if raw and "sections" not in raw and (
        "hero" in raw or "featured_collections" in raw or "sections_order" in raw
    ):
        raw = _migrate_v1(raw)
    theme = _deep_merge(DEFAULT_THEME, raw)
    if theme.get("font") not in FONT_PRESETS:
        theme["font"] = DEFAULT_THEME["font"]
    # _deep_merge listeleri override eder ama raw'da sections yoksa defaults kalır
    theme["sections"] = _normalize_sections(theme.get("sections"))
    theme["version"] = 2
    return theme


def validate_theme_patch(patch: dict) -> dict:
    """Panelden gelen temayı temizle: yalnızca bilinen anahtarlar."""
    cleaned: dict = {}
    for key in ("colors", "announcement", "animations", "footer", "whatsapp", "trust_badges"):
        value = patch.get(key)
        default = DEFAULT_THEME[key]
        if isinstance(value, dict):
            cleaned[key] = {k: v for k, v in value.items() if k in default}
    for key in ("font", "logo_url", "favicon_url"):
        if key in patch:
            cleaned[key] = patch[key]
    cleaned["sections"] = _normalize_sections(patch.get("sections") or [])
    cleaned["version"] = 2
    return cleaned
