// Ürün sayfasında "Kendi Tasarımını Yap" bölümü.
//
// Panelde bu ürüne bağlanan kılıf şablonlarını gösterir; müşteri birini
// seçince stüdyo o kılıfla ve bu ürünle açılır.
import Link from "next/link";

interface Modul {
  key: string;
  label: string;
  description: string | null;
  image_url: string;
}

export default function StudioModules({
  modules, productSlug,
}: { modules: Modul[]; productSlug: string }) {
  if (!modules?.length) return null;
  return (
    <section className="mt-8 border border-zinc-200 rounded-2xl p-5">
      <h2 className="text-lg font-semibold">🎨 Kendi Tasarımını Yap</h2>
      <p className="mt-1 text-sm text-zinc-500">
        Bu ürünü kendi fotoğrafın ve yazınla tasarlayabilirsin. Kılıfını seç,
        stüdyoda tasarla, sepete ekle.
      </p>
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
        {modules.map((m) => (
          <Link key={m.key}
            href={`/tasarla?urun=${encodeURIComponent(productSlug)}&kilif=${encodeURIComponent(m.key)}`}
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
    </section>
  );
}
