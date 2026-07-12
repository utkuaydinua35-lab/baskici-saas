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
    # İkon şeridi (ShinePro icon-bar): avantaj vurguları
    "icon_bar": {"items": []},   # [{icon, title, text}] max 6
    # Karşılaştırma tablosu (ShinePro comparison-table): Biz vs Diğerleri
    "comparison": {"title": "Neden Biz?", "us_label": "Biz", "them_label": "Diğerleri",
                   "rows": []},  # [{feature, us: bool, them: bool}] max 8
    # Müşteri yorumları vitrini (ShinePro results/testimonials)
    "testimonials": {"title": "Müşterilerimiz Ne Diyor?", "items": []},  # [{author, text, rating}]
    # Görsel galerisi (ShinePro image-slider "Sizden Gelenler")
    "gallery": {"title": "Sizden Gelenler", "images": []},  # [url] max 8
    # İletişim formu (ShinePro contact-form) — mağaza e-postasına iletir
    "contact": {"title": "İletişim", "subtitle": "Soru ve önerileriniz için bize yazın."},
    # Kampanya geri sayımı — süre dolunca bölüm kendini gizler
    "countdown": {"title": "Kampanya bitiyor!", "subtitle": "", "ends_at": "",
                  "cta_text": "Alışverişe Başla", "cta_url": "/urunler"},
}

MAX_FAQ_ITEMS = 12
MAX_LIST_ITEMS = 8

_SLIDE_KEYS = {"image", "title", "subtitle", "cta_text", "cta_url", "cta2_text", "cta2_url"}

