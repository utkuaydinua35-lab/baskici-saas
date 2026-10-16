// Panelde ayarlanan oran + kırpımla görsel (koleksiyon sayfası başlığı).
// Kırpma tarayıcıda yapılır (dosya değişmez): kutu seçilen oranda, görsel
// kutuyu kaplar; odak noktası (x,y %) ve yakınlaştırma panelin önizlemesiyle
// AYNI CSS — panel/src/components/KoleksiyonGorselDuzen.jsx ile birebir.
export interface Kirp {
  oran: string; x: number; y: number; zoom: number;
  duzen?: "yan" | "kaplama"; taraf?: "sag" | "sol";
}

export function oranCss(oran?: string): string | undefined {
  const m = /^(\d+):(\d+)$/.exec(oran || "");
  return m ? `${m[1]} / ${m[2]}` : undefined;
}

export default function KirpikGorsel({ src, alt, kirp, className = "" }: {
  src: string; alt: string; kirp?: Kirp | null; className?: string;
}) {
  const oran = oranCss(kirp?.oran);
  if (!oran) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} className={`block w-full h-auto ${className}`} />;
  }
  const x = kirp?.x ?? 50, y = kirp?.y ?? 50, zoom = kirp?.zoom ?? 1;
  return (
    <div className={`relative overflow-hidden ${className}`} style={{ aspectRatio: oran }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} className="absolute inset-0 h-full w-full object-cover"
        style={{ objectPosition: `${x}% ${y}%`, transform: zoom > 1 ? `scale(${zoom})` : undefined,
          transformOrigin: `${x}% ${y}%` }} />
    </div>
  );
}
