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

/** Hazır tasarım şablonu (panelden yüklenen çerçeve/desen).
 *  Baskı ALANINI tam kaplar — taşınmaz, ölçeklenmez; kılıfa bire bir otursun.
 *  Çizim sırası: görseller → overlay → yazılar (bkz. katmanlar.ts). */
export interface OverlayLayer {
  id: string;
  type: "overlay";
  overlay_id: string;   // DesignOverlay.id — baskıda dosya BUNDAN bulunur
  url: string;          // tuvalde gösterilen görsel
  label?: string;
  /** Kısıtlı şablonun açılabilir öğesi (bayrak, logo…): alan anahtarı.
   *  Boşsa şablonun kendi görselidir ve baskı alanını tam kaplar. */
  field?: string;
  /** field varsa öğenin konumu (baskı alanına oransal) */
  kutu?: { x: number; y: number; w: number; h: number };
}

export type Layer = ImageLayer | TextLayer | OverlayLayer;

/** Kısıtlı şablonda müşterinin doldurduğu tek alan (panelde tanımlanır) */
export interface StudioAlan {
  key: string;
  tip: "yazi" | "gorsel";
  etiket: string;
  x: number; y: number; w: number;
  h?: number;                    // görsel alanı
  varsayilan?: string | boolean;
  max?: number;                  // yazı: en fazla karakter
  size?: number;                 // yazı: punto (baskı alanı yüksekliğine oran)
  font?: string;
  renk?: string;
  hiza?: "left" | "center" | "right";
  image_url?: string | null;     // görsel alanı
}

export interface StudioOverlay {
  id: string;
  label: string;
  template_key: string | null;   // null → tüm kılıflarda geçerli
  image_url: string;
  thumb_url: string;
  /** "kisitli" → editör form moduna geçer: serbest görsel/yazı eklenemez */
  mod?: "serbest" | "kisitli";
  alanlar?: StudioAlan[];
}

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
