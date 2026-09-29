// Vitrin teması — backend'ten çekilir (60 sn revalidate), defaults fallback.
// Önizleme çerezi (canlı tema editörü) varsa taslak tema önbelleksiz gelir.
import "server-only";
import { cookies } from "next/headers";
import { getStoreSlug } from "./api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export interface HeroSlide {
  image: string | null;
  eyebrow?: string;
  title: string;
  subtitle: string;
  cta_text: string;
  cta_url: string;
  cta2_text?: string;
  cta2_url?: string;
  // Bölünmüş hero: sigdir (kesilmeden; beyaz/pano renkli zemin panoya karışır —
  // mix-blend darken) | kapla (yuvarlak kart)
  gorsel_kip?: "sigdir" | "kapla";
}

export interface ThemeSection {
  id: string;
  hidden?: boolean;
  scheme?: "none" | "band";
  // Akış çizgisi bu bölümün üstünden geçsin (style.akis_cizgisi açıkken)
  akis?: boolean;
  type: "hero_slider" | "featured_collections" | "products_grid" | "featured_products"
    | "rich_text" | "banner" | "image_with_text" | "faq" | "newsletter"
    | "icon_bar" | "comparison" | "testimonials" | "gallery" | "contact" | "countdown"
    | "kurdele" | "stil_onerici" | "adimlar" | "kilif_onizleme" | "son_bakilanlar";
  settings: {
    slides?: HeroSlide[];
    autoplay_sec?: number;
    title?: string;
    slugs?: string[];
    collection?: string | null;
    limit?: number;
    body?: string;
    image?: string | null;
    url?: string;
    cta_text?: string;
    cta_url?: string;
    image_side?: string;
    items?: { q?: string; a?: string; icon?: string; title?: string; text?: string;
      author?: string; rating?: number; image?: string; url?: string; buyuk?: boolean }[];
    subtitle?: string;
    us_label?: string;
    them_label?: string;
    rows?: { feature: string; us: boolean; them: boolean }[];
    images?: string[];
    ogeler?: { url: string; tip?: "gorsel" | "video"; link?: string; etiket?: string }[];
    ends_at?: string;
    radius_scope?: "both" | "mobile" | "desktop" | "none";
    radius_pct?: number;
    // Başlık üçlüsü (üst etiket / başlık / alt başlık)
    eyebrow?: string;
    // Düzen seçenekleri — değerler backend'de kısıtlanır (_SECTION_ENUMS)
    layout?: "grid" | "showcase" | "carousel" | "kartlar" | "sekmeli";
    align?: "center" | "left";
    height?: "normal" | "tall";
    aspect?: "square" | "story";
    mode?: "scroll" | "carousel" | "marquee" | "izgara";
    // Füzyon seçenekleri
    stil?: string;               // bölüm tipine göre (backend _SECTION_ENUMS)
    panel_renk?: string;
    sekmeler?: string[];
    yedek_gorseller?: string[];
    gorsel_notu?: string;
    eposta?: string;
    alt_not?: string;
    baglanti?: string;
    baglanti_metni?: string;
    sembol?: string;
    palet?: "neon" | "tema";
    secenekler?: { etiket: string; renk: string; kelime: string; neden: string;
      urun: string; zemin: string }[];
    buton?: string;
    logo_yazi?: string;
    not?: string;
  };
}

// Tema geneli görünüm (backend _STYLE_ENUMS)
export interface ThemeStyle {
  header_layout: "left" | "center" | "vitrin";
  button_shape: "rounded" | "pill";
  card_style: "boxed" | "minimal" | "yumusak";
  heading_style: "compact" | "showcase" | "editoryal";
  scroll_top: boolean;
  header_sabit?: "hep" | "mobil" | "masaustu" | "yok";
  footer_stil?: "sade" | "genis";
  ust_not?: string;
  ust_link_metin?: string;
  ust_link_url?: string;
  mobil_dock?: boolean;
  ilerleme?: boolean;
  akis_cizgisi?: boolean;
}

