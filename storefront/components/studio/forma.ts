// Forma tasarlayıcı — kısıtlı şablonda müşteriye açılan seçenekler:
// desen + renkler (zemin KODLA çizilir), yazı tipi/rengi/konturu, amblem.
//
// DESEN GEOMETRİSİ üç yerde AYNI olmalı (ekran, önizleme PNG'si, baskı):
//   backend/app/services/forma.py            → desen_sekilleri   (baskı, asıl)
//   storefront/components/studio/forma.ts    → desenSekilleri    (bu dosya)
//   panel/src/lib/formaDesen.js              → desenSekilleri    (panel önizlemesi)
// Birini değiştirirsen üçünü de değiştir; backend/scripts/forma_test.py
// sunucu çıktısını sabit değerlerle karşılaştırır.
import type { StudioOverlay } from "./types";

/** Yazı konturu kalınlığı / punto (harfin DIŞINDA görünen kısım).
 *  Sunucudaki eşi: backend/app/services/forma.py → KONTUR_ORANLARI */
export const KONTUR_ORANLARI: Record<string, number> = { ince: 0.018, orta: 0.032, kalin: 0.05 };
export const konturOrani = (anahtar?: string) =>
  KONTUR_ORANLARI[anahtar || "orta"] ?? KONTUR_ORANLARI.orta;
/** Konturlu yazıda harf arası = kontur kalınlığının 2 katı: yan yana iki
 *  harfin konturu üst üste binmez (sunucu: design_render._kontur) */
export const konturAraligi = (anahtar?: string) => 2 * konturOrani(anahtar);

export type Yogunluk = "ince" | "orta" | "kalin";
export type Cokgen = { renk: number; nokta: [number, number][] };

const yuvarla = (n: number) => Math.round(n * 1e6) / 1e6;

/** Desen → çokgenler, birim karede (0-1). Zemin HER ZAMAN renk 0'dır;
 *  buradakiler onun üstüne çizilir. */
export function desenSekilleri(desen: string, yogunluk: string = "orta"): Cokgen[] {
  const y = yogunluk === "ince" ? 0 : yogunluk === "kalin" ? 2 : 1;
  const s: Cokgen[] = [];
  const kutu = (renk: number, x0: number, y0: number, x1: number, y1: number) =>
    s.push({ renk, nokta: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]] });

  if (desen === "dikey") {
    const n = [11, 7, 5][y];
    for (let i = 1; i < n; i += 2) kutu(1, i / n, 0, (i + 1) / n, 1);
  } else if (desen === "yatay") {
    const n = [17, 11, 7][y];
    for (let i = 1; i < n; i += 2) kutu(1, 0, i / n, 1, (i + 1) / n);
  } else if (desen === "capraz") {
    const n = [9, 6, 4][y];
    const g = 1 / n;
    for (let i = -n; i <= n; i++) {
      const x0 = i * g;
      s.push({ renk: 1, nokta: [[x0, 0], [x0 + g / 2, 0], [x0 + g / 2 + 1, 1], [x0 + 1, 1]] });
    }
  } else if (desen === "yari") {
    kutu(1, 0.5, 0, 1, 1);
  } else if (desen === "kareli") {
    const sutun = [6, 4, 2][y];
    const satir = sutun * 2;
    for (let r = 0; r < satir; r++) {
      for (let c = 0; c < sutun; c++) {
        if ((r + c) % 2 === 1) kutu(1, c / sutun, r / satir, (c + 1) / sutun, (r + 1) / satir);
      }
    }
  } else if (desen === "bant") {
    const h = [0.10, 0.16, 0.24][y];
    const ust = 0.50 - h / 2;
    kutu(1, 0, ust, 1, ust + h);
    kutu(2, 0, ust - 0.012, 1, ust);
    kutu(2, 0, ust + h, 1, ust + h + 0.012);
  } else if (desen === "orta_serit") {
    const w = [0.18, 0.30, 0.44][y];
    const sol = 0.5 - w / 2;
    kutu(1, sol, 0, sol + w, 1);
    kutu(2, sol - 0.024, 0, sol, 1);
    kutu(2, sol + w, 0, sol + w + 0.024, 1);
  } else if (desen === "capraz_bant") {
    const w = [0.16, 0.26, 0.38][y];
    s.push({ renk: 2, nokta: [[-w / 2 - 0.03, 0], [w / 2 + 0.03, 0], [1 + w / 2 + 0.03, 1], [1 - w / 2 - 0.03, 1]] });
    s.push({ renk: 1, nokta: [[-w / 2, 0], [w / 2, 0], [1 + w / 2, 1], [1 - w / 2, 1]] });
  }
  return s.map((c) => ({
    renk: c.renk, nokta: c.nokta.map(([px, py]) => [yuvarla(px), yuvarla(py)] as [number, number]),
  }));
}

