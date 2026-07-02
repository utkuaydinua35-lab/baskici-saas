import Link from "next/link";
import { formatPrice } from "@/lib/format";
import type { ProductCard as ProductCardType } from "@/lib/api";

export default function ProductCard({ product }: { product: ProductCardType }) {
  return (
    <Link
      href={`/urun/${product.slug}`}
      className="group block rounded-2xl border border-zinc-200 overflow-hidden bg-white hover:shadow-md transition-shadow"
    >
      <div className="aspect-square bg-zinc-100 overflow-hidden">
        {product.cover_image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.cover_image}
            alt={product.title}
            className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform"
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
