import { getProducts } from "@/lib/api";
import StilOnericiSahne, { type Secenek } from "@/components/sections/StilOnericiSahne";

// Stil önerici (Füzyon) — ziyaretçi bir ruh hâli seçer, o hâle bağlı ürün
// sahnede belirir. Ürünler sunucuda tek istekte çekilir; seçim tarayıcıda
// (istek yok). Ürünü bulunmayan seçenek gösterilmez; hiçbiri yoksa bölüm yok.
export default async function StilOnerici({
  eyebrow,
  title,
  subtitle,
  secenekler = [],
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  secenekler?: { etiket: string; renk: string; kelime: string; neden: string; urun: string; zemin: string }[];
}) {
  const sluglar = [...new Set(secenekler.map((s) => s.urun).filter(Boolean))];
  if (sluglar.length === 0) return null;
  const data = await getProducts({ slugs: sluglar.join(","), perPage: 12 });
  const urunler = new Map((data?.items ?? []).map((p) => [p.slug, p]));
  const hazir: Secenek[] = secenekler
    .filter((s) => urunler.has(s.urun))
    .map((s) => {
      const p = urunler.get(s.urun)!;
      return { ...s, urunAdi: p.title, gorsel: p.cover_image, fiyat: p.price, paraBirimi: p.currency };
    });
  if (hazir.length === 0) return null;
  return <StilOnericiSahne eyebrow={eyebrow} title={title} subtitle={subtitle} secenekler={hazir} />;
}
