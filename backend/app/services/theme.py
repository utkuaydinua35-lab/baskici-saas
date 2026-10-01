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

MAX_SECTIONS = 16
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
        # Görünüm: kaplama (görsel tam zemin, yazı üstünde) | bolunmus (açık
        # renkli yuvarlak pano: yazı solda, görsel sağda — Füzyon)
        "stil": "kaplama",
        # Bölünmüş panonun zemin rengi (#rrggbb)
        "panel_renk": "#efefef",
    },
    # Bölüm başlığı üçlüsü (eyebrow/title/subtitle) — "SENİN İÇİN SEÇTİK /
    # Çok Satanlar / En sevilen tasarımlar" kalıbı. Boş alan gösterilmez.
    # layout: grid (4'lü küçük kart) | showcase (2'li büyük, numaralı, açıklamalı)
    # yedek_gorseller: görseli OLMAYAN koleksiyon kartına sırayla konan görseller
    # (koleksiyonun kendi görseli varsa o kullanılır)
    "featured_collections": {"eyebrow": "", "title": "Koleksiyonlar", "subtitle": "",
                             "slugs": [], "layout": "grid", "limit": 4, "yedek_gorseller": []},
    # layout: grid | carousel (oklu yatay şerit)
    # layout sekmeli: üstte koleksiyon hapları (Tümü + sekmeler) ve sıralama;
    # hap seçilince o koleksiyonun ürünleri gösterilir (sayfa yenilenmeden)
    "products_grid": {"eyebrow": "", "title": "Öne Çıkanlar", "subtitle": "",
                      "collection": None, "limit": 8, "layout": "grid", "sekmeler": []},
    "featured_products": {"eyebrow": "", "title": "Öne Çıkan Ürünler", "subtitle": "",
                          "slugs": [], "layout": "grid"},
    "rich_text": {"title": "", "body": ""},
    "banner": {"image": None, "url": "", "radius_scope": "both", "radius_pct": 50},
    # Görsel + metin (Shopify "Image with text")
    # stil: acik (beyaz kart) | koyu (koyu editoryal pano, büyük başlık,
    # görselin köşesinde küçük not — Füzyon)
    "image_with_text": {"image": None, "eyebrow": "", "title": "", "body": "",
                        "cta_text": "", "cta_url": "", "image_side": "left",
                        "stil": "acik", "gorsel_notu": ""},
    # SSS akordeonu (Shopify "Collapsible content")
    # stil: tek (ortada liste) | iki_sutun (solda başlık + iletişim, sağda liste)
    # eposta: iki sütunda başlığın altındaki iletişim adresi (boşsa mağazanınki)
    "faq": {"eyebrow": "", "title": "Sıkça Sorulan Sorular", "subtitle": "", "items": [],
            "stil": "tek", "eposta": ""},  # [{q, a}]
    # Bülten kayıt bölümü (footer'daki formun büyük hali)
    "newsletter": {"title": "Kampanyalardan haberdar olun",
                   "subtitle": "İndirim ve yeni tasarımlar e-postanıza gelsin."},
    # İkon şeridi (ShinePro icon-bar): avantaj vurguları
    # stil: kart (ortalı kutular) | serit (tek çerçevede yan yana, tıklanır)
    # icon: emoji ya da çizgi ikon adı (kargo, konum, iade, eposta, destek,
    # guvenli, hediye, yildiz, kalp, saat, telefon, kutu)
    "icon_bar": {"items": [], "stil": "kart"},   # [{icon, title, text, url}] max 6
    # Karşılaştırma tablosu (ShinePro comparison-table): Biz vs Diğerleri
    "comparison": {"title": "Neden Biz?", "us_label": "Biz", "them_label": "Diğerleri",
                   "rows": []},  # [{feature, us: bool, them: bool}] max 8
    # Müşteri yorumları vitrini (ShinePro results/testimonials)
    # stil: kart (yıldızlı kutular) | fotografli (koyu bant, fotoğraflı
    # yatay kartlar, oklu + otomatik ilerleyen şerit)
    "testimonials": {"eyebrow": "", "title": "Müşterilerimiz Ne Diyor?", "subtitle": "",
                     "items": [], "stil": "kart", "alt_not": ""},  # [{author, text, rating, image}]
    # Görsel galerisi (ShinePro image-slider "Sizden Gelenler")
    # aspect: square | story (9:16 hikâye kartı)
    # mode: scroll (elle kaydır) | carousel (oklu + otomatik) | marquee (sürekli akan)
    # ogeler: [{url, tip: gorsel|video, link, etiket}] — doğruluk kaynağı.
    # images: [url] — eski biçim; okunurken ogeler'e çevrilir, yazılırken
    # ogeler'den türetilir (eski önbellek/istemci kırılmasın).
    # mode izgara: masaüstünde yan yana 5'li, mobilde kaydırılır; görseller
    # yavaşça yakınlaşır (Instagram paylaşımları). baglanti: başlığın
    # sağındaki link ("Takip et →").
    "gallery": {"eyebrow": "", "title": "Sizden Gelenler", "subtitle": "",
                "images": [], "ogeler": [], "aspect": "square", "mode": "scroll",
                "baglanti": "", "baglanti_metni": ""},  # max 12
    # İletişim formu (ShinePro contact-form) — mağaza e-postasına iletir
    "contact": {"title": "İletişim", "subtitle": "Soru ve önerileriniz için bize yazın."},
    # Kampanya geri sayımı — süre dolunca bölüm kendini gizler
    "countdown": {"title": "Kampanya bitiyor!", "subtitle": "", "ends_at": "",
                  "cta_text": "Alışverişe Başla", "cta_url": "/urunler"},
    # ── Füzyon bölümleri ──
    # Çapraz kurdeleler: üç eğik şerit zıt yönlerde akar. items: [{text, buyuk}]
    # palet: neon (sarı + pembe) | tema (ana renk + vurgu)
    "kurdele": {"items": [], "sembol": "✦", "palet": "neon"},
    # Stil önerici: ziyaretçi bir ruh hâli seçer, o hâle bağlı ürün sahnede
    # belirir. secenekler: [{etiket, renk, kelime, neden, urun(slug), zemin}]
    "stil_onerici": {"eyebrow": "", "title": "Hangi tarz\nsana göre?", "subtitle": "",
                     "secenekler": []},
    # Numaralı adımlar: solda başlık, sağda 01-02-03 satırları (tıklanır)
    "adimlar": {"eyebrow": "", "title": "", "subtitle": "", "items": []},  # [{title, text, url}]
    # Canlı kılıf önizleme: ziyaretçi fotoğrafını seçer, kılıfın üstünde
    # sürükler/yakınlaştırır. Fotoğraf cihazdan ÇIKMAZ (yüklenmez).
    "kilif_onizleme": {"eyebrow": "", "title": "", "subtitle": "",
                       "buton": "FOTOĞRAF SEÇ", "cta_text": "", "cta_url": "/tasarla",
                       "logo_yazi": "{magaza}",
                       "not": "Önizlemedir; baskı renkleri ekrana göre küçük farklar gösterebilir."},
    # Son bakılanlar: ziyaretçinin ürün sayfalarında gezdikleri (tarayıcısında
    # saklanır); ilk kez gelende liste boş → bölüm görünmez
    "son_bakilanlar": {"eyebrow": "", "title": "Son baktığın tasarımlar", "subtitle": ""},
}

