// Ürün sayfasında "Kendi Tasarımını Yap" bölümü.
//
// İki ayrı liste gösterir:
//  • KILIF ŞABLONLARI (studio_templates) — boş kılıf, müşteri sıfırdan tasarlar.
//  • HAZIR TASARIM MODÜLLERİ (studio_moduller) — Spotify arayüzü, forma gibi
//    hazır tasarımlar; müşteri yalnız içindeki alanları doldurur.
// Panelde yalnız modül seçilmişse de bölüm görünür (eskiden kılıf şablonu
// seçilmediğinde ürün sayfasında hiçbir şey çıkmıyordu).
import Link from "next/link";
import { desenSekilleri } from "@/components/studio/forma";

interface Modul {
  key: string;
  label: string;
  description: string | null;
  image_url: string;
}

export interface HazirModul {
  id: string;
  label: string;
  kategori: string | null;
  thumb_url: string;
  kilif_key: string | null;
  /** Forma tasarlayıcı açıksa: kodla çizilen başlangıç deseni */
  forma_onizleme?: { desen: string; yogunluk: string; renkler: string[] } | null;
}

export default function StudioModules({
  modules, moduller = [], productSlug,
}: { modules: Modul[]; moduller?: HazirModul[]; productSlug: string }) {
  if (!modules?.length && !moduller?.length) return null;
  const urunQs = `urun=${encodeURIComponent(productSlug)}`;
  return (
    <section id="tasarim" className="mt-8 border border-zinc-200 rounded-2xl p-5 scroll-mt-24 transition-shadow">
      <h2 className="text-lg font-semibold">🎨 Kendi Tasarımını Yap</h2>
      <p className="mt-1 text-sm text-zinc-500">
        Bu ürünü kendi fotoğrafın ve yazınla tasarlayabilirsin. Kılıfını seç,
        stüdyoda tasarla, sepete ekle.
      </p>

      {moduller.length > 0 && (
        <>
          <h3 className="mt-4 text-sm font-medium text-zinc-700">Hazır tasarımlar</h3>
          <p className="text-xs text-zinc-500">
            Tasarım hazır — sen yalnız yazıları ve fotoğrafı değiştir.
          </p>
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {moduller.map((m) => (
              <Link key={m.id}
                href={`/tasarla?${urunQs}&modul=${encodeURIComponent(m.id)}${
                  m.kilif_key ? `&kilif=${encodeURIComponent(m.kilif_key)}` : ""}`}
                className="group rounded-2xl border border-zinc-200 overflow-hidden hover:border-zinc-900 transition">
                <div className="aspect-[3/4] bg-zinc-50 flex items-center justify-center p-2">
                  {m.forma_onizleme ? (
                    <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden
                      className="h-full aspect-[1/2] rounded-xl group-hover:scale-105 transition">
                      <rect x="0" y="0" width="1" height="1" fill={m.forma_onizleme.renkler[0]} />
                      {desenSekilleri(m.forma_onizleme.desen, m.forma_onizleme.yogunluk).map((c, i) => (
                        <polygon key={i} fill={m.forma_onizleme!.renkler[Math.min(c.renk, 2)]}
                          points={c.nokta.map(([x, y]) => `${x},${y}`).join(" ")} />
                      ))}
                    </svg>
                  ) : (
                    <img src={m.thumb_url} alt={m.label}
                      className="h-full w-auto object-contain group-hover:scale-105 transition" />
                  )}
                </div>
                <div className="px-2.5 py-2">
                  {/* Ürüne özel modülün iç adı müşteriye gösterilmez (boş gelir) */}
                  <div className="text-sm font-medium truncate">{m.label || "Tasarlamaya başla →"}</div>
                  {m.kategori && (
                    <div className="text-[11px] text-zinc-500 truncate">{m.kategori}</div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}

      {modules.length > 0 && (
        <>
          {moduller.length > 0 && (
            <h3 className="mt-5 text-sm font-medium text-zinc-700">Sıfırdan tasarla</h3>
          )}
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {modules.map((m) => (
              <Link key={m.key}
                href={`/tasarla?${urunQs}&kilif=${encodeURIComponent(m.key)}`}
                className="group rounded-2xl border border-zinc-200 overflow-hidden hover:border-zinc-900 transition">
                <div className="aspect-[3/4] bg-zinc-50 flex items-center justify-center p-2">
                  <img src={m.image_url} alt={m.label}
                    className="h-full w-auto object-contain group-hover:scale-105 transition" />
                </div>
                <div className="px-2.5 py-2">
                  <div className="text-sm font-medium truncate">{m.label}</div>
                  {m.description && (
                    <div className="text-[11px] text-zinc-500 truncate">{m.description}</div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