export interface Theme {
  version: number;
  colors: { primary: string; accent: string; bg: string };
  font: "inter" | "poppins" | "playfair" | "dm-sans" | "editoryal";
  logo_url: string | null;
  logo_width?: number;
  logo_width_mobile?: number | null;
  favicon_url: string | null;
  announcement: { enabled: boolean; text: string; url: string; bg?: string;
    items?: { text: string; url?: string }[]; kayan?: boolean };
  style: ThemeStyle;
  // Kampanya araçları (eskiden ham kod parçacığı)
  cark?: { enabled: boolean; baslik: string; metin: string; buton: string;
    gecikme_sn: number; tekrar_gun: number; dilimler: { yazi: string; kod: string }[] };
  cikis?: { enabled: boolean; baslik: string; metin: string; kupon: string; buton: string;
    vazgec: string; tekrar_gun: number; mobil_gecikme_sn: number };
  popup: { enabled: boolean; ust_baslik?: string; gorsel_boyut?: number; baslik: string; metin: string; kupon: string; buton: string; gorsel_url: string };
  sections: ThemeSection[];
  // sepete_ucus: sepete ekleyince ürün görseli sepet simgesine uçar
  animations: { reveal: boolean; hover_zoom: boolean; cart_drawer: boolean; sepete_ucus?: boolean };
  texts?: Record<string, string>;
  collection_pages?: Record<string, { image?: string | null; body?: string; position?: string }>;
  footer: { about: string; instagram: string };
  nav_links?: { label: string; url?: string; type?: string; slugs?: string[] }[];
  whatsapp?: { enabled: boolean; number: string; message: string };
  trust_badges?: { enabled: boolean };
  cart_messages?: { bxgy_progress: string; bxgy_reached: string };
  thankyou?: { title?: string; message?: string };
}

export interface ThemePayload {
  // Kiralama: kiracının aboneliği askıya düştüyse backend 503 +
  // "vitrin_bakimda" döner; kök düzen tüm siteyi bakım ekranına çevirir.
  bakimda?: boolean;
  store_name: string;
  theme: Theme;
  settings: Record<string, string | null>;
  contact: { email: string | null; phone: string | null; instagram: string | null };
  pixels?: { meta: string | null; ga4: string | null; tiktok: string | null };
  pages?: { slug: string; title: string }[];
  custom_code?: { head_html?: string; css?: string; body_html?: string } | null;
  active_promotion?: { label: string; kind: string; min_subtotal: string | null;
    buy_x?: number | null; pay_y?: number | null } | null;
  active_promotions?: { label: string; kind: string; min_subtotal: string | null;
    buy_x?: number | null; pay_y?: number | null }[] | null;
  has_blog?: boolean;
  password_protected?: boolean;
  support?: { enabled: boolean; faq: { q: string; a: string }[] } | null;
  legal: { kvkk: string | null; mesafeli_satis: string | null; iade: string | null };
  // İşletme bilgileri — BOŞ gelirse ilgili cümle HİÇ yazılmaz. Eskiden
  // BERNZ'in taahhütleri (teslim süresi, iade istisnası) koda sabitti ve
  // her yeni mağazaya aynen gidiyordu.
  isletme: {
    urun_turu: string | null;
    tanitim: string | null;
    teslim_suresi: string | null;
    kisiye_ozel: boolean;
  };
}

const DEFAULT_PAYLOAD: ThemePayload = {
  // Mağaza adı backend'den gelir; bu yalnız backend erişilemezken
  // görünen NÖTR yedektir — buraya marka adı yazılmaz.
  store_name: "Mağaza",
  theme: {
    version: 2,
    colors: { primary: "#18181b", accent: "#f59e0b", bg: "#fafafa" },
    font: "inter",
    logo_url: null,
    favicon_url: null,
    announcement: { enabled: false, text: "", url: "", bg: "" },
    style: { header_layout: "left", button_shape: "rounded", card_style: "boxed",
      heading_style: "compact", scroll_top: false },
    popup: { enabled: false, ust_baslik: "", baslik: "", metin: "", kupon: "", buton: "Alışverişe Başla", gorsel_url: "" },
    sections: [
      { id: "d-hero", type: "hero_slider", settings: { slides: [], autoplay_sec: 5 } },
      { id: "d-kol", type: "featured_collections", settings: { title: "Koleksiyonlar", slugs: [] } },
      { id: "d-urun", type: "products_grid", settings: { title: "Öne Çıkanlar", collection: null, limit: 8 } },
    ],
    animations: { reveal: true, hover_zoom: true, cart_drawer: true },
    footer: { about: "", instagram: "" },
  },
  settings: {},
  contact: { email: null, phone: null, instagram: null },
  legal: { kvkk: null, mesafeli_satis: null, iade: null },
  isletme: { urun_turu: null, tanitim: null, teslim_suresi: null, kisiye_ozel: false },
};