DEFAULT_THEME: dict = {
    "version": 2,
    "name": "Mağaza Teması",   # panelde görünen tema adı (yayındayken de değişir)
    "colors": {
        "primary": "#18181b",   # buton/vurgu (zinc-900)
        "accent": "#f59e0b",    # ikincil vurgu (amber-500)
        "bg": "#fafafa",        # sayfa zemini
    },
    "font": "inter",            # inter | poppins | playfair | dm-sans
    "logo_url": None,
    "logo_width": 120,   # px — panelden ayarlanır (60-320)
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
    # Üst menü linkleri (Shopify Navigation) — boşsa varsayılan menü kullanılır
    "nav_links": [],   # [{label, url}]
    # WhatsApp yüzen butonu (TR e-ticareti standardı) — boşsa görünmez
    "whatsapp": {"enabled": False, "number": "", "message": "Merhaba, sipariş hakkında bilgi almak istiyorum."},
    # Ürün sayfası + checkout güven şeridi
    "trust_badges": {"enabled": True},
    # Sepet kampanya mesajları — {kalan} {x} {y} yer tutucuları desteklenir
    "cart_messages": {
        "bxgy_progress": "🎁 {x} AL {y} ÖDE'den yararlanmak için sepetine {kalan} ürün daha ekle!",
        "bxgy_reached": "🎉 {x} AL {y} ÖDE kazandın — en ucuz ürünler bedava!",
    },
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
                {"id": "sp-ikonlar", "type": "icon_bar",
                 "settings": {"items": [
                     {"icon": "🚚", "title": "Hızlı Kargo",
                      "text": "1-3 iş gününde kargoda"},
                     {"icon": "🎨", "title": "Kişiye Özel Baskı",
                      "text": "Tasarımını seç, biz basalım"},
                     {"icon": "🛡️", "title": "Dayanıklı Malzeme",
                      "text": "Darbe emici kaliteli kılıf"},
                     {"icon": "🔒", "title": "Güvenli Ödeme",
                      "text": "iyzico / PayTR güvencesi"},
                 ]}},
                {"id": "sp-karsilastirma", "type": "comparison",
                 "settings": {"title": "NEDEN BİZ?", "us_label": "Biz",
                              "them_label": "Diğerleri", "rows": [
                     {"feature": "Kişiye özel baskı kalitesi", "us": True, "them": False},
                     {"feature": "1-3 iş gününde kargo", "us": True, "them": False},
                     {"feature": "Yüzlerce telefon modeli", "us": True, "them": False},
                     {"feature": "Kolay iade ve değişim", "us": True, "them": False},
                     {"feature": "Gerçek müşteri desteği", "us": True, "them": False},
                 ]}},
                {"id": "sp-galeri", "type": "gallery",
                 "settings": {"title": "SİZDEN GELENLER", "images": []}},
                {"id": "sp-yorumlar", "type": "testimonials",
                 "settings": {"title": "MÜŞTERİLERİMİZ NE DİYOR?", "items": [
                     {"author": "Elif K.", "rating": 5,
                      "text": "Baskı kalitesi harika, telefonuma tam oturdu. Kargolama da çok hızlıydı!"},
                     {"author": "Mert A.", "rating": 5,
                      "text": "Kendi tasarımımı yaptırdım, beklediğimden çok daha iyi geldi. Kesinlikle tavsiye ederim."},
                     {"author": "Zeynep D.", "rating": 5,
                      "text": "İkinci siparişim — renkleri canlı, malzemesi sağlam. Teşekkürler!"},
                 ]}},
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
                {"id": "sp-iletisim", "type": "contact",
                 "settings": {"title": "İLETİŞİM",
                              "subtitle": "Soru ve önerileriniz için bize yazın."}},
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
        elif stype == "icon_bar":
            settings["items"] = [
                {"icon": str((i or {}).get("icon") or "✨")[:8],
                 "title": str((i or {}).get("title") or "")[:80],
                 "text": str((i or {}).get("text") or "")[:200]}
                for i in (settings.get("items") or [])[:6]
                if isinstance(i, dict) and i.get("title")
            ]
        elif stype == "comparison":
            settings["rows"] = [
                {"feature": str((r or {}).get("feature") or "")[:120],
                 "us": bool((r or {}).get("us", True)),
                 "them": bool((r or {}).get("them", False))}
                for r in (settings.get("rows") or [])[:MAX_LIST_ITEMS]
                if isinstance(r, dict) and r.get("feature")
            ]
        elif stype == "testimonials":
            cleaned_items = []
            for i in (settings.get("items") or [])[:6]:
                if not isinstance(i, dict) or not i.get("text"):
                    continue
                try:
                    rating = min(5, max(1, int(i.get("rating") or 5)))
                except (TypeError, ValueError):
                    rating = 5
                cleaned_items.append({
                    "author": str(i.get("author") or "Müşteri")[:80],
                    "text": str(i.get("text") or "")[:600],
                    "rating": rating,
                })
            settings["items"] = cleaned_items
        elif stype == "gallery":
            settings["images"] = [
                str(u)[:500] for u in (settings.get("images") or [])[:MAX_LIST_ITEMS] if u
            ]
        cleaned.append({
            "id": str(sec.get("id") or uuid.uuid4().hex[:8])[:40],
            "type": stype,
            "settings": settings,
            # Gizle/göster: silmeden kapatma (Shopify eye toggle)
            "hidden": bool(sec.get("hidden")),
            # Zemin şeması: none (sayfa zemini) | band (beyaz bant)
            "scheme": sec.get("scheme") if sec.get("scheme") in ("none", "band") else "none",
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
    for key in ("colors", "announcement", "animations", "footer", "whatsapp",
                "trust_badges", "cart_messages"):
        value = patch.get(key)
        default = DEFAULT_THEME[key]
        if isinstance(value, dict):
            cleaned[key] = {k: v for k, v in value.items() if k in default}
    for key in ("font", "logo_url", "favicon_url"):
        if key in patch:
            cleaned[key] = patch[key]
    if "name" in patch:
        cleaned["name"] = str(patch["name"] or "").strip()[:80] or "Mağaza Teması"
    if "logo_width" in patch:
        try:
            cleaned["logo_width"] = min(320, max(60, int(patch["logo_width"] or 120)))
        except (TypeError, ValueError):
            cleaned["logo_width"] = 120
    if "nav_links" in patch:
        links = []
        for l in (patch.get("nav_links") or [])[:8]:
            if not isinstance(l, dict) or not str(l.get("label") or "").strip():
                continue
            label = str(l["label"]).strip()[:40]
            if l.get("type") == "collections":
                # Açılır koleksiyon menüsü — panelden ELLE seçilen koleksiyonlar
                links.append({
                    "label": label, "type": "collections",
                    "slugs": [str(s)[:200] for s in (l.get("slugs") or [])[:24] if s],
                })
            elif l.get("url"):
                links.append({"label": label, "url": str(l["url"])[:300]})
        cleaned["nav_links"] = links
    cleaned["sections"] = _normalize_sections(patch.get("sections") or [])
    cleaned["version"] = 2
    return cleaned
