// Tasarım stüdyosu veri tipleri.
//
// KONUM SİSTEMİ: her katmanın x/y/w/h değeri BASKI ALANINA oransaldır (0-1).
// Ekran 320px de olsa 1400px de olsa aynı sonuç; sunucu 827×1713 px baskı
// dosyasını üretirken de aynı oranları kullanır. Böylece müşterinin gördüğü
// ile basılan bire bir örtüşür.

export interface CaseArea {
  x: number; y: number; w: number; h: number; radius: number;
}

export interface Cutout {
  x: number; y: number; w: number; h: number; radius: number; label?: string;
}

export interface CaseTemplate {
  key: string;
  label: string;
  description: string | null;
  image_url: string;
  area: CaseArea;
  cutouts: Cutout[];
  print: { width_mm: number; height_mm: number; dpi: number };
}

export interface ImageLayer {
  id: string;
  type: "image";
  asset_id: string;
  url: string;          // tuvalde gösterilen hafif önizleme
  x: number; y: number; w: number; h: number;   // baskı alanına oransal
  rot: number;          // derece
  src_w: number;        // orijinal piksel — çözünürlük uyarısı için
  src_h: number;
  // Kırpma: görselin hangi bölümü kullanılacak (0-1, orijinale oransal)
  crop?: { x: number; y: number; w: number; h: number };
}

export interface TextLayer {
  id: string;
  type: "text";
  text: string;
  font: string;         // FONTS[].key
  size: number;         // baskı alanı YÜKSEKLİĞİNE oran (0-1)
  color: string;
  x: number; y: number; // metin kutusunun sol-üstü
  w: number;            // sarma genişliği
  rot: number;
  align: "left" | "center" | "right";
}

export type Layer = ImageLayer | TextLayer;

export interface SavedDesign {
  id: string;
  name: string;
  template_key: string | null;
  layers: Layer[];
  preview_url: string | null;
  status: "draft" | "ready" | "ordered";
  updated_at: string | null;
}

// Katman güncelleme yaması — 'type' ve 'id' hariç iki katman tipinin birleşimi.
// (ImageLayer & TextLayer doğrudan kesiştirilirse 'type' alanı çakışıp never olur.)
export type LayerPatch = Partial<Omit<ImageLayer, 'type' | 'id'>> &
  Partial<Omit<TextLayer, 'type' | 'id'>>;