MAX_FAQ_ITEMS = 12
# Çizgi ikon adları (vitrin lib/cizgiIkon.tsx ile birebir)
CIZGI_IKONLAR = {"kargo", "konum", "iade", "eposta", "destek", "guvenli", "hediye",
                 "yildiz", "kalp", "saat", "telefon", "kutu"}
MAX_LIST_ITEMS = 8
MAX_GALLERY_IMAGES = 12

# Hazır şablonların ortak örnek görselleri (app/sablon_gorselleri → depo;
# storage.sablon_gorsellerini_kur). Marka içermeyenler — mağaza değiştirir.
FZ = "/storage/sablon/fuzyon"

# Değeri sabit bir kümeye kısıtlanan ayarlar: (bölüm tipi, anahtar) → izinliler.
# İlki varsayılandır. Panel/elle düzenlenmiş config'ten gelen tanımsız değer
# vitrinde beklenmedik sınıf üretmesin diye varsayılana düşer.
_SECTION_ENUMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("hero_slider", "align"): ("center", "left"),
    ("hero_slider", "height"): ("normal", "tall"),
    ("hero_slider", "stil"): ("kaplama", "bolunmus"),
    ("featured_collections", "layout"): ("grid", "showcase", "kartlar"),
    ("products_grid", "layout"): ("grid", "carousel", "sekmeli"),
    ("featured_products", "layout"): ("grid", "carousel"),
    ("gallery", "aspect"): ("square", "story"),
    ("gallery", "mode"): ("scroll", "carousel", "marquee", "izgara"),
    ("image_with_text", "stil"): ("acik", "koyu"),
    ("faq", "stil"): ("tek", "iki_sutun"),
    ("icon_bar", "stil"): ("kart", "serit"),
    ("testimonials", "stil"): ("kart", "fotografli"),
    ("kurdele", "palet"): ("neon", "tema"),
}
# Başlık üçlüsü olan bölümlerde metin alanı uzunluk sınırları
_HEADING_LIMITS = {"eyebrow": 60, "title": 100, "subtitle": 200}

