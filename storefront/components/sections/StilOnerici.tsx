import { getProducts } from "@/lib/api";
import StilOnericiSahne, { type Secenek } from "@/components/sections/StilOnericiSahne";

// Stil önerici (Füzyon) — ziyaretçi bir ruh hâli seçer, o hâle bağlı ürünler
// sahnede sırayla belirir. Bir tarzda BİRDEN ÇOK ürün olabilir; öneriler kendi
// kendine döner (ziyaretçi dokununca durur). Ürünler sunucuda çekilir; seçim
// tarayıcıda (istek yok). Ürünü bulunmayan tarz gösterilmez; hiçbiri yoksa bölüm yok.
export default async function StilOnerici({
  eyebrow,
  title,
  subtitle,
  secenekler = [],
  otomatik = true,
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  secenekler?: { etiket: string; renk: string; kelime: string; neden: string; urun?: string; urunler?: string[]; zemin: string }[];
  otomatik?: boolean;
}) {
  // `urunler` yeni alan; eski temalarda yalnız tek `urun` var
  const slugListesi = (s: { urun?: string; urunler?: string[] }) =>
    (s.urunler?.length ? s.urunler : s.urun ? [s.urun] : []).filter(Boolean);
  const sluglar = [...new Set(secenekler.flatMap(slugListesi))];
  if (sluglar.length === 0) return null;
  // Uç istek başına en fazla 24 slug döner → parça parça
  const parcalar: string[][] = [];
  for (let i = 0; i < sluglar.length; i += 24) parcalar.push(sluglar.slice(i, i + 24));
  const yanitlar = await Promise.all(
    parcalar.map((p) => getProducts({ slugs: p.join(","), perPage: 24 })));
  const urunler = new Map(yanitlar.flatMap((d) => d?.items ?? []).map((p) => [p.slug, p]));
  const hazir: Secenek[] = secenekler
    .map((s) => ({
      etiket: s.etiket, renk: s.renk, kelime: s.kelime, neden: s.neden, zemin: s.zemin,
      urunler: slugListesi(s).filter((slug) => urunler.has(slug)).map((slug) => {
        const p = urunler.get(slug)!;
        return { slug, ad: p.title, gorsel: p.cover_image, fiyat: p.price, paraBirimi: p.currency };
      }),
    }))
    .filter((s) => s.urunler.length > 0);
  if (hazir.length === 0) return null;
  return <StilOnericiSahne eyebrow={eyebrow} title={title} subtitle={subtitle}
    secenekler={hazir} otomatik={otomatik !== false} />;
}
