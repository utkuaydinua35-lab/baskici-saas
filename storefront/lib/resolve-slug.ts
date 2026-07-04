// Route handler'lar için host → slug çözümü (React cache'siz sade sürüm).
import "server-only";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const STORE_SLUG = process.env.STORE_SLUG || "vitrin";
const DEFAULT_HOSTS = new Set(
  (process.env.DEFAULT_HOSTS || "localhost,127.0.0.1")
    .split(",").map((h) => h.trim().toLowerCase()).filter(Boolean),
);

export async function resolveSlugFromHost(hostHeader: string | null): Promise<string> {
  const host = (hostHeader || "").toLowerCase().split(":")[0];
  if (!host || DEFAULT_HOSTS.has(host)) return STORE_SLUG;
  try {
    const res = await fetch(
      `${BACKEND_URL}/api/shop/_resolve?host=${encodeURIComponent(host)}`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return STORE_SLUG;
    const data = (await res.json()) as { slug?: string };
    return data.slug || STORE_SLUG;
  } catch {
    return STORE_SLUG;
  }
}
