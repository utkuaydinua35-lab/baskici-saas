import Link from "next/link";

// Özel 404 — müşteriyi çıkmaza sokmadan alışverişe geri yönlendirir.
export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <div className="text-6xl mb-4">🔍</div>
      <h1 className="text-2xl font-bold">Sayfa bulunamadı</h1>
      <p className="mt-2 text-sm text-zinc-500">
        Aradığınız sayfa taşınmış ya da kaldırılmış olabilir.
      </p>
      <div className="mt-8 flex justify-center gap-3">
        <Link
          href="/"
          className="rounded-xl border border-zinc-300 px-5 py-2.5 text-sm font-medium hover:border-zinc-500 transition"
        >
          Anasayfa
        </Link>
        <Link
          href="/urunler"
          className="rounded-xl text-white px-5 py-2.5 text-sm font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}
        >
          Ürünlere Göz At
        </Link>
      </div>
    </div>
  );
}
