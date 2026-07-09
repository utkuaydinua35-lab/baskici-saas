import Link from "next/link";
import { formatPrice } from "@/lib/format";
import type { ProductCard as ProductCardType } from "@/lib/api";

export default function ProductCard({ product }: { product: ProductCardType }) {
  const price = Number(product.price);
  const compareAt = product.compare_at_price ? Number(product.compare_at_price) : null;
  const discountPct =
    compareAt && compareAt > price ? Math.round(((compareAt - price) / compareAt) * 100) : null;
  const lowStock =
    product.total_stock != null && product.total_stock > 0 && product.total_stock < 5
      ? product.total_stock
      : null;

  return (
    <Link
      href={`/urun/${product.slug}`}
      className="group relative block rounded-2xl border border-zinc-200 overflow-hidden bg-white hover:shadow-md transition-shadow"
    >
      {(discountPct != null || lowStock != null) && (
        <div className="absolute top-2 left-2 z-10 flex flex-col items-start gap-1">
          {discountPct != null && (
            <span
              className="text-[11px] font-semibold text-white rounded-full px-2 py-0.5"
              style={{ background: "var(--c-accent)" }}
            >
              %{discountPct} İNDİRİM
            </span>
          )}
          {lowStock != null && (
            <span className="text-[11px] font-medium bg-red-50 text-red-700 border border-red-200 rounded-full px-2 py-0.5">
              Son {lowStock} adet
            </span>
          )}
        </div>
      )}
      <div className="aspect-square bg-zinc-100 overflow-hidden hover-zoom">
        {product.cover_image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.cover_image}
            alt={product.title}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-4xl text-zinc-300">
            📱
          </div>
        )}
      </div>
      <div className="p-3">
        <h3 className="text-sm font-medium text-zinc-900 line-clamp-2">{product.title}</h3>
        <div className="mt-1.5 flex items-baseline gap-2">
          <span className="font-semibold">{formatPrice(product.price, product.currency)}</span>
          {product.compare_at_price && (
            <span className="text-xs text-zinc-400 line-through">
              {formatPrice(product.compare_at_price, product.currency)}
            </span>
          )}
        </div>
        {product.model_count > 0 && (
          <div className="mt-1 text-xs text-zinc-500">{product.model_count} model için uygun</div>
        )}
      </div>
    </Link>
  );
}
