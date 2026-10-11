// /favicon.ico, /apple-touch-icon.png → temadaki site simgesi.
// Tarayıcılar ve telefonlar (ana ekrana ekle, sekme, yer imi) <link rel="icon">
// olsa bile bu SABİT adresleri de ister; yoktu ve canlıda günde ~70 istek
// 404 alıyordu (iPhone'da ana ekrana eklenince simge boş çıkar).
import "server-only";
import { getThemePayload } from "@/lib/theme";

export async function simgeyeYonlendir(): Promise<Response> {
  try {
    const { theme } = await getThemePayload();
    const url = theme?.favicon_url || theme?.logo_url;
    if (url) {
      return new Response(null, {
        status: 302,
        headers: { Location: url, "Cache-Control": "public, max-age=3600" },
      });
    }
  } catch { /* tema okunamadı → 404 */ }
  return new Response(null, { status: 404, headers: { "Cache-Control": "public, max-age=300" } });
}
