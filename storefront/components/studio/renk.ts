// BASKI RENK KURALI — dijital baskı makinesi CMYK ile çalışır ve mürekkep
// bileşenlerinin tamamı sıfır olan bir rengi "boşluk" sayıp oraya HİÇ baskı
// yapmaz. Yani saf beyaz (#FFFFFF = CMYK 0,0,0,0) müşterinin ekranında beyaz
// görünür ama üründe baskısız (kılıfın kendi rengi) çıkar.
//
// Çözüm: beyaz her zaman CMYK 0,0,0,5 ile basılır — gözle beyaz, makine için
// mürekkep var. Bu dosya hem palet hem de elle girilen hex kodu için tek
// doğruluk kaynağıdır (aynı kural backend/app/services/design_render.py'de de
// uygulanır; istemciye güvenmiyoruz).

/** CMYK 0,0,0,5 karşılığı — "basılabilir beyaz" */
export const BASKI_BEYAZ = "#f2f2f2";

/** #abc / #aabbcc / aabbcc → #aabbcc (geçersizse null) */
export function hexNormalize(ham: string): string | null {
  const s = (ham || "").trim().replace(/^#/, "").toLowerCase();
  if (/^[0-9a-f]{3}$/.test(s)) return `#${s[0]}${s[0]}${s[1]}${s[1]}${s[2]}${s[2]}`;
  if (/^[0-9a-f]{6}$/.test(s)) return `#${s}`;
  return null;
}

export function hexToRgb(hex: string): [number, number, number] {
  const s = hexNormalize(hex) || "#000000";
  return [
    parseInt(s.slice(1, 3), 16),
    parseInt(s.slice(3, 5), 16),
    parseInt(s.slice(5, 7), 16),
  ];
}

/** RGB → CMYK (0-100). Baskı öncesi kontrol için yaklaşık dönüşüm. */
export function rgbToCmyk(r: number, g: number, b: number): [number, number, number, number] {
  const R = r / 255, G = g / 255, B = b / 255;
  const k = 1 - Math.max(R, G, B);
  if (k >= 1) return [0, 0, 0, 100];
  const c = (1 - R - k) / (1 - k);
  const m = (1 - G - k) / (1 - k);
  const y = (1 - B - k) / (1 - k);
  return [
    Math.round(c * 100), Math.round(m * 100),
    Math.round(y * 100), Math.round(k * 100),
  ];
}

export function cmykYazi(hex: string): string {
  const [c, m, y, k] = rgbToCmyk(...hexToRgb(hex));
  return `C${c} M${m} Y${y} K${k}`;
}

/**
 * Rengi baskıya uygun hale getirir. CMYK bileşenlerinin tamamı %2'nin altındaysa
 * (saf beyaz ve ona çok yakın tonlar) makine hiç mürekkep basmaz — bu renkler
 * basılabilir beyaza (CMYK 0,0,0,5) çekilir.
 */
export function basilabilirRenk(hex: string): { renk: string; duzeltildi: boolean } {
  const s = hexNormalize(hex);
  if (!s) return { renk: BASKI_BEYAZ, duzeltildi: true };
  const [c, m, y, k] = rgbToCmyk(...hexToRgb(s));
  if (c < 2 && m < 2 && y < 2 && k < 2) return { renk: BASKI_BEYAZ, duzeltildi: true };
  return { renk: s, duzeltildi: false };
}

/** Editör paleti — saf beyaz YOK, yerine basılabilir beyaz var. */
export const PALET: { hex: string; ad: string }[] = [
  { hex: "#111111", ad: "Siyah" },
  { hex: BASKI_BEYAZ, ad: "Beyaz (basılabilir)" },
  { hex: "#6b7280", ad: "Gri" },
  { hex: "#e11d48", ad: "Kırmızı" },
  { hex: "#f43f5e", ad: "Pembe" },
  { hex: "#f59e0b", ad: "Turuncu" },
  { hex: "#facc15", ad: "Sarı" },
  { hex: "#10b981", ad: "Yeşil" },
  { hex: "#059669", ad: "Zümrüt" },
  { hex: "#0ea5e9", ad: "Mavi" },
  { hex: "#2563eb", ad: "Koyu mavi" },
  { hex: "#7c3aed", ad: "Mor" },
  { hex: "#a855f7", ad: "Lila" },
  { hex: "#78350f", ad: "Kahve" },
  { hex: "#0f766e", ad: "Petrol" },
  { hex: "#be185d", ad: "Fuşya" },
];
