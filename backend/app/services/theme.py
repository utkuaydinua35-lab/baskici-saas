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
import re
import uuid

MAX_SECTIONS = 12
MAX_SLIDES = 6

SECTION_DEFAULTS: dict[str, dict] = {
    "hero_slider": {
        "slides": [],   # [{image,title,subtitle,cta_text,cta_url}]
        "autoplay_sec": 5,
        # Çerçeve köşe ovalliği: both|mobile|desktop|none + %0-100
        "radius_scope": "both",
        "radius_pct": 50,
        # Metin hizası: center | left (sol hizada soldan koyulaşan geçiş)
        "align": "center",
        # Yükseklik: normal | tall (tam ekrana yakın vitrin)
        "height": "normal",
    },
    # Bölüm başlığı üçlüsü (eyebrow/title/subtitle) — "SENİN İÇİN SEÇTİK /
    # Çok Satanlar / En sevilen tasarımlar" kalıbı. Boş alan gösterilmez.
    # layout: grid (4'lü küçük kart) | showcase (2'li büyük, numaralı, açıklamalı)
    "featured_collections": {"eyebrow": "", "title": "Koleksiyonlar", "subtitle": "",
                             "slugs": [], "layout": "grid", "limit": 4},
    # layout: grid | carousel (oklu yatay şerit)
    "products_grid": {"eyebrow": "", "title": "Öne Çıkanlar", "subtitle": "",
                      "collection": None, "limit": 8, "layout": "grid"},
    "featured_products": {"eyebrow": "", "title": "Öne Çıkan Ürünler", "subtitle": "",
                          "slugs": [], "layout": "grid"},
    "rich_text": {"title": "", "body": ""},
    "banner": {"image": None, "url": "", "radius_scope": "both", "radius_pct": 50},
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
    "testimonials": {"eyebrow": "", "title": "Müşterilerimiz Ne Diyor?", "subtitle": "",
                     "items": []},  # [{author, text, rating}]
    # Görsel galerisi (ShinePro image-slider "Sizden Gelenler")
    # aspect: square | story (9:16 hikâye kartı)
    # mode: scroll (elle kaydır) | carousel (oklu + otomatik) | marquee (sürekli akan)
    # ogeler: [{url, tip: gorsel|video, link, etiket}] — doğruluk kaynağı.
    # images: [url] — eski biçim; okunurken ogeler'e çevrilir, yazılırken
    # ogeler'den türetilir (eski önbellek/istemci kırılmasın).
    "gallery": {"eyebrow": "", "title": "Sizden Gelenler", "subtitle": "",
                "images": [], "ogeler": [], "aspect": "square", "mode": "scroll"},  # max 12
    # İletişim formu (ShinePro contact-form) — mağaza e-postasına iletir
    "contact": {"title": "İletişim", "subtitle": "Soru ve önerileriniz için bize yazın."},
    # Kampanya geri sayımı — süre dolunca bölüm kendini gizler
    "countdown": {"title": "Kampanya bitiyor!", "subtitle": "", "ends_at": "",
                  "cta_text": "Alışverişe Başla", "cta_url": "/urunler"},
}

MAX_FAQ_ITEMS = 12
MAX_LIST_ITEMS = 8
MAX_GALLERY_IMAGES = 12

# Değeri sabit bir kümeye kısıtlanan ayarlar: (bölüm tipi, anahtar) → izinliler.
# İlki varsayılandır. Panel/elle düzenlenmiş config'ten gelen tanımsız değer
# vitrinde beklenmedik sınıf üretmesin diye varsayılana düşer.
_SECTION_ENUMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("hero_slider", "align"): ("center", "left"),
    ("hero_slider", "height"): ("normal", "tall"),
    ("featured_collections", "layout"): ("grid", "showcase"),
    ("products_grid", "layout"): ("grid", "carousel"),
    ("featured_products", "layout"): ("grid", "carousel"),
    ("gallery", "aspect"): ("square", "story"),
    ("gallery", "mode"): ("scroll", "carousel", "marquee"),
}
# Başlık üçlüsü olan bölümlerde metin alanı uzunluk sınırları
_HEADING_LIMITS = {"eyebrow": 60, "title": 100, "subtitle": 200}

