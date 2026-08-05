// KATMAN SIRASI — dizideki sıra ÇİZİM SIRASIDIR: ilk eleman en altta,
// son eleman en üstte. Tipe göre otomatik sıralama YOK; müşteri hazır şablonu
// (çerçeveyi) istediği katmana taşıyabilsin diye sıra tamamen ona bırakılmıştır.
// Aynı kural üç yerde geçerli: tuval (Canvas.tsx), önizleme (preview.ts) ve
// baskı dosyası (backend/app/services/design_render.py).
import type { Layer } from "./types";

/**
 * Yeni katmanı diziye ekler. Hazır şablon EN ÜSTTEYSE yeni içerik onun ALTINA
 * girer — müşteri çerçeveyi üstte tutmayı seçtiyse eklediği her görsel/yazı
 * çerçevenin arkasında kalsın diye. Şablon üstte değilse katman sona eklenir.
 */
export function katmanEkle(layers: Layer[], yeni: Layer): Layer[] {
  const son = layers[layers.length - 1];
  if (son?.type === "overlay") return [...layers.slice(0, -1), yeni, son];
  return [...layers, yeni];
}

/** Hazır şablonu en alta (zemin) veya en üste taşır. */
export function overlayTasi(layers: Layer[], nereye: "ust" | "alt"): Layer[] {
  const ov = layers.find((l) => l.type === "overlay");
  if (!ov) return layers;
  const digerleri = layers.filter((l) => l !== ov);
  return nereye === "alt" ? [ov, ...digerleri] : [...digerleri, ov];
}