/** Yoğunluk seçeneği olmayan desenler (tek biçimi var) */
export const YOGUNLUKSUZ = new Set(["duz", "yari"]);
/** Üçüncü rengi (ince kenar çizgisi) kullanan desenler */
export const UC_RENKLI = new Set(["bant", "orta_serit", "capraz_bant"]);

export interface FormaSecim {
  desen: string; yogunluk: Yogunluk; renkler: [string, string, string];
  font: string; yazi_renk: string; kontur: string;      // "" → kontur yok
  kontur_kalinlik: Yogunluk;
  amblem: string; amblem_renk: string;                    // "" → amblem yok
}

/** alanDegerleri içindeki `_…` anahtarları → geçerli seçim (eksikler şablon
 *  varsayılanından). Sunucu aynı doğrulamayı yeniden yapar (services/forma). */
export function formaSecimi(o: StudioOverlay, d: Record<string, unknown>): FormaSecim | null {
  const f = o.forma;
  if (!f) return null;
  const v = f.varsayilan;
  // Hazır ürün (kilitli): müşteri seçimi yok — hep şablonun görünümü
  const metin = (k: string) => (!f.kilitli && typeof d[k] === "string" ? (d[k] as string) : undefined);
  const desen = f.desenler.some((x) => x.key === metin("_desen")) ? metin("_desen")! : v.desen;
  const yg = metin("_yogunluk");
  const amblemHam = metin("_amblem");
  const amblem = amblemHam === undefined ? v.amblem
    : f.amblemler.some((a) => a.key === amblemHam) ? amblemHam : "";
  const konturHam = metin("_kontur");
  return {
    desen,
    yogunluk: (yg === "ince" || yg === "orta" || yg === "kalin") ? yg : v.yogunluk,
    renkler: [0, 1, 2].map((i) => metin(`_renk${i + 1}`) || v.renkler[i]) as [string, string, string],
    font: f.fontlar.includes(metin("_font") || "") ? metin("_font")! : v.font,
    yazi_renk: metin("_yazi_renk") || v.yazi_renk,
    kontur: konturHam === undefined ? v.kontur : konturHam,
    kontur_kalinlik: (() => {
      const k = metin("_kontur_kalinlik");
      return (k === "ince" || k === "orta" || k === "kalin") ? k : (v.kontur_kalinlik || "orta");
    })(),
    amblem: f.amblemler.some((a) => a.key === amblem) ? amblem : "",
    amblem_renk: metin("_amblem_renk") || v.amblem_renk,
  };
}

/** Seçim → sunucuya/duruma yazılacak `_…` anahtarları */
export function formaDegerleri(s: FormaSecim): Record<string, string> {
  return {
    _desen: s.desen, _yogunluk: s.yogunluk,
    _renk1: s.renkler[0], _renk2: s.renkler[1], _renk3: s.renkler[2],
    _font: s.font, _yazi_renk: s.yazi_renk, _kontur: s.kontur,
    _kontur_kalinlik: s.kontur_kalinlik,
    _amblem: s.amblem, _amblem_renk: s.amblem_renk,
  };
}
