import type { Metadata } from "next";
import Link from "next/link";
import { getStoreSlug } from "@/lib/api";

export const metadata: Metadata = {
  title: "Blog",
  description: "Rehberler, ipuçları ve haberler.",
};

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

interface PostCard {
  slug: string;
  title: string;
  excerpt: string | null;
  cover_url: string | null;
  published_at: string | null;
}

async function getPosts(): Promise<PostCard[]> {
  try {
    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/blog`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return [];
    return ((await res.json()) as { posts: PostCard[] }).posts ?? [];
  } catch {
    return [];
  }
}

export default async function BlogPage() {
  const posts = await getPosts();

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-bold">Blog</h1>
      {posts.length === 0 ? (
        <p className="mt-8 py-12 text-center text-sm text-zinc-400">Henüz yazı yayınlanmadı.</p>
      ) : (
        <div className="mt-8 space-y-6">
          {posts.map((p) => (
            <Link key={p.slug} href={`/blog/${p.slug}`}
              className="block rounded-2xl border border-zinc-200 bg-white overflow-hidden hover:shadow-md transition-shadow">
              {p.cover_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={p.cover_url} alt={p.title} className="w-full max-h-64 object-cover" />
              )}
              <div className="p-5">
                <h2 className="text-lg font-semibold">{p.title}</h2>
                {p.published_at && (
                  <p className="mt-1 text-xs text-zinc-400">
                    {new Date(p.published_at).toLocaleDateString("tr-TR", {
                      day: "numeric", month: "long", year: "numeric",
                    })}
                  </p>
                )}
                {p.excerpt && <p className="mt-2 text-sm text-zinc-600 line-clamp-3">{p.excerpt}</p>}
                <span className="mt-3 inline-block text-sm font-medium underline">Devamını oku →</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
