// Kısıtlı hazır şablon — müşteri yalnız tanımlı alanları doldurur.
//
// Bu dosya alan DEĞERLERİNDEN tuval katmanlarını üretir (canlı önizleme için).
// Konum, font, renk, punto ve dosyalar HEP ŞABLONDAN gelir. Aynı kurallar
// sunucuda da uygulanır — kaydederken müşteri sadece alan değerlerini gönderir,
// katmanları backend/app/services/kisitli_sablon.py yeniden üretir. Yani buradaki
// çıktı yalnızca önizlemedir; baskıya giden katmanlar sunucudan doğar.
//
// Alan tipleri:
//   yazi     — müşteri metni yazar
//   gorsel   — panelden gelen SABİT öğe, müşteri açıp kapatır (bayrak, logo)
//   foto     — MÜŞTERİNİN yüklediği görsel, çerçeveye oranı bozulmadan oturur
//   ilerleme — iki süre alanından hesaplanan Spotify tarzı çubuk + nokta
import type {
  ImageLayer, Layer, OverlayLayer, ShapeLayer, StudioAlan, StudioOverlay, TextLayer,
} from "./types";

/** Müşterinin foto alanına yüklediği görsel */
export interface FotoDegeri {
  asset_id: string;
  url: string;
  w: number;
  h: number;
}

export type AlanDegeri = string | boolean | FotoDegeri | null;

export function varsayilanDegerler(o: StudioOverlay): Record<string, AlanDegeri> {
  const d: Record<string, AlanDegeri> = {};
  for (const a of o.alanlar || []) {
    if (a.tip === "yazi") d[a.key] = String(a.varsayilan ?? "");
    else if (a.tip === "gorsel") d[a.key] = a.varsayilan !== false;
    else if (a.tip === "foto") d[a.key] = null;
  }
  return d;
}

/** "3:07" / "187" → saniye. Çözemezse null. */
export function saniyeCoz(metin: unknown): number | null {
  const s = String(metin ?? "").trim();
  if (!s) return null;
  if (s.includes(":")) {
    const parcalar = s.split(":").map((p) => Number(p));
    if (parcalar.some((n) => !Number.isFinite(n))) return null;
    return parcalar.reduce((t, n) => t * 60 + n, 0);
  }
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** Görseli çerçeveye ORANI BOZMADAN doldurur (cover) — taşan kenar kırpılır. */
function kaplaCrop(hedefOran: number, kaynakW: number, kaynakH: number) {
  if (!kaynakW || !kaynakH) return undefined;
  const kaynakOran = kaynakW / kaynakH;
  if (kaynakOran > hedefOran) {
    const w = hedefOran / kaynakOran;
    return { x: (1 - w) / 2, y: 0, w, h: 1 };
  }
  const h = kaynakOran / hedefOran;
  return { x: 0, y: (1 - h) / 2, w: 1, h };
}

export function kisitliKatmanlar(
  o: StudioOverlay,
  degerler: Record<string, AlanDegeri>,
  alanOran = 1,           // baskı alanının en/boy oranı (W/H)
): Layer[] {
  const arkadakiler: Layer[] = [];
  const ondekiler: Layer[] = [];

  const sureDegeri = (key?: string): number | null => {
    if (!key) return null;
    const d = degerler[key];
    const coz = saniyeCoz(d);
    if (coz !== null) return coz;
    const alan = (o.alanlar || []).find((x) => x.key === key);
    return saniyeCoz(alan?.varsayilan);
  };

  for (const a of o.alanlar || []) {
    const hedef = a.arkada ? arkadakiler : ondekiler;

    if (a.tip === "yazi") {
      const metin = String(degerler[a.key] ?? a.varsayilan ?? "")
        .slice(0, a.max || 40).trim();
      if (!metin) continue;
      const yazi: TextLayer = {
        id: `alan-${a.key}`, type: "text", text: metin,
        font: a.font || "anton", size: a.size ?? 0.1, color: a.renk || "#ffffff",
        x: a.x, y: a.y, w: a.w,
        // Çerçeve yüksekliği — panelde çizilmemişse yok sayılır: o alanda
        // metin büyümez, yalnız gerekirse küçülür (taşma olmaz)
        ...(a.h ? { h: a.h } : {}),
        rot: 0,
        align: (a.hiza as TextLayer["align"]) || "center",
        // Panelde "çerçeveyi doldur" kapatılmadıysa punto çerçeveye oturur
        sigdir: a.otomatik_kucult !== false,
      };
      hedef.push(yazi);

    } else if (a.tip === "gorsel") {
      const secim = degerler[a.key];
      const acik = secim === undefined || secim === null ? a.varsayilan !== false : !!secim;
      if (!acik || !a.image_url) continue;
      hedef.push({
        id: `alan-${a.key}`, type: "overlay", overlay_id: o.id,
        url: a.image_url, label: a.etiket, field: a.key,
        kutu: { x: a.x, y: a.y, w: a.w, h: a.h ?? 0.1 },
      } as OverlayLayer);

    } else if (a.tip === "foto") {
      const foto = degerler[a.key] as FotoDegeri | null;
      if (!foto?.url) continue;
      const h = a.h ?? 0.3;
      const gorsel: ImageLayer = {
        id: `alan-${a.key}`, type: "image", asset_id: foto.asset_id, url: foto.url,
        x: a.x, y: a.y, w: a.w, h, rot: 0, src_w: foto.w, src_h: foto.h,
        ...((a.sigdir ?? "kapla") === "kapla"
          ? { crop: kaplaCrop((a.w * alanOran) / h, foto.w, foto.h) }
          : {}),
      };
      hedef.push(gorsel);

    } else if (a.tip === "ilerleme") {
      const gecen = sureDegeri(a.kaynak_gecen);
      const toplam = sureDegeri(a.kaynak_toplam);
      const oran = gecen !== null && toplam ? Math.max(0, Math.min(1, gecen / toplam)) : 0;
      const sekil: ShapeLayer = {
        id: `alan-${a.key}`, type: "sekil", bicim: "ilerleme",
        x: a.x, y: a.y, w: a.w,
        kalinlik: a.kalinlik ?? 0.004,
        boyut: a.boyut ?? 0.012,
        oran,
        renk: a.renk || "#ffffff",
        renk_pasif: a.renk_pasif || "#5a5a5a",
      };
      hedef.push(sekil);
    }
  }

  const taban: OverlayLayer = {
    id: "taban", type: "overlay", overlay_id: o.id, url: o.image_url, label: o.label,
  };
  return [...arkadakiler, taban, ...ondekiler];
}

/** Sunucuya gönderilecek biçim: foto alanları yalnız asset_id olarak gider. */
export function sunucuDegerleri(
  degerler: Record<string, AlanDegeri>, alanlar: StudioAlan[],
): Record<string, string | boolean | null> {
  const cikti: Record<string, string | boolean | null> = {};
  for (const a of alanlar || []) {
    const d = degerler[a.key];
    if (a.tip === "foto") cikti[a.key] = (d as FotoDegeri | null)?.asset_id || null;
    else if (a.tip === "gorsel") cikti[a.key] = d !== false;
    else if (a.tip === "yazi") cikti[a.key] = String(d ?? "");
  }
  return cikti;
}
