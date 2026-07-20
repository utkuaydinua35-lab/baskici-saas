import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getStoreSlug } from "@/lib/api";

// Özel sayfa — panelden yönetilir; düz metin, satır sonları korunur.
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

interface CustomPage {
  slug: string;
  title: string;
  content: string;
  images?: string[];
  cta_text?: string;
  cta_url?: string;
}

async function getPage(pageSlug: string): Promise<CustomPage | null> {
  try {
    const storeSlug = await getStoreSlug();
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${storeSlug}/pages/${encodeURIComponent(pageSlug)}`,
      { next: { revalidate: 60 } },
    );
    if (!res.ok) return null;
    return (await res.json()) as CustomPage;
  } catch {
    return null;
  }
}

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const page = await getPage(slug);
  return { title: page?.title ?? "Sayfa bulunamadı" };
}

export default async function CustomPageView({ params }: Props) {
  const { slug } = await params;
  const page = await getPage(slug);
  if (!page) notFound();

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-bold">{page.title}</h1>
      {/* Sayfaya özel görseller (panelden yüklenir — örn. tutorial) */}
      {(page.images ?? []).length > 0 && (
        <div className="mt-6 space-y-4">
          {page.images!.map((url) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={url} src={url} alt={page.title}
              className="w-full rounded-2xl border border-zinc-200" />
          ))}
        </div>
      )}
      <div className="mt-6 text-sm text-zinc-700 leading-relaxed whitespace-pre-line">
        {page.content}
      </div>
      {/* Yönlendirme butonu — panelden hedef seçilir (koleksiyon/ürünler/sayfa) */}
      {page.cta_text && page.cta_url && (
        <a href={page.cta_url}
          className="mt-8 inline-block rounded-xl text-white px-6 py-3 text-sm font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}>
          {page.cta_text}
        </a>
      )}
    </div>
  );
}