# Tema geneli görünüm seçenekleri (style.*) — ilki varsayılan
_STYLE_ENUMS: dict[str, tuple[str, ...]] = {
    # left: logo solda | center: logo ortada, menü altında | vitrin: logo
    # ortada, altında koyu "Koleksiyonlar" düğmesi + geniş arama çubuğu (Füzyon)
    "header_layout": ("left", "center", "vitrin"),
    "button_shape": ("rounded", "pill"),     # yuvarlatılmış köşe | tam yuvarlak
    # boxed: çerçeveli | minimal: çerçevesiz, ortalı | yumusak: yuvarlak gri
    # zeminli görsel, ad solda fiyat sağda
    "card_style": ("boxed", "minimal", "yumusak"),
    # compact: küçük sol | showcase: büyük ortalı | editoryal: büyük serif
    # başlık solda, açıklama sağda, satır satır yükselerek belirir
    "heading_style": ("compact", "showcase", "editoryal"),
    "header_sabit": ("hep", "mobil", "masaustu", "yok"),
    "footer_stil": ("sade", "genis"),        # tek satır | logolu, sütunlu
}
MAX_DUYURU = 8

# gorsel_kip (bölünmüş hero): sigdir (görsel kesilmeden, açık zemine karışır)
# | kapla (yuvarlak köşeli kart gibi doldurur)
_SLIDE_KEYS = {"image", "eyebrow", "title", "subtitle", "cta_text", "cta_url", "cta2_text",
               "cta2_url", "gorsel_kip"}

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
    # ust_not: vitrin üst menüsünde logonun solundaki küçük yazı;
    # ust_link_*: sağdaki yazı bağlantısı ("Sipariş takibi").
    # mobil_dock: telefonda altta sabit Keşfet/Tasarla/Favoriler/Sepet çubuğu.
    # ilerleme: sayfanın üstünde kaydırma ilerleme çizgisi.
    # akis_cizgisi: anasayfada kaydırdıkça çizilen renkli, halkalı çizgi.
    "style": {"header_layout": "left", "button_shape": "rounded",
              "card_style": "boxed", "heading_style": "compact", "scroll_top": False,
              "header_sabit": "hep", "footer_stil": "sade",
              "ust_not": "", "ust_link_metin": "", "ust_link_url": "",
              "mobil_dock": False, "ilerleme": False, "akis_cizgisi": False},
    # Açılış kampanya pop-up'ı — sayfa açılınca bir kez görünür (oturumda
    # tekrar çıkmaz). Marka-nötr: her mağaza kendi metnini/kupon kodunu yazar.
    # baslik/metin boşsa pop-up HİÇ gösterilmez (kapalı gibi davranır).
    # ust_baslik: başlığın üstündeki küçük etiket (örn. "✨ KAMPANYA ✨");
    # baslik'ta satır sonu korunur ("3 AL 2 ÖDE\n5 AL 3 ÖDE").
    # gorsel_boyut: pop-up görselinin (ör. logo) genişliği, % (30-100)
    "popup": {"enabled": False, "ust_baslik": "", "baslik": "", "metin": "", "kupon": "",
              "buton": "Alışverişe Başla", "gorsel_url": "", "gorsel_boyut": 100},
    # ── Kampanya araçları (eskiden "Özel Kod → Hazır ekle" ile HAM KOD olarak
    # ekleniyordu; metin/kupon/süre değiştirmek için kod düzenlemek gerekiyordu
    # ve aynı kod iki kez yapıştırılabiliyordu). Artık formla ayarlanır.
    # İndirim çarkı: ziyaretçi gecikme_sn sonra görür, çevirir, kupon kazanır.
    # dilimler: [{yazi, kod}] — kod boşsa "Tekrar dene" dilimi. 2-8 dilim.
    "cark": {"enabled": False, "baslik": "Şansını dene! 🎁",
             "metin": "Çarkı çevir, indirim kodunu kap.", "buton": "ÇEVİR",
             "gecikme_sn": 8, "tekrar_gun": 7,
             "dilimler": [
                 {"yazi": "%10 İNDİRİM", "kod": ""}, {"yazi": "Tekrar dene", "kod": ""},
                 {"yazi": "%15 İNDİRİM", "kod": ""}, {"yazi": "Ücretsiz Kargo", "kod": ""},
             ]},
    # Çıkışta yakala: masaüstünde imleç sayfadan çıkarken, mobilde
    # mobil_gecikme_sn sonra indirim teklifi. Kupon boşsa hiç gösterilmez.
    "cikis": {"enabled": False, "baslik": "Gitmeden önce… 🎁",
              "metin": "Bu siparişe özel indirim hazırladık.", "kupon": "",
              "buton": "Kodu Kullan", "vazgec": "Hayır, teşekkürler",
              "tekrar_gun": 3, "mobil_gecikme_sn": 45},
    "sections": [
        {"id": "varsayilan-hero", "type": "hero_slider",
         "settings": dict(SECTION_DEFAULTS["hero_slider"])},
        {"id": "varsayilan-koleksiyonlar", "type": "featured_collections",
         "settings": dict(SECTION_DEFAULTS["featured_collections"])},
        {"id": "varsayilan-urunler", "type": "products_grid",
         "settings": dict(SECTION_DEFAULTS["products_grid"])},
    ],
    # sepete_ucus: sepete ekleyince ürün görseli sepet simgesine uçar
    # hareket_tercihi: uy (ziyaretçinin "hareketi azalt" sistem ayarına uyulur —
    # Windows'ta "Animasyon efektleri" kapalıysa animasyonlar durur) |
    # her_zaman (her cihazda oynar; ziyaretçi footer'dan durdurabilir)
    "animations": {"reveal": True, "hover_zoom": True, "cart_drawer": True, "sepete_ucus": False,
                   "hareket_tercihi": "uy"},
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

