"use client";

// Kupon kodu girişi — doğrulama sunucuda; geçerliyse cart context'e yazılır.
// Paylaşım linkiyle (?kupon=KOD) gelen kod localStorage'da bekler, sepette
// ürün olunca otomatik uygulanır.
import { useEffect, useState } from "react";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";

export const PENDING_COUPON_KEY = "bernz_pending_coupon";

export default function CouponInput({ email }: { email?: string }) {
  const { items, coupon, setCoupon } = useCart();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Paylaşım linkinden gelen bekleyen kupon — sepet doluysa otomatik dene
  useEffect(() => {
    if (coupon || items.length === 0) return;
    let pending: string | null = null;
    try { pending = localStorage.getItem(PENDING_COUPON_KEY); } catch { /* yok */ }
    if (!pending) return;
    try { localStorage.removeItem(PENDING_COUPON_KEY); } catch { /* yok */ }
    applyCode(pending);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length]);

  const apply = async () => {
    applyCode(code);
  };

  const applyCode = async (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/validate-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: trimmed,
          items: items.map((i) => ({
            variant_id: i.variantId, quantity: i.quantity,
            second_variant_id: i.secondVariantId || null,
            custom: i.custom || null,
          })),
          email: email || null,
        }),
      });
      const data = await res.json();
      if (data.valid) {
        setCoupon({
          code: data.code,
          kind: data.kind,
          discountAmount: data.discount_amount,
          freeShipping: data.free_shipping,
        });
        setCode("");
      } else {
        setError(data.message || "Kupon geçersiz");
      }
    } catch {
      setError("Doğrulama başarısız, tekrar deneyin");
    } finally {
      setBusy(false);
    }
  };

  if (coupon) {
    return (
      <div className="flex items-center justify-between gap-2 text-sm bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2">
        <span className="text-emerald-700">
          🎟️ <b className="font-mono">{coupon.code}</b>
          {coupon.freeShipping
            ? " — ücretsiz kargo"
            : ` — ${formatPrice(coupon.discountAmount)} indirim`}
        </span>
        <button onClick={() => setCoupon(null)} className="text-xs text-emerald-600 underline">
          Kaldır
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), apply())}
          placeholder="Kupon kodu"
          className="flex-1 min-w-0 rounded-xl border border-zinc-300 px-3 py-2 text-sm font-mono uppercase bg-white"
          maxLength={40}
        />
        <button
          type="button"
          onClick={apply}
          disabled={busy || !code.trim()}
          className="shrink-0 whitespace-nowrap px-4 py-2 rounded-xl border border-zinc-900 text-sm font-medium disabled:opacity-40 hover:bg-zinc-900 hover:text-white transition"
        >
          {busy ? "…" : "Uygula"}
        </button>
      </div>
      {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}
    </div>
  );
}
