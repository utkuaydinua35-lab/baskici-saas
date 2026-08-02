// Tasarım stüdyosu font seti — hepsi ticari kullanıma açık (SIL OFL / Apache 2.0)
// ve KENDİ SUNUCUMUZDA barındırılıyor. Aynı .ttf dosyaları backend'de de var:
// baskıya hazır dosya sunucuda üretilirken müşterinin ekranda gördüğü yazı
// tipiyle birebir aynısı kullanılır (dış CDN'e bağımlılık da yok).
export interface StudioFont {
  key: string;
  label: string;
  file: string;
  css: string;      // font-family adı
  lisans: string;
}

export const FONTS: StudioFont[] = [
  { key: "poppins", label: "Poppins", file: "Poppins-SemiBold", css: "Poppins", lisans: "OFL" },
  { key: "montserrat", label: "Montserrat", file: "Montserrat-Bold", css: "Montserrat", lisans: "OFL" },
  { key: "playfair", label: "Playfair", file: "PlayfairDisplay-Bold", css: "Playfair Display", lisans: "OFL" },
  { key: "bebas", label: "Bebas Neue", file: "BebasNeue-Regular", css: "Bebas Neue", lisans: "OFL" },
  { key: "oswald", label: "Oswald", file: "Oswald-SemiBold", css: "Oswald", lisans: "OFL" },
  { key: "dancing", label: "El yazısı", file: "DancingScript-Bold", css: "Dancing Script", lisans: "OFL" },
  { key: "lobster", label: "Lobster", file: "Lobster-Regular", css: "Lobster", lisans: "OFL" },
  { key: "mono", label: "Daktilo", file: "RobotoMono-Medium", css: "Roboto Mono", lisans: "Apache 2.0" },
];

export const fontCss = FONTS.map(
  (f) => `@font-face{font-family:'${f.css}';src:url('/fonts/${f.file}.ttf') format('truetype');font-display:swap}`,
).join("\n");

export const fontByKey = (key: string) => FONTS.find((f) => f.key === key) || FONTS[0];
