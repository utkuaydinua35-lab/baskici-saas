// KATMAN SIRASI — tek kural, üç yerde de aynı:
// tuval (Canvas.tsx), önizleme PNG'si (preview.ts) ve baskı dosyası
// (backend/app/services/design_render.py → siralanmis_katmanlar).
//
// Müşterinin görselleri EN ALTTA, hazır şablon (çerçeve) onların üstünde,
// yazılar EN ÜSTTE. Böylece fotoğraf çerçevesi şablonu seçen müşterinin
// yüklediği fotoğraf çerçevenin içinde kalır, yazısı ise çerçevenin üstüne
// yazılabilir.
import type { Layer } from "./types";

const SIRA: Record<string, number> = { image: 0, overlay: 1, text: 2 };

export function siralanmisKatmanlar(layers: Layer[]): Layer[] {
  // Array.sort kararlıdır: aynı tipteki katmanların kendi sırası korunur
  return [...layers].sort((a, b) => (SIRA[a.type] ?? 0) - (SIRA[b.type] ?? 0));
}
