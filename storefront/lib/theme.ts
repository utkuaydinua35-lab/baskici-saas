// Vitrin teması — backend'ten çekilir (60 sn revalidate), defaults fallback.
// Önizleme çerezi (canlı tema editörü) varsa taslak tema önbelleksiz gelir.
import "server-only";
import { cookies } from "next/headers";
import { getStoreSlug } from "./api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export interface HeroSlide {
  image: string | null;
  title: string;
  subtitle: string;
  cta_text: string;
  cta_url: string;
  cta2_text?: string;
  cta2_url?: string;
}

export interface ThemeSection {
  id: string;
  hidden?: boolean;
  scheme?: "none" | "band";
  type: "hero_slider" | "featured_collections" | "products_grid" | "featured_products"
    | "rich_text" | "banner" | "image_with_text" | "faq" | "newsletter"
    | "icon_bar" | "comparison" | "testimonials" | "gallery" | "contact" | "countdown";
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
      author?: string; rating?: number }[];
    subtitle?: string;
    us_label?: string;
    them_label?: string;
    rows?: { feature: string; us: boolean; them: boolean }[];
    images?: string[];
    ends_at?: string;
    radius_scope?: "both" | "mobile" | "desktop" | "none";
    radius_pct?: number;
  };
}

export interface Theme {
  version: number;
  colors: { primary: string; accent: string; bg: string };
  font: "inter" | "poppins" | "playfair" | "dm-sans";
  logo_url: string | null;
  logo_width?: number;
  favicon_url: string | null;
  announcement: { enabled: boolean; text: string; url: string };
  sections: ThemeSection[];
  animations: { reveal: boolean; hover_zoom: boolean; cart_drawer: boolean };
  texts?: Record<string, string>;
  footer: { about: string; instagram: string };
  nav_links?: { label: string; url?: string; type?: string; slugs?: string[] }[];
  whatsapp?: { enabled: boolean; number: string; message: string };
  trust_badges?: { enabled: boolean };
  cart_messages?: { bxgy_progress: string; bxgy_reached: string };
  thankyou?: { title?: string; message?: string };
}

export interface ThemePayload {
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
  legal: { kvkk: string | null; mesafeli_satis: string | null; iade: string | null };
}

const DEFAULT_PAYLOAD: ThemePayload = {
  store_name: process.env.SITE_NAME || "Bernz",
  theme: {
    version: 2,
    colors: { primary: "#18181b", accent: "#f59e0b", bg: "#fafafa" },
    font: "inter",
    logo_url: null,
    favicon_url: null,
    announcement: { enabled: false, text: "", url: "" },
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
};

export async function getThemePayload(): Promise<ThemePayload & { is_preview?: boolean }> {
  try {
    const slug = await getStoreSlug();
    let preview = false;
    try {
      preview = (await cookies()).get("vitrin_onizleme")?.value === "1";
    } catch { /* statik render */ }
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${slug}/theme${preview ? "?preview=1" : ""}`,
      preview ? { cache: "no-store" } : { next: { revalidate: 60 } },
    );
    if (!res.ok) return DEFAULT_PAYLOAD;
    const payload = (await res.json()) as ThemePayload;
    // Şema koruması: eski önbellek/eksik alan sayfayı düşürmesin
    if (!Array.isArray(payload.theme?.sections)) {
      payload.theme = { ...DEFAULT_PAYLOAD.theme, ...payload.theme, sections: DEFAULT_PAYLOAD.theme.sections };
    }
    payload.theme.animations = { ...DEFAULT_PAYLOAD.theme.animations, ...payload.theme.animations };
    payload.theme.colors = { ...DEFAULT_PAYLOAD.theme.colors, ...payload.theme.colors };
    payload.theme.announcement = { ...DEFAULT_PAYLOAD.theme.announcement, ...payload.theme.announcement };
    payload.theme.footer = { ...DEFAULT_PAYLOAD.theme.footer, ...payload.theme.footer };
    return { ...payload, is_preview: preview };
  } catch {
    return DEFAULT_PAYLOAD; // backend erişilemezse varsayılan temayla render
  }
}