# Tema geneli görünüm seçenekleri (style.*) — ilki varsayılan
_STYLE_ENUMS: dict[str, tuple[str, ...]] = {
    "header_layout": ("left", "center"),     # logo solda | logo ortada, menü altında
    "button_shape": ("rounded", "pill"),     # yuvarlatılmış köşe | tam yuvarlak
    "card_style": ("boxed", "minimal"),      # çerçeveli kart | çerçevesiz, ortalı yazı
    "heading_style": ("compact", "showcase"),  # küçük sol başlık | büyük ortalı başlık
    "header_sabit": ("hep", "mobil", "masaustu", "yok"),
}
MAX_DUYURU = 8

_SLIDE_KEYS = {"image", "eyebrow", "title", "subtitle", "cta_text", "cta_url", "cta2_text", "cta2_url"}

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
    "logo_width": 120,   # px — MASAÜSTÜ logo genişliği (60-320)
    # px — MOBİL logo genişliği (40-240); None = masaüstüyle aynı (ekrana sığdırılır)
    "logo_width_mobile": None,
    "favicon_url": None,
    # bg: şerit rengi (#rrggbb); boşsa temanın ana rengi.
    # items: [{text, url}] — birden fazla duyuru ("3 AL 2 ÖDE!", "950 TL üzeri
    # ücretsiz kargo!"). kayan: sürekli akan şerit; kapalıysa duyurular sırayla
    # değişir. text/url eski tek-duyuru biçimi: okunurken items'a çevrilir.
    "announcement": {"enabled": False, "text": "", "url": "", "bg": "",
                     "items": [], "kayan": True},
    # Tema geneli görünüm — değerler _STYLE_ENUMS'ta; scroll_top: sağ altta
    # "yukarı çık" düğmesi
    # header_sabit: sayfa kayarken üst menü görünür kalsın mı — hep | mobil
    # (yalnız mobilde) | masaustu (yalnız masaüstünde) | yok
    "style": {"header_layout": "left", "button_shape": "rounded",
              "card_style": "boxed", "heading_style": "compact", "scroll_top": False,
              "header_sabit": "hep"},
    # Açılış kampanya pop-up'ı — sayfa açılınca bir kez görünür (oturumda
    # tekrar çıkmaz). Marka-nötr: her mağaza kendi metnini/kupon kodunu yazar.
    # baslik/metin boşsa pop-up HİÇ gösterilmez (kapalı gibi davranır).
    # ust_baslik: başlığın üstündeki küçük etiket (örn. "✨ KAMPANYA ✨");
    # baslik'ta satır sonu korunur ("3 AL 2 ÖDE\n5 AL 3 ÖDE").
    # gorsel_boyut: pop-up görselinin (ör. logo) genişliği, % (30-100)
    "popup": {"enabled": False, "ust_baslik": "", "baslik": "", "metin": "", "kupon": "",
              "buton": "Alışverişe Başla", "gorsel_url": "", "gorsel_boyut": 100},
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
    # Sipariş onayı (teşekkür) ekranı metinleri — ödeme sonrası sayfa
    "thankyou": {"title": "", "message": ""},
    # Sepet kampanya mesajları — {kalan} {x} {y} yer tutucuları desteklenir
    "cart_messages": {
        "bxgy_progress": "🎁 {x} AL {y} ÖDE'den yararlanmak için sepetine {kalan} ürün daha ekle!",
        "bxgy_reached": "🎉 {x} AL {y} ÖDE kazandın — en ucuz ürünler bedava!",
    },
    # Sayfa bazlı içerik — koleksiyon sayfalarına özel blok (tutorial görseli
    # + metin; ürün listesinin üstünde ya da altında). {slug: {image, body, position}}
    "collection_pages": {},
    # Vitrin metin sözlüğü — sabit arayüz yazıları marka diliyle özelleştirilir
    "texts": {
        "add_to_cart": "Sepete Ekle",
        "cart_empty": "Sepetiniz boş.",
        "checkout_cta": "Ödemeye Geç",
        "newsletter_title": "📮 Kampanyalardan haberdar olun",
        "trust_ssl": "256-bit SSL güvenli ödeme",
        # BOŞ: vitrin bunu mağazanın teslim süresinden türetir (lib/texts.ts).
        # Burada dolu olsaydı her mağazaya "özel metin" gibi gidip türetmeyi
        # ezer ve BERNZ'in "1-3 iş günü" taahhüdünü her kiracıya yayardı.
        "trust_shipping": "",
        "trust_return": "Kolay iade ve değişim",
        "fav_empty_title": "Favori listeniz boş",
        "fav_empty_sub": "Beğendiğiniz ürünlerin kalbine dokunun, burada biriksin.",
    },
}

