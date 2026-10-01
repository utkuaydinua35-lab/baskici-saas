import Link from "next/link";
import { formatPrice } from "@/lib/format";
import type { ProductCard as ProductCardType } from "@/lib/api";
import FavButton from "@/components/FavButton";
import CardMedia from "@/components/CardMedia";

export default function ProductCard({ product, oncelikli = false }: {
  product: ProductCardType;
  // Sayfa açılışında görünen kart: görsel tembel değil, yüksek öncelikli
  oncelikli?: boolean;
}) {
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
      className="urun-kart group relative block rounded-2xl border border-zinc-200 overflow-hidden bg-white hover:shadow-md transition-shadow"
    >
      <FavButton item={{ slug: product.slug, title: product.title, price: product.price,
        currency: product.currency, image: product.cover_image }} />
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
      <CardMedia
        cover={product.cover_image}
        hoverImage={product.hover_image}
        videoUrl={product.video_url}
        title={product.title}
        oncelikli={oncelikli}
      />
      <div className="urun-kart-bilgi p-3">
        <h3 className="urun-kart-baslik text-sm font-medium text-zinc-900 line-clamp-2">{product.title}</h3>
        <div className="urun-kart-fiyat mt-1.5 flex items-baseline gap-2">
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