// Hazır şablon metinlerindeki {magaza} yer tutucusu → mağazanın adı
// ("{magaza} SPECIAL", kurdele yazıları, kılıf üstündeki logo yazısı…).
// Şablon marka-nötr kalır, her mağazada kendi adı görünür.
function magazaAdiniYerlestir(theme: Theme, ad: string): Theme {
  const ham = JSON.stringify(theme);
  if (!ham.includes("{magaza}")) return theme;
  // JSON dizesi içine güvenli gömme (tırnak, ters bölü kaçışlı)
  const kacisli = JSON.stringify(ad || "").slice(1, -1);
  // Fonksiyonla: dize verilseydi addaki "$&" gibi kalıplar özel anlam taşırdı
  return JSON.parse(ham.replaceAll("{magaza}", () => kacisli)) as Theme;
}

export async function getThemePayload(): Promise<ThemePayload & { is_preview?: boolean }> {
  try {
    const slug = await getStoreSlug();
    let preview = false;
    try {
      // Çerez VEYA middleware'in eklediği header (ilk istekte çerez yoktur)
      const { headers } = await import("next/headers");
      preview = (await cookies()).get("vitrin_onizleme")?.value === "1"
        || (await headers()).get("x-vitrin-onizleme") === "1";
    } catch { /* statik render */ }
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${slug}/theme${preview ? "?preview=1" : ""}`,
      // tags: panel "Kaydet ve Yayınla" sonrası /api/revalidate-theme bu
      // cache'i anında düşürür — 60 sn eski tema görünmesin
      preview ? { cache: "no-store" } : { next: { revalidate: 60, tags: ["theme"] } },
    );
    if (res.status === 503) {
      // Yalnız ABONELİK kaynaklı 503 bakım ekranıdır; sunucunun kendisi
      // çökmüşse (başka bir 503) eski davranış — varsayılan tema.
      const govde = await res.json().catch(() => null);
      if (govde?.detail === "vitrin_bakimda") return { ...DEFAULT_PAYLOAD, bakimda: true };
    }
    if (!res.ok) return DEFAULT_PAYLOAD;
    const payload = (await res.json()) as ThemePayload;
    // Şema koruması: eski önbellek/eksik alan sayfayı düşürmesin
    if (!Array.isArray(payload.theme?.sections)) {
      payload.theme = { ...DEFAULT_PAYLOAD.theme, ...payload.theme, sections: DEFAULT_PAYLOAD.theme.sections };
    }
    payload.theme.animations = { ...DEFAULT_PAYLOAD.theme.animations, ...payload.theme.animations };
    payload.theme.colors = { ...DEFAULT_PAYLOAD.theme.colors, ...payload.theme.colors };
    payload.theme.announcement = { ...DEFAULT_PAYLOAD.theme.announcement, ...payload.theme.announcement };
    payload.theme.popup = { ...DEFAULT_PAYLOAD.theme.popup, ...(payload.theme.popup || {}) };
    payload.theme.style = { ...DEFAULT_PAYLOAD.theme.style, ...(payload.theme.style || {}) };
    payload.theme.footer = { ...DEFAULT_PAYLOAD.theme.footer, ...payload.theme.footer };
    // Eski sunucu/önbellek isletme göndermiyorsa sayfa çökmesin
    payload.isletme = { ...DEFAULT_PAYLOAD.isletme, ...(payload.isletme || {}) };
    payload.theme = magazaAdiniYerlestir(payload.theme, payload.store_name);
    return { ...payload, is_preview: preview };
  } catch {
    return DEFAULT_PAYLOAD; // backend erişilemezse varsayılan temayla render
  }
}
