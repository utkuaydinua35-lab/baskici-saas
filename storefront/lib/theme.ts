// Vitrin teması — backend'ten çekilir (60 sn revalidate), defaults fallback.
import "server-only";
import { getStoreSlug } from "./api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export interface Theme {
  version: number;
  colors: { primary: string; accent: string; bg: string };
  font: "inter" | "poppins" | "playfair" | "dm-sans";
  logo_url: string | null;
  favicon_url: string | null;
  announcement: { enabled: boolean; text: string; url: string };
  hero: {
    enabled: boolean;
    image: string | null;
    title: string;
    subtitle: string;
    cta_text: string;
    cta_url: string;
  };
  featured_collections: string[];
  sections_order: string[];
  animations: { reveal: boolean; hover_zoom: boolean; cart_drawer: boolean };
  footer: { about: string; instagram: string };
}

export interface ThemePayload {
  store_name: string;
  theme: Theme;
  settings: Record<string, string | null>;
  contact: { email: string | null; phone: string | null; instagram: string | null };
  legal: { kvkk: string | null; mesafeli_satis: string | null; iade: string | null };
}

const DEFAULT_PAYLOAD: ThemePayload = {
  store_name: process.env.SITE_NAME || "Bernz",
  theme: {
    version: 1,
    colors: { primary: "#18181b", accent: "#f59e0b", bg: "#fafafa" },
    font: "inter",
    logo_url: null,
    favicon_url: null,
    announcement: { enabled: false, text: "", url: "" },
    hero: { enabled: false, image: null, title: "", subtitle: "", cta_text: "", cta_url: "/urunler" },
    featured_collections: [],
    sections_order: ["hero", "featured", "products"],
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
    return (await res.json()) as ThemePayload;
  } catch {
    return DEFAULT_PAYLOAD; // backend erişilemezse varsayılan temayla render
  }
}