FONT_PRESETS = {"inter", "poppins", "playfair", "dm-sans"}

# ─── Hazır tema şablonları (Shopify theme library karşılığı) ─────
# Uygulanınca renk/font/duyuru/bölümler değişir; logo, favicon, WhatsApp,
# özel kod ve mağazaya özel ayarlar KORUNUR (panel tarafı merge eder).
THEME_PRESETS: dict[str, dict] = {
    "modern": {
        "label": "Modern",
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
        "label": "ShinePro",
        "description": "Poppins yazı tipi, mor vurgu, kampanya şeridi ve zengin "
                       "anasayfa akışı.",
        "theme": {
            "colors": {"primary": "#121212", "accent": "#6d388b", "bg": "#ffffff"},
            "font": "poppins",
            # Kapalı gelir: kiracı kendi kampanyasını yazıp açar. Eskiden açıktı
            # ve "hemen üretelim" diye bir üretim vaadi taşıyordu.
            "announcement": {"enabled": False,
                             "text": "🎉 Kampanya metninizi buraya yazın",
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
                      "text": "Siparişiniz özenle hazırlanır"},
                     {"icon": "💬", "title": "Destek", "text": "Sorularınız için yanınızdayız"},
                     {"icon": "↩️", "title": "Kolay İade", "text": "Koşullar iade sayfamızda"},
                     {"icon": "🔒", "title": "Güvenli Ödeme",
                      "text": "256-bit SSL ile korunur"},
                 ]}},
                {"id": "sp-karsilastirma", "type": "comparison",
                 "settings": {"title": "NEDEN BİZ?", "us_label": "Biz",
                              "them_label": "Diğerleri", "rows": [
                     {"feature": "Özenli paketleme", "us": True, "them": False},
                     {"feature": "Hızlı kargo", "us": True, "them": False},
                     {"feature": "Güvenli ödeme", "us": True, "them": False},
                     {"feature": "Kolay iade ve değişim", "us": True, "them": False},
                     {"feature": "Gerçek müşteri desteği", "us": True, "them": False},
                 ]}},
                {"id": "sp-galeri", "type": "gallery",
                 "settings": {"title": "SİZDEN GELENLER", "images": []}},
                {"id": "sp-yorumlar", "type": "testimonials",
                 "settings": {"title": "MÜŞTERİLERİMİZ NE DİYOR?", "items": []}},  # BOŞ: hazır temada uydurma müşteri yorumu yayınlanmaz
                {"id": "sp-kolek", "type": "featured_collections",
                 "settings": {"title": "Koleksiyonlar", "slugs": []}},
                {"id": "sp-sss", "type": "faq",
                 "settings": {"title": "Sıkça Sorulan Sorular", "items": [
                     {"q": "Siparişim ne zaman kargoya verilir?",
                      "a": "Kargo ve teslimat süreleri ürün sayfalarında ve mesafeli satış sözleşmesinde belirtilir."},
                     {"q": "İade edebilir miyim?",
                      "a": "İade koşulları için İade ve Değişim sayfamıza göz atın."},
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
    # ── Manzara ── landscapecase.com düzeninden uyarlanmış marka-NÖTR tema.
    # Bölüm sırası onlarınkiyle aynı: sol hizalı büyük hero → hikâye kartı
    # şeridi → numaralı büyük koleksiyon kartları → tam genişlik banner →
    # sürekli akan "Sizden Gelenler" → oklu "Çok Satanlar" şeridi.
    # Görsel alanları BOŞ gelir (boş bölüm vitrinde görünmez); mağaza kendi
    # görsellerini ekler. Açılış pop-up'ı açık ama başlığı boş → mağaza kendi
    # kampanyasını yazana dek çıkmaz. Hiçbir metinde marka adı yok.
    "manzara": {
        "label": "Manzara",
        "description": "Ortada logo, tam yuvarlak butonlar, büyük ortalı başlıklar; "
                       "açılış kampanya pop-up'ı, hikâye kartı şeridi, sürekli akan "
                       "galeri ve oklu ürün şeridi. Görselleri siz eklersiniz.",
        "theme": {
            "colors": {"primary": "#111111", "accent": "#6f4c87", "bg": "#f8f9fd"},
            "font": "poppins",
            "announcement": {"enabled": False, "text": "", "url": "", "bg": ""},
            "style": {"header_layout": "center", "button_shape": "pill",
                      "card_style": "minimal", "heading_style": "showcase",
                      "scroll_top": True},
            "popup": {"enabled": True, "ust_baslik": "✨ KAMPANYA ✨", "baslik": "",
                      "metin": "", "kupon": "", "buton": "Alışverişe Devam Et",
                      "gorsel_url": ""},
            "animations": {"reveal": True, "hover_zoom": True, "cart_drawer": True},
            "sections": [
                {"id": "mz-hero", "type": "hero_slider",
                 "settings": {"slides": [], "autoplay_sec": 5, "align": "left",
                              "height": "tall", "radius_scope": "both", "radius_pct": 67}},
                {"id": "mz-hikaye", "type": "gallery",
                 "settings": {"eyebrow": "Gerçek Deneyimler", "title": "Sizden Gelenler ✨",
                              "subtitle": "Müşterilerimizin paylaşımları.",
                              "images": [], "aspect": "story", "mode": "carousel"}},
                {"id": "mz-kolek", "type": "featured_collections",
                 "settings": {"eyebrow": "Tarzını Seç", "title": "Koleksiyonlar",
                              "subtitle": "Tarzına en yakın seriyi seç.",
                              "slugs": [], "layout": "showcase", "limit": 6}},
                {"id": "mz-banner", "type": "banner",
                 "settings": {"image": None, "url": "", "radius_scope": "both", "radius_pct": 50}},
                {"id": "mz-akan", "type": "gallery",
                 "settings": {"eyebrow": "Gerçek Deneyimler", "title": "Sizin Karelerinizden",
                              "subtitle": "Sizden gelen fotoğraf paylaşımları.",
                              "images": [], "aspect": "story", "mode": "marquee"}},
                {"id": "mz-cok-satan", "type": "products_grid",
                 "settings": {"eyebrow": "Senin İçin Seçtik", "title": "Çok Satanlar",
                              "subtitle": "En sevilen tasarımları keşfet.",
                              "collection": None, "limit": 12, "layout": "carousel"}},
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


_VIDEO_UZANTI = (".mp4", ".webm", ".mov", ".m4v")


def _guvenli_link(u) -> str:
    """Galeri öğesi bağlantısı: site içi yol ya da https. javascript:, //
    ile başlayan protokolsüz adres vb. atılır."""
    u = str(u or "").strip()[:300]
    if u.startswith("/") and not u.startswith("//"):
        return u
    return u if u.lower().startswith("https://") else ""


def _galeri_ogesi(x) -> dict | None:
    if isinstance(x, str):
        x = {"url": x}
    if not isinstance(x, dict):
        return None
    url = str(x.get("url") or "").strip()[:500]
    if not url or not (url.startswith("/storage/") or url.lower().startswith("https://")):
        return None
    tip = x.get("tip")
    if tip not in ("gorsel", "video"):
        tip = "video" if url.lower().endswith(_VIDEO_UZANTI) else "gorsel"
    return {"url": url, "tip": tip, "link": _guvenli_link(x.get("link")),
            "etiket": str(x.get("etiket") or "").strip()[:60]}


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
        for (etype, key), allowed in _SECTION_ENUMS.items():
            if etype == stype and settings.get(key) not in allowed:
                settings[key] = allowed[0]
        if "eyebrow" in defaults:   # başlık üçlüsü olan bölümler
            for key, limit in _HEADING_LIMITS.items():
                settings[key] = str(settings.get(key) or "")[:limit]
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
            if stype == "featured_collections":
                try:
                    settings["limit"] = min(12, max(1, int(settings.get("limit") or 4)))
                except (TypeError, ValueError):
                    settings["limit"] = 4
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
            ham = settings.get("ogeler") or [
                {"url": u} for u in (settings.get("images") or []) if u]
            settings["ogeler"] = [o for o in (_galeri_ogesi(x) for x in ham) if o][:MAX_GALLERY_IMAGES]
            settings["images"] = [o["url"] for o in settings["ogeler"]]
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
    style = theme.get("style") if isinstance(theme.get("style"), dict) else {}
    for key, allowed in _STYLE_ENUMS.items():
        if style.get(key) not in allowed:
            style[key] = allowed[0]
    style["scroll_top"] = bool(style.get("scroll_top"))
    theme["style"] = style
    ann = theme.get("announcement") or {}
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(ann.get("bg") or "")):
        ann["bg"] = ""
    ham = ann.get("items") or ([{"text": ann.get("text"), "url": ann.get("url")}]
                               if (ann.get("text") or "").strip() else [])
    ann["items"] = [
        {"text": str(x.get("text") or "").strip()[:140], "url": _guvenli_link(x.get("url"))}
        for x in ham[:MAX_DUYURU] if isinstance(x, dict) and str(x.get("text") or "").strip()
    ]
    ann["kayan"] = bool(ann.get("kayan", True))
    # Eski alanlar ilk duyuruyu yansıtır (eski önbellek / istemci kırılmasın)
    ann["text"] = ann["items"][0]["text"] if ann["items"] else ""
    ann["url"] = ann["items"][0]["url"] if ann["items"] else ""
    popup = theme.get("popup") or {}
    for key, limit in (("ust_baslik", 40), ("baslik", 80), ("metin", 140),
                       ("kupon", 40), ("buton", 40), ("gorsel_url", 500)):
        popup[key] = str(popup.get(key) or "")[:limit]
    popup["enabled"] = bool(popup.get("enabled"))
    try:
        popup["gorsel_boyut"] = min(100, max(30, int(popup.get("gorsel_boyut") or 100)))
    except (TypeError, ValueError):
        popup["gorsel_boyut"] = 100
    lwm = theme.get("logo_width_mobile")
    try:
        theme["logo_width_mobile"] = min(240, max(40, int(lwm))) if lwm not in (None, "") else None
    except (TypeError, ValueError):
        theme["logo_width_mobile"] = None
    theme["version"] = 2
    return theme


def validate_theme_patch(patch: dict) -> dict:
    """Panelden gelen temayı temizle: yalnızca bilinen anahtarlar."""
    cleaned: dict = {}
    for key in ("colors", "announcement", "popup", "style", "animations", "footer", "whatsapp",
                "trust_badges", "cart_messages", "thankyou", "texts"):
        value = patch.get(key)
        default = DEFAULT_THEME[key]
        if isinstance(value, dict):
            cleaned[key] = {k: v for k, v in value.items() if k in default}
    # Sayfa bazlı koleksiyon blokları — anahtar slug olduğundan genel
    # döngüdeki "bilinen anahtar" filtresine giremez, ayrı temizlenir
    if isinstance(patch.get("collection_pages"), dict):
        pages = {}
        for slug, blk in list(patch["collection_pages"].items())[:50]:
            if not isinstance(blk, dict):
                continue
            body = str(blk.get("body") or "").strip()[:4000]
            image = blk.get("image")
            cta_text = str(blk.get("cta_text") or "").strip()[:60]
            cta_url = str(blk.get("cta_url") or "").strip()[:300]
            if not body and not image and not (cta_text and cta_url):
                continue   # boş blok saklanmaz
            pages[str(slug)[:200]] = {
                "image": str(image)[:500] if image else None,
                "body": body,
                "position": "alt" if blk.get("position") == "alt" else "ust",
                # Yönlendirme butonu (ops.) — koleksiyon/ürün/sayfa hedefi
                "cta_text": cta_text,
                "cta_url": cta_url,
            }
        cleaned["collection_pages"] = pages
    for key in ("font", "logo_url", "favicon_url"):
        if key in patch:
            cleaned[key] = patch[key]
    if "name" in patch:
        cleaned["name"] = str(patch["name"] or "").strip()[:80] or "Mağaza Teması"
    if "logo_width_mobile" in patch:
        v = patch["logo_width_mobile"]
        try:
            cleaned["logo_width_mobile"] = min(240, max(40, int(v))) if v not in (None, "") else None
        except (TypeError, ValueError):
            cleaned["logo_width_mobile"] = None
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
