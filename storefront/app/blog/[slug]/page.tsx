import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getStoreSlug } from "@/lib/api";
import { jsonLdScript } from "@/lib/jsonld";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

interface Post {
  slug: string;
  title: string;
  excerpt: string | null;
  content: string;
  cover_url: string | null;
  seo_title: string | null;
  seo_description: string | null;
  published_at: string | null;
}

async function getPost(postSlug: string): Promise<Post | null> {
  try {
    const slug = await getStoreSlug();
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${slug}/blog/${encodeURIComponent(postSlug)}`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return null;
    return (await res.json()) as Post;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) return { title: "Yazı bulunamadı" };
  return {
    title: post.seo_title || post.title,
    description: post.seo_description || post.excerpt || undefined,
    openGraph: {
      title: post.seo_title || post.title,
      description: post.seo_description || post.excerpt || undefined,
      type: "article",
      ...(post.cover_url ? { images: [post.cover_url] } : {}),
    },
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    ...(post.published_at ? { datePublished: post.published_at } : {}),
    ...(post.cover_url ? { image: post.cover_url } : {}),
    ...(post.excerpt ? { description: post.excerpt } : {}),
  };

  return (
    <article className="mx-auto max-w-2xl px-4 py-10">
      <script type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />
      <Link href="/blog" className="text-xs text-zinc-500 hover:underline">← Tüm yazılar</Link>
      <h1 className="mt-3 text-3xl font-bold leading-tight">{post.title}</h1>
      {post.published_at && (
        <p className="mt-2 text-xs text-zinc-400">
          {new Date(post.published_at).toLocaleDateString("tr-TR", {
            day: "numeric", month: "long", year: "numeric",
          })}
        </p>
      )}
      {post.cover_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={post.cover_url} alt={post.title}
          className="mt-6 w-full rounded-2xl border border-zinc-200" />
      )}
      <div className="mt-8 text-[15px] leading-relaxed text-zinc-700 whitespace-pre-line">
        {post.content}
      </div>
      <div className="mt-10 border-t border-zinc-200 pt-6">
        <Link href="/urunler"
          className="inline-block rounded-xl text-white px-5 py-2.5 text-sm font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}>
          Ürünlere Göz At
        </Link>
      </div>
    </article>
  );
}
