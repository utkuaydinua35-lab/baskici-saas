import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { formatPrice } from "@/lib/format";
import ReviewForm from "@/components/ReviewForm";
import OrderRequestForm from "@/components/OrderRequestForm";

export const metadata: Metadata = {
  title: "Sipariş Takibi",
  robots: { index: false, follow: false }, // token'lı sayfa indekslenmesin
};

interface OrderStatus {
  order_number: string;
  created_at: string | null;
  durum: { key: string; label: string; progress: number };
  kargo: { takip_no: string; takip_url: string | null; firma: string | null } | null;
  items: { title: string; variant_title: string | null; quantity: number; product_slug?: string | null }[];
  amount: string;
  shipping_amount: string;
  currency: string;
}

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

async function getOrder(token: string): Promise<OrderStatus | null> {
  if (!/^[A-Za-z0-9_-]{20,80}$/.test(token)) return null;
  try {
    const res = await fetch(
      `${BACKEND_URL}/api/shop/orders/${encodeURIComponent(token)}`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as OrderStatus;
  } catch {
    return null;
  }
}

export default async function OrderTrackPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const order = await getOrder(token);
  if (!order) notFound();

  return (
    <div className="mx-auto max-w-xl px-4 py-10">
      <h1 className="text-xl font-semibold">Sipariş #{order.order_number}</h1>
      {order.created_at && (
        <p className="mt-1 text-xs text-zinc-500">
          {new Date(order.created_at).toLocaleDateString("tr-TR", {
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
        </p>
      )}

      <div className="mt-6 bg-white border border-zinc-200 rounded-2xl p-5">
        <div className="flex items-center justify-between">
          <span className="font-medium">{order.durum.label}</span>
          <span className="text-xs text-zinc-500">%{order.durum.progress}</span>
        </div>
        <div className="mt-2 h-2 rounded-full bg-zinc-100 overflow-hidden">
          <div
            className="h-full bg-emerald-500 transition-all"
            style={{ width: `${order.durum.progress}%` }}
          />
        </div>
        {/* Adım göstergesi — Shopify sipariş durumu sayfası hissi */}
        <div className="mt-4 grid grid-cols-4 gap-1 text-center">
          {[
            ["Onaylandı", 5],
            ["Hazırlanıyor", 30],
            ["Kargoda", 80],
            ["Teslim", 100],
          ].map(([label, threshold]) => {
            const reached = order.durum.progress >= Number(threshold);
            return (
              <div key={label as string} className="flex flex-col items-center gap-1">
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold ${
                    reached ? "bg-emerald-500 text-white" : "bg-zinc-100 text-zinc-400"
                  }`}
                >
                  {reached ? "✓" : ""}
                </span>
                <span className={`text-[10px] ${reached ? "text-zinc-700 font-medium" : "text-zinc-400"}`}>
                  {label}
                </span>
              </div>
            );
          })}
        </div>
        {order.kargo && (
          <div className="mt-4 text-sm">
            <span className="text-zinc-500">Kargo:</span>{" "}
            {order.kargo.firma && <span>{order.kargo.firma} — </span>}
            {order.kargo.takip_url ? (
              <a href={order.kargo.takip_url} className="underline" target="_blank" rel="noopener">
                {order.kargo.takip_no}
              </a>
            ) : (
              <span className="font-mono">{order.kargo.takip_no}</span>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 bg-white border border-zinc-200 rounded-2xl p-5">
        <h2 className="text-sm font-semibold mb-3">Sipariş İçeriği</h2>
        <ul className="space-y-2 text-sm">
          {order.items.map((item, i) => (
            <li key={i}>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-700">
                  {item.title}
                  {item.variant_title && (
                    <span className="text-zinc-400"> — {item.variant_title}</span>
                  )}
                </span>
                <span className="text-zinc-500 whitespace-nowrap">×{item.quantity}</span>
              </div>
              {item.product_slug && (
                <ReviewForm lookupToken={token} productSlug={item.product_slug}
                  productTitle={item.title} />
              )}
            </li>
          ))}
        </ul>
        <div className="mt-4 pt-3 border-t border-zinc-100 flex justify-between text-sm font-semibold">
          <span>Toplam</span>
          <span>{formatPrice(order.amount, order.currency)}</span>
        </div>
      </div>

      <OrderRequestForm token={token} />

      <p className="mt-6 text-xs text-zinc-400 text-center">
        Sorunuz mu var? Sipariş onay e-postanızı yanıtlayarak bize ulaşabilirsiniz.
      </p>
    </div>
  );
}