# editoryal: gövde Inter, başlıklar Instrument Serif (ince, zarif serif)
FONT_PRESETS = {"inter", "poppins", "playfair", "dm-sans", "editoryal"}

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
    # ── Füzyon ── BERNZ "fusion" tasarım taslağından (2026-09) uyarlandı,
    # marka-NÖTR. Beyaz zemin, Instrument Serif başlıklar, koyu hap butonlar,
    # mavi vurgu. Üstte logo ortada + koyu "Koleksiyonlar" düğmesi ve geniş
    # arama; açık gri panolu bölünmüş hero; çapraz akan kurdeleler; stil
    # önerici; sekmeli ürünler; koyu editoryal pano; fotoğraflı yorumlar;
    # Instagram ızgarası; numaralı adımlar; canlı kılıf önizleme; iki
    # sütunlu SSS. Sayfa boyunca kaydırdıkça çizilen halkalı akış çizgisi ve
    # telefonda alt çubuk. {magaza} yazan yerlere mağaza adı gelir. Tasarımın
    # MARKASIZ görselleri örnek olarak gelir (FZ); BERNZ logolu ürün
    # fotoğrafları yalnız scripts/fuzyon_bernz_taslak.py ile. Uydurma yorum yok.
    "fuzyon": {
        "label": "Füzyon",
        "description": "Beyaz, editoryal ve hareketli: serif başlıklar, bölünmüş hero, "
                       "çapraz akan kurdeleler, stil önerici, canlı kılıf önizleme ve "
                       "kaydırdıkça çizilen akış çizgisi. Örnek görsellerle gelir.",
        "theme": {
            "colors": {"primary": "#191919", "accent": "#3d49ee", "bg": "#ffffff"},
            "font": "editoryal",
            "announcement": {"enabled": True, "bg": "#f1f1f1", "kayan": True, "items": [
                {"text": "{magaza}", "url": ""},
                {"text": "KENDİ KILIFINI TASARLA", "url": "/tasarla"},
                {"text": "HER TARZA BİR KOLEKSİYON", "url": "/urunler"},
            ]},
            "style": {"header_layout": "vitrin", "button_shape": "pill",
                      "card_style": "yumusak", "heading_style": "editoryal",
                      "header_sabit": "yok", "footer_stil": "genis", "scroll_top": False,
                      "ust_not": "SIRA DIŞI TASARIMLAR",
                      "ust_link_metin": "Siparişlerim", "ust_link_url": "/hesap",
                      "mobil_dock": True, "ilerleme": True, "akis_cizgisi": True},
            "popup": {"enabled": False},
            "animations": {"reveal": True, "hover_zoom": True, "cart_drawer": True, "sepete_ucus": True,
                           "hareket_tercihi": "her_zaman"},
            "sections": [
                {"id": "fz-hero", "type": "hero_slider",
                 "settings": {"stil": "bolunmus", "panel_renk": "#efefef", "autoplay_sec": 6,
                              "radius_scope": "both", "radius_pct": 50, "slides": [
                     {"image": f"{FZ}/hero-1.jpg", "eyebrow": "KİŞİYE ÖZEL BASKI",
                      "title": "Fotoğrafın,\nkılıfın olsun.",
                      "subtitle": "Görselini yükle, telefon modelini seç. Gerisini biz halledelim.",
                      "cta_text": "KENDİ KILIFINI OLUŞTUR", "cta_url": "/tasarla",
                      "cta2_text": "ya da hazır tasarımlara göz at", "cta2_url": "/urunler",
                      "gorsel_kip": "sigdir"},
                     {"image": f"{FZ}/hero-2.jpg", "eyebrow": "KOLEKSİYONLAR",
                      "title": "Her tarza\nbir kılıf.",
                      "subtitle": "Serilerimizden sana uyan tasarımı seç.",
                      "cta_text": "KOLEKSİYONU KEŞFET", "cta_url": "/urunler",
                      "cta2_text": "", "cta2_url": "", "gorsel_kip": "sigdir"},
                     {"image": f"{FZ}/koleksiyon.jpg", "eyebrow": "EDİTÖRÜN SEÇİMİ",
                      "title": "Editörün\nseçimi.",
                      "subtitle": "Sakin tonlarda, güçlü dokulu bir tasarım.",
                      "cta_text": "ÜRÜNÜ İNCELE", "cta_url": "/urunler",
                      "cta2_text": "", "cta2_url": "", "gorsel_kip": "kapla"},
                 ]}},
                {"id": "fz-hizmet", "type": "icon_bar",
                 "settings": {"stil": "serit", "items": [
                     {"icon": "kargo", "title": "Özenli paketleme",
                      "text": "Siparişin özenle hazırlanır", "url": ""},
                     {"icon": "konum", "title": "Sipariş takibi",
                      "text": "Kargon nerede, anında gör", "url": "/hesap"},
                     {"icon": "iade", "title": "İade ve değişim",
                      "text": "Koşulları önceden incele", "url": "/iade"},
                     {"icon": "eposta", "title": "Destek",
                      "text": "Sorularına hızlı yanıt", "url": ""},
                 ]}},
                {"id": "fz-kategori", "type": "featured_collections",
                 "settings": {"title": "Kategoriler", "slugs": [], "layout": "kartlar", "limit": 4,
                              "yedek_gorseller": [f"{FZ}/kendi-kilifini-tasarla.jpg", f"{FZ}/koleksiyon.jpg",
                                                  f"{FZ}/android.jpg", f"{FZ}/hero-1.jpg"]}},
                {"id": "fz-kurdele", "type": "kurdele",
                 "settings": {"palet": "neon", "sembol": "✦", "items": [
                     {"text": "KENDİ KILIFINI TASARLA", "buyuk": True},
                     {"text": "{magaza}", "buyuk": False},
                     {"text": "Tarzını yanında taşı", "buyuk": False},
                     {"text": "SIRA DIŞI TASARIMLAR", "buyuk": True},
                     {"text": "Yeni koleksiyon", "buyuk": False},
                     {"text": "Her tarza bir kılıf", "buyuk": False},
                 ]}},
                {"id": "fz-stil", "type": "stil_onerici",
                 "settings": {"eyebrow": "STİL ÖNERİCİ", "title": "Hangi tarz\nsana göre?",
                              "subtitle": "Birini seç, sana uygun tasarımı gösterelim.",
                              "secenekler": [
                     {"etiket": "Sakin & sanatsal", "renk": "#69778c", "kelime": "SANAT.",
                      "neden": "Sakin renkler. Güçlü bir bakış açısı.", "urun": "", "zemin": "#e5e8ed"},
                     {"etiket": "Cesur & hızlı", "renk": "#ce4444", "kelime": "HIZ.",
                      "neden": "Yarış ruhunu her gün yanında taşı.", "urun": "", "zemin": "#edc4c2"},
                     {"etiket": "Farklı & özgün", "renk": "#bba075", "kelime": "ÖZGÜN.",
                      "neden": "Herkesten farklı bir çizgin olsun.", "urun": "", "zemin": "#e6dfd2"},
                     {"etiket": "Tamamen bana özel", "renk": "#8871b4", "kelime": "SEN.",
                      "neden": "Bir anı, bir fotoğraf. Hikâye tamamen senin.", "urun": "",
                      "zemin": "#e3d7ed"},
                 ]}},
                {"id": "fz-urunler", "type": "products_grid", "akis": True,
                 "settings": {"eyebrow": "KOLEKSİYON", "title": "Öne çıkan tasarımlar",
                              "subtitle": "Serilerimizden en çok bakılanlar.",
                              "collection": None, "limit": 8, "layout": "sekmeli", "sekmeler": []}},
                {"id": "fz-imza", "type": "image_with_text", "akis": True,
                 "settings": {"stil": "koyu", "eyebrow": "İMZA SERİ", "title": "İmza tasarımımız",
                              "body": "Serimizin en sevilen tasarımını yakından tanı.",
                              "cta_text": "Koleksiyonu keşfet", "cta_url": "/urunler",
                              "image": f"{FZ}/kendi-kilifini-tasarla.jpg", "image_side": "left",
                              "gorsel_notu": ""}},
                {"id": "fz-yorumlar", "type": "testimonials",
                 "settings": {"stil": "fotografli", "eyebrow": "MÜŞTERİ FOTOĞRAFLARI",
                              "title": "Siparişlerden gelen fotoğraflar",
                              "subtitle": "Müşterilerimizin sipariş sonrası paylaştığı yorumlar ve fotoğraflar.",
                              "items": [], "alt_not": "Daha fazlası Instagram'da."}},
                {"id": "fz-instagram", "type": "gallery",
                 "settings": {"eyebrow": "INSTAGRAM", "title": "Instagram'dan", "subtitle": "",
                              "ogeler": [{"url": f"{FZ}/{ad}.jpg"} for ad in (
                                  "kendi-kilifini-tasarla", "koleksiyon", "hero-1", "android", "instagram-dikey")],
                              "images": [], "aspect": "story", "mode": "izgara",
                              "baglanti": "", "baglanti_metni": "Takip et"}},
                {"id": "fz-adimlar", "type": "adimlar", "akis": True,
                 "settings": {"eyebrow": "KİŞİYE ÖZEL", "title": "Kendi kılıfını\n3 adımda tasarla.",
                              "items": [
                     {"title": "Görselini seç.",
                      "text": "Bir fotoğraf, bir çizim ya da bir yazı; ne istersen.", "url": "/tasarla"},
                     {"title": "Baskıya hazırlıyoruz.",
                      "text": "Tasarımın özenle basılır ve paketlenir.", "url": ""},
                     {"title": "Kargonu takip et.",
                      "text": "Siparişinin nerede olduğunu tek yerden gör.", "url": "/hesap"},
                 ]}},
                {"id": "fz-onizleme", "type": "kilif_onizleme",
                 "settings": {"eyebrow": "CANLI ÖNİZLEME",
                              "title": "Fotoğrafını seç,\nkılıfını hemen gör.",
                              "subtitle": "Fotoğrafın yalnızca bu ekranda kalır, hiçbir yere "
                                          "yüklenmez. Sürükle, yakınlaştır, modelini seç.",
                              "buton": "FOTOĞRAF SEÇ", "cta_text": "Bu tasarımla sipariş ver",
                              "cta_url": "/tasarla", "logo_yazi": "{magaza}"}},
                {"id": "fz-son", "type": "son_bakilanlar",
                 "settings": {"eyebrow": "SON BAKTIKLARIN", "title": "Son baktığın tasarımlar"}},
                {"id": "fz-sss", "type": "faq",
                 "settings": {"stil": "iki_sutun", "eyebrow": "YARDIM",
                              "title": "Sık sorulan sorular",
                              "subtitle": "Cevabını bulamadığın bir soru olursa bize yaz, yardımcı olalım.",
                              "eposta": "", "items": [
                     {"q": "Telefonuma uygun modeli nasıl seçerim?",
                      "a": "Ürün sayfasındaki model listesinden telefonunu seç. Tam model adını "
                           "cihaz ayarlarındaki \u201cHakkında\u201d bölümünde bulabilirsin."},
                     {"q": "Kendi görselimle kılıf tasarlayabilir miyim?",
                      "a": "Evet. Tasarım sayfasında görselini yükle ve telefon modelini seç, "
                           "gerisini biz hazırlayalım."},
                     {"q": "Siparişimi nereden takip ederim?",
                      "a": "Sipariş onayı e-postandaki bağlantıdan ya da Hesabım sayfasından "
                           "siparişinin durumunu görebilirsin."},
                     {"q": "İade ve değişim koşulları neler?",
                      "a": "Koşullarımızı İade ve Değişim sayfamızda bulabilirsin. Kişiye özel "
                           "ürünlerle ilgili soruların için bize yazabilirsin."},
                 ]}},
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


def _renk(v, varsayilan: str = "") -> str:
    v = str(v or "").strip()
    return v if re.fullmatch(r"#[0-9a-fA-F]{6}", v) else varsayilan


def _metin(v, limit: int) -> str:
    return str(v or "").strip()[:limit]


def _sinirli_sayi(v, alt: int, ust: int, varsayilan: int) -> int:
    try:
        return min(ust, max(alt, int(v)))
    except (TypeError, ValueError):
        return varsayilan


def _kupon_kodu(v) -> str:
    """Kupon kodu: kuponlar büyük harfle saklanır (bkz. apply_discount)."""
    return "".join(str(v or "").split()).upper()[:40]


def _cark_temizle(c: dict) -> dict:
    v = DEFAULT_THEME["cark"]
    dilimler = [
        {"yazi": str(d.get("yazi") or "").strip()[:24], "kod": _kupon_kodu(d.get("kod"))}
        for d in (c.get("dilimler") or [])[:8]
        if isinstance(d, dict) and str(d.get("yazi") or "").strip()
    ]
    return {
        "enabled": bool(c.get("enabled")),
        "baslik": str(c.get("baslik") or "").strip()[:60] or v["baslik"],
        "metin": str(c.get("metin") or "").strip()[:140],
        "buton": str(c.get("buton") or "").strip()[:24] or v["buton"],
        "gecikme_sn": _sinirli_sayi(c.get("gecikme_sn"), 0, 120, v["gecikme_sn"]),
        "tekrar_gun": _sinirli_sayi(c.get("tekrar_gun"), 1, 60, v["tekrar_gun"]),
        # En az 2 dilim; biri bile kuponlu değilse çark anlamsız → vitrin göstermez
        "dilimler": dilimler if len(dilimler) >= 2 else copy.deepcopy(v["dilimler"]),
    }


def _cikis_temizle(c: dict) -> dict:
    v = DEFAULT_THEME["cikis"]
    return {
        "enabled": bool(c.get("enabled")),
        "baslik": str(c.get("baslik") or "").strip()[:60] or v["baslik"],
        "metin": str(c.get("metin") or "").strip()[:200],
        "kupon": _kupon_kodu(c.get("kupon")),
        "buton": str(c.get("buton") or "").strip()[:30] or v["buton"],
        "vazgec": str(c.get("vazgec") or "").strip()[:40] or v["vazgec"],
        "tekrar_gun": _sinirli_sayi(c.get("tekrar_gun"), 1, 60, v["tekrar_gun"]),
        "mobil_gecikme_sn": _sinirli_sayi(c.get("mobil_gecikme_sn"), 5, 600, v["mobil_gecikme_sn"]),
    }


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
            for sl in settings["slides"]:
                if sl.get("gorsel_kip") not in ("sigdir", "kapla"):
                    sl["gorsel_kip"] = "sigdir"
            settings["panel_renk"] = _renk(settings.get("panel_renk"), "#efefef")
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
                settings["yedek_gorseller"] = [
                    u for u in (_metin(x, 500) for x in (settings.get("yedek_gorseller") or [])[:12])
                    if u.startswith("/storage/") or u.startswith("https://")]
        elif stype == "products_grid":
            try:
                settings["limit"] = min(24, max(1, int(settings.get("limit") or 8)))
            except (TypeError, ValueError):
                settings["limit"] = 8
            settings["sekmeler"] = [str(x)[:200] for x in (settings.get("sekmeler") or [])
                                    if isinstance(x, str) and x][:6]
        elif stype == "image_with_text":
            if settings.get("image_side") not in ("left", "right"):
                settings["image_side"] = "left"
            settings["gorsel_notu"] = _metin(settings.get("gorsel_notu"), 80)
        elif stype == "faq":
            settings["items"] = [
                {"q": str((i or {}).get("q") or "")[:300],
                 "a": str((i or {}).get("a") or "")[:2000]}
                for i in (settings.get("items") or [])[:MAX_FAQ_ITEMS]
                if isinstance(i, dict) and (i.get("q") or i.get("a"))
            ]
            settings["eposta"] = _metin(settings.get("eposta"), 120)
        elif stype == "icon_bar":
            settings["items"] = [
                {"icon": str((i or {}).get("icon") or "✨")[:8],
                 "title": str((i or {}).get("title") or "")[:80],
                 "text": str((i or {}).get("text") or "")[:200],
                 "url": _guvenli_link((i or {}).get("url")) or (
                     _metin((i or {}).get("url"), 120)
                     if str((i or {}).get("url") or "").startswith("mailto:") else "")}
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
                img = _metin(i.get("image"), 500)
                cleaned_items.append({
                    "author": str(i.get("author") or "Müşteri")[:80],
                    "text": str(i.get("text") or "")[:600],
                    "rating": rating,
                    # Fotoğraflı stil için (ops.) — yalnız kendi deposu ya da https
                    "image": img if img.startswith("/storage/") or img.startswith("https://") else "",
                })
            settings["items"] = cleaned_items
            settings["alt_not"] = _metin(settings.get("alt_not"), 120)
        elif stype == "gallery":
            ham = settings.get("ogeler") or [
                {"url": u} for u in (settings.get("images") or []) if u]
            settings["ogeler"] = [o for o in (_galeri_ogesi(x) for x in ham) if o][:MAX_GALLERY_IMAGES]
            settings["images"] = [o["url"] for o in settings["ogeler"]]
            settings["baglanti"] = _guvenli_link(settings.get("baglanti"))
            settings["baglanti_metni"] = _metin(settings.get("baglanti_metni"), 40)
        elif stype == "kurdele":
            settings["items"] = [
                {"text": _metin(i.get("text"), 60), "buyuk": bool(i.get("buyuk"))}
                for i in (settings.get("items") or [])[:10]
                if isinstance(i, dict) and _metin(i.get("text"), 60)
            ]
            settings["sembol"] = _metin(settings.get("sembol"), 4) or "✦"
        elif stype == "stil_onerici":
            settings["secenekler"] = [
                {"etiket": _metin(o.get("etiket"), 40),
                 "renk": _renk(o.get("renk"), "#888888"),
                 "kelime": _metin(o.get("kelime"), 14),
                 "neden": _metin(o.get("neden"), 120),
                 "urun": _metin(o.get("urun"), 200),
                 "zemin": _renk(o.get("zemin"), "#e5e8ed")}
                for o in (settings.get("secenekler") or [])[:6]
                if isinstance(o, dict) and _metin(o.get("etiket"), 40)
            ]
        elif stype == "adimlar":
            settings["items"] = [
                {"title": _metin(i.get("title"), 80), "text": _metin(i.get("text"), 200),
                 "url": _guvenli_link(i.get("url"))}
                for i in (settings.get("items") or [])[:6]
                if isinstance(i, dict) and _metin(i.get("title"), 80)
            ]
        elif stype == "kilif_onizleme":
            for key, limit in (("buton", 30), ("cta_text", 40), ("logo_yazi", 24), ("not", 140)):
                settings[key] = _metin(settings.get(key), limit)
            settings["buton"] = settings["buton"] or "FOTOĞRAF SEÇ"
            settings["cta_url"] = _guvenli_link(settings.get("cta_url")) or "/tasarla"
        cleaned.append({
            "id": str(sec.get("id") or uuid.uuid4().hex[:8])[:40],
            "type": stype,
            "settings": settings,
            # Gizle/göster: silmeden kapatma (Shopify eye toggle)
            "hidden": bool(sec.get("hidden")),
            # Zemin şeması: none (sayfa zemini) | band (beyaz bant)
            "scheme": sec.get("scheme") if sec.get("scheme") in ("none", "band") else "none",
            # Akış çizgisi bu bölümün üstünden geçsin (style.akis_cizgisi açıkken)
            "akis": bool(sec.get("akis")),
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
    for key in ("scroll_top", "mobil_dock", "ilerleme", "akis_cizgisi"):
        style[key] = bool(style.get(key))
    style["ust_not"] = _metin(style.get("ust_not"), 40)
    style["ust_link_metin"] = _metin(style.get("ust_link_metin"), 30)
    style["ust_link_url"] = _guvenli_link(style.get("ust_link_url"))
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
    anim = theme.get("animations") if isinstance(theme.get("animations"), dict) else {}
    if anim.get("hareket_tercihi") not in ("uy", "her_zaman"):
        anim["hareket_tercihi"] = "uy"
    theme["animations"] = anim
    theme["cark"] = _cark_temizle(theme.get("cark") or {})
    theme["cikis"] = _cikis_temizle(theme.get("cikis") or {})
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
    for key in ("colors", "announcement", "popup", "style", "cark", "cikis", "animations", "footer", "whatsapp",
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
