// Tasarım stüdyosu font seti — hepsi ticari kullanıma açık (SIL OFL / Apache 2.0)
// ve KENDİ SUNUCUMUZDA barındırılıyor. Aynı .ttf dosyaları backend/app/fonts'ta da
// var: baskıya hazır dosya sunucuda üretilirken müşterinin ekranda gördüğü yazı
// tipiyle birebir aynısı kullanılır (dış CDN'e bağımlılık da yok).
//
// tr:false olan fontlarda ğ Ğ ş Ş İ gibi harflerin GLYPH'İ YOK — editör bu
// harfler yazıldığında uyarır (baskıda boş kutu çıkmasın diye).
export interface StudioFont {
  key: string;
  label: string;
  file: string;
  css: string;      // font-family adı
  lisans: string;
  grup: "Klasik" | "Sokak" | "El yazısı" | "Retro";
  tr?: boolean;     // Türkçe karakterlerin tamamı var mı (varsayılan: evet)
  eksik?: string[]; // tr:false ise fontta glyph'i OLMAYAN harfler
}

export const FONTS: StudioFont[] = [
  // ── Klasik / okunaklı ──
  { key: "poppins", label: "Poppins", file: "Poppins-SemiBold", css: "Poppins", lisans: "OFL", grup: "Klasik" },
  { key: "montserrat", label: "Montserrat", file: "Montserrat-Bold", css: "Montserrat", lisans: "OFL", grup: "Klasik" },
  { key: "playfair", label: "Playfair", file: "PlayfairDisplay-Bold", css: "Playfair Display", lisans: "OFL", grup: "Klasik" },
  { key: "bebas", label: "Bebas Neue", file: "BebasNeue-Regular", css: "Bebas Neue", lisans: "OFL", grup: "Klasik" },
  { key: "oswald", label: "Oswald", file: "Oswald-SemiBold", css: "Oswald", lisans: "OFL", grup: "Klasik" },
  { key: "anton", label: "Anton", file: "Anton-Regular", css: "Anton", lisans: "OFL", grup: "Klasik" },
  { key: "staatliches", label: "Staatliches", file: "Staatliches-Regular", css: "Staatliches", lisans: "OFL", grup: "Klasik" },
  { key: "russo", label: "Russo One (forma)", file: "RussoOne-Regular", css: "Russo One", lisans: "OFL", grup: "Klasik" },
  { key: "mono", label: "Daktilo", file: "RobotoMono-Medium", css: "Roboto Mono", lisans: "Apache 2.0", grup: "Klasik" },

  // ── Sokak / gangsta / poster ──
  { key: "gotik", label: "Gotik (Gangsta)", file: "UnifrakturCook-Bold", css: "UnifrakturCook", lisans: "OFL", grup: "Sokak", tr: false, eksik: ["ğ", "Ğ", "ı", "İ", "ş", "Ş"] },
  { key: "pirata", label: "Gotik İnce", file: "PirataOne-Regular", css: "Pirata One", lisans: "OFL", grup: "Sokak" },
  { key: "bangers", label: "Çizgi Roman", file: "Bangers-Regular", css: "Bangers", lisans: "OFL", grup: "Sokak" },
  { key: "marker", label: "Marker", file: "PermanentMarker-Regular", css: "Permanent Marker", lisans: "Apache 2.0", grup: "Sokak", tr: false, eksik: ["ğ", "Ğ", "İ", "ş", "Ş"] },
  { key: "sprey", label: "Sprey", file: "RockSalt-Regular", css: "Rock Salt", lisans: "Apache 2.0", grup: "Sokak", tr: false, eksik: ["ğ", "Ğ", "İ", "ş", "Ş"] },
  { key: "bungee", label: "Tabela", file: "Bungee-Regular", css: "Bungee", lisans: "OFL", grup: "Sokak" },
  { key: "alfaslab", label: "Kalın Serif", file: "AlfaSlabOne-Regular", css: "Alfa Slab One", lisans: "OFL", grup: "Sokak" },
  { key: "creepster", label: "Korku", file: "Creepster-Regular", css: "Creepster", lisans: "OFL", grup: "Sokak", tr: false, eksik: ["ğ", "Ğ", "İ", "ş", "Ş"] },

  // ── El yazısı ──
  { key: "dancing", label: "El yazısı", file: "DancingScript-Bold", css: "Dancing Script", lisans: "OFL", grup: "El yazısı" },
  { key: "caveat", label: "Not defteri", file: "Caveat-Regular", css: "Caveat", lisans: "OFL", grup: "El yazısı" },
  { key: "greatvibes", label: "Zarif", file: "GreatVibes-Regular", css: "Great Vibes", lisans: "OFL", grup: "El yazısı" },
  { key: "pacifico", label: "Pacifico", file: "Pacifico-Regular", css: "Pacifico", lisans: "OFL", grup: "El yazısı" },

  // ── Retro ──
  { key: "lobster", label: "Lobster", file: "Lobster-Regular", css: "Lobster", lisans: "OFL", grup: "Retro" },
  { key: "monoton", label: "Neon", file: "Monoton-Regular", css: "Monoton", lisans: "OFL", grup: "Retro" },
  { key: "righteous", label: "Art Deco", file: "Righteous-Regular", css: "Righteous", lisans: "OFL", grup: "Retro" },
  { key: "elite", label: "Eski Daktilo", file: "SpecialElite-Regular", css: "Special Elite", lisans: "Apache 2.0", grup: "Retro" },
];

export const FONT_GRUPLARI = ["Klasik", "Sokak", "El yazısı", "Retro"] as const;

export const fontCss = FONTS.map(
  (f) => `@font-face{font-family:'${f.css}';src:url('/fonts/${f.file}.ttf') format('truetype');font-display:swap}`,
).join("\n");

export const fontByKey = (key: string) => FONTS.find((f) => f.key === key) || FONTS[0];

/** Seçili font metindeki Türkçe harfleri basabiliyor mu? Basamıyorsa uyarı metni. */
export function trUyarisi(fontKey: string, metin: string): string | null {
  const f = fontByKey(fontKey);
  if (f.tr !== false) return null;
  const sorunlu = (f.eksik || []).filter((h) => metin.includes(h));
  if (!sorunlu.length) return null;
  return `“${f.label}” yazı tipi ${sorunlu.join(", ")} harflerini içermiyor — baskıda boş çıkar.`;
}
