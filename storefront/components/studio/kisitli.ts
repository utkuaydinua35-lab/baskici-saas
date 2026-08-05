// Kısıtlı hazır şablon — müşteri yalnız tanımlı alanları doldurur.
//
// Bu dosya alan DEĞERLERİNDEN tuval katmanlarını üretir (canlı önizleme için).
// Konum, font, renk, punto ve dosyalar HEP ŞABLONDAN gelir. Aynı kurallar
// sunucuda da uygulanır — kaydederken müşteri sadece alan değerlerini gönderir,
// katmanları backend/app/services/kisitli_sablon.py yeniden üretir. Yani buradaki
// çıktı yalnızca önizlemedir; baskıya giden katmanlar sunucudan doğar.
import type { Layer, OverlayLayer, StudioOverlay, TextLayer } from "./types";

export type AlanDegeri = string | boolean | null;

export function varsayilanDegerler(o: StudioOverlay): Record<string, AlanDegeri> {
  const d: Record<string, AlanDegeri> = {};
  for (const a of o.alanlar || []) {
    d[a.key] = a.tip === "yazi" ? String(a.varsayilan ?? "") : a.varsayilan !== false;
  }
  return d;
}

export function kisitliKatmanlar(
  o: StudioOverlay, degerler: Record<string, AlanDegeri>,
): Layer[] {
  const taban: OverlayLayer = {
    id: "taban", type: "overlay", overlay_id: o.id, url: o.image_url, label: o.label,
  };
  const katmanlar: Layer[] = [taban];

  for (const a of o.alanlar || []) {
    if (a.tip === "yazi") {
      const ham = degerler[a.key];
      const metin = String(ham ?? a.varsayilan ?? "").slice(0, a.max || 40).trim();
      if (!metin) continue;
      const yazi: TextLayer = {
        id: `alan-${a.key}`, type: "text", text: metin,
        font: a.font || "anton", size: a.size ?? 0.1, color: a.renk || "#ffffff",
        x: a.x, y: a.y, w: a.w, rot: 0,
        align: (a.hiza as TextLayer["align"]) || "center",
      };
      katmanlar.push(yazi);
    } else {
      const secim = degerler[a.key];
      const acik = secim === undefined || secim === null ? a.varsayilan !== false : !!secim;
      if (!acik || !a.image_url) continue;
      katmanlar.push({
        id: `alan-${a.key}`, type: "overlay", overlay_id: o.id,
        url: a.image_url, label: a.etiket, field: a.key,
        kutu: { x: a.x, y: a.y, w: a.w, h: a.h ?? 0.1 },
      } as OverlayLayer);
    }
  }
  return katmanlar;
}
