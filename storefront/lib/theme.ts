// Vitrin teması — backend'ten çekilir (60 sn revalidate), defaults fallback.
import "server-only";
import { getStoreSlug } from "./api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export interface HeroSlide {
  image: string | null;
  title: string;
  subtitle: string;
  cta_text: string;
  cta_url: string;
}

export interface ThemeSection {
  id: string;
  type: "hero_slider" | "featured_collections" | "products_grid" | "rich_text" | "banner";
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
  };
}

export interface Theme {
  version: number;
  colors: { primary: string; accent: string; bg: string };
  font: "inter" | "poppins" | "playfair" | "dm-sans";
  logo_url: string | null;
  favicon_url: string | null;
  announcement: { enabled: boolean; text: string; url: string };
  sections: ThemeSection[];
  animations: { reveal: boolean; hover_zoom: boolean; cart_drawer: boolean };
  footer: { about: string; instagram: string };
}

export interface ThemePayload {
  store_name: string;
  theme: Theme;
  settings: Record<string, string | null>;
  contact: { email: string | null; phone: string | null; instagram: string | null };
  pixels?: { meta: string | null; ga4: string | null; tiktok: string | null };
  pages?: { slug: string; title: string }[];
  custom_code?: { head_html?: string; css?: string; body_html?: string } | null;
  active_promotion?: { label: string; kind: string; min_subtotal: string | null } | null;
  has_blog?: boolean;
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

export async function getThemePayload(): Promise<ThemePayload> {
  try {
    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/theme`, {
      next: { revalidate: 60 },
    });
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
    return payload;
  } catch {
    return DEFAULT_PAYLOAD; // backend erişilemezse varsayılan temayla render
  }
}
