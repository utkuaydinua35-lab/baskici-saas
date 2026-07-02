import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { formatPrice } from "@/lib/format";

export const metadata: Metadata = {
  title: "Sipariş Takibi",
  robots: { index: false, follow: false }, // token'lı sayfa indekslenmesin
};

interface OrderStatus {
  order_number: string;
  created_at: string | null;
  durum: { key: string; label: string; progress: number };
  kargo: { takip_no: string; takip_url: string | null; firma: string | null } | null;
  items: { title: string; variant_title: string | null; quantity: number }[];
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
            <li key={i} className="flex justify-between gap-3">
              <span className="text-zinc-700">
                {item.title}
                {item.variant_title && (
                  <span className="text-zinc-400"> — {item.variant_title}</span>
                )}
              </span>
              <span className="text-zinc-500 whitespace-nowrap">×{item.quantity}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4 pt-3 border-t border-zinc-100 flex justify-between text-sm font-semibold">
          <span>Toplam</span>
          <span>{formatPrice(order.amount, order.currency)}</span>
        </div>
      </div>

      <p className="mt-6 text-xs text-zinc-400 text-center">
        Sorunuz mu var? Sipariş onay e-postanızı yanıtlayarak bize ulaşabilirsiniz.
      </p>
    </div>
  );
}
