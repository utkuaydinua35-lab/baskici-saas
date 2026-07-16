"use client";

// Sepet çekmecesi — sağdan kayan slide-over (tema animations.cart_drawer).
// /sepet sayfası tam görünüm olarak kalır; çekmece hızlı erişim içindir.
import { useEffect } from "react";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import { useAutoQuote } from "@/lib/useAutoQuote";

export default function CartDrawer({ freeShippingOver }: { freeShippingOver?: string | null }) {
  const { items, subtotal, coupon, drawerOpen, setDrawerOpen, setQuantity, removeItem } = useCart();
  const freeOver = Number(freeShippingOver || 0);
  const remaining = freeOver > 0 ? Math.max(0, freeOver - subtotal) : 0;
  // Otomatik kampanya (3 al 2 öde vb.) çekmecede de görünmeli —
  // yoksa müşteri ödemeye kadar indirimi göremez, kafası karışır
  const autoQuote = useAutoQuote(items, coupon);

  // Açıkken body scroll kilidi + ESC ile kapatma
  useEffect(() => {
    if (!drawerOpen) return;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [drawerOpen, setDrawerOpen]);

  return (
    <>
      {/* Karartma */}
      <div
        onClick={() => setDrawerOpen(false)}
        className={`fixed inset-0 z-50 bg-black/40 transition-opacity duration-300 ${
          drawerOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />
      {/* Çekmece */}
      <aside
        className={`fixed top-0 right-0 z-50 h-full w-full max-w-sm bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-out ${
          drawerOpen ? "translate-x-0" : "translate-x-full"
        }`}
        aria-hidden={!drawerOpen}
      >
        <div className="flex items-center justify-between px-4 h-14 border-b border-zinc-200">
          <h2 className="font-semibold">Sepetim ({items.length})</h2>
          <button onClick={() => setDrawerOpen(false)} aria-label="Kapat"
            className="text-zinc-400 hover:text-zinc-900 text-xl leading-none">×</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {items.length === 0 && (
            <p className="text-sm text-zinc-500 text-center py-10">Sepetiniz boş.</p>
          )}
          {items.map((item) => (
            <div key={item.lineId ?? item.variantId} className="flex gap-3">
              <div className="w-16 h-16 rounded-xl bg-zinc-100 overflow-hidden shrink-0">
                {item.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.image} alt={item.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xl text-zinc-300">📱</div>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium line-clamp-1">{item.title}</div>
                <div className="text-xs text-zinc-500">
                  {item.modelDisplay}
                  {item.secondModelDisplay ? ` + ${item.secondModelDisplay}` : ""}
                  {item.variation ? ` · ${item.variation}` : ""}
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <div className="inline-flex items-center border border-zinc-300 rounded-lg text-sm">
                    <button className="px-2" onClick={() => setQuantity(item.lineId ?? item.variantId, item.quantity - 1)}>−</button>
                    <span className="px-1.5 tabular-nums">{item.quantity}</span>
                    <button className="px-2" onClick={() => setQuantity(item.lineId ?? item.variantId, item.quantity + 1)}>+</button>
                  </div>
                  <button onClick={() => removeItem(item.lineId ?? item.variantId)}
                    className="text-[11px] text-zinc-400 hover:text-red-600">Kaldır</button>
                </div>
              </div>
              <div className="text-sm font-semibold whitespace-nowrap">
                {formatPrice(Number(item.price) * item.quantity)}
              </div>
            </div>
          ))}
        </div>

        {items.length > 0 && (
          <div className="border-t border-zinc-200 p-4 space-y-2">
            {freeOver > 0 && (
              <div className="pb-1">
                {remaining > 0 ? (
                  <p className="text-[11px] text-zinc-600 mb-1">
                    🚚 Ücretsiz kargoya <b>{formatPrice(remaining)}</b> kaldı
                  </p>
                ) : (
                  <p className="text-[11px] text-emerald-600 mb-1 font-medium">
                    🎉 Kargonuz ücretsiz!
                  </p>
                )}
                <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-500"
                    style={{ width: `${Math.min(100, (subtotal / freeOver) * 100)}%` }}
                  />
                </div>
              </div>
            )}
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">Ara toplam</span>
              <span className="font-semibold">{formatPrice(subtotal)}</span>
            </div>
            {autoQuote && autoQuote.discount > 0 && (
              <>
                <div className="flex justify-between text-sm text-emerald-600 font-medium">
                  <span>🎁 Kampanya{autoQuote.code ? ` (${autoQuote.code})` : ""}</span>
                  <span>−{formatPrice(autoQuote.discount)}</span>
                </div>
                <div className="flex justify-between text-sm border-t border-zinc-100 pt-1.5">
                  <span className="text-zinc-500">Kampanyalı toplam</span>
                  <span className="font-semibold">
                    {formatPrice(Math.max(0, subtotal - autoQuote.discount))}
                  </span>
                </div>
              </>
            )}
            {autoQuote?.freeShipping && (
              <div className="text-xs text-emerald-600">🎁 Kampanya: kargo ücretsiz</div>
            )}
            <Link href="/odeme" onClick={() => setDrawerOpen(false)}
              className="block text-center rounded-xl text-white font-medium py-3 transition hover:opacity-90"
              style={{ background: "var(--c-primary)" }}>
              Ödemeye Geç
            </Link>
            <Link href="/sepet" onClick={() => setDrawerOpen(false)}
              className="block text-center text-xs text-zinc-500 hover:underline">
              Sepeti görüntüle
            </Link>
          </div>
        )}
      </aside>
    </>
  );
}
