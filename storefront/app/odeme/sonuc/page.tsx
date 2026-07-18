import type { Metadata } from "next";
import { getThemePayload } from "@/lib/theme";
import ResultClient from "./ResultClient";

export const metadata: Metadata = { title: "Sipariş Sonucu" };

// Sunucu sarmalayıcı: temadaki teşekkür metinlerini istemci sonuç
// görünümüne geçirir. ?demo=1 yalnız tema editörü önizlemesinde çalışır.
export default async function ResultPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [payload, sp] = await Promise.all([getThemePayload(), searchParams]);
  // onizleme=1 parametresi de kabul edilir: editör iframe'inin İLK isteğinde
  // vitrin_onizleme çerezi henüz yazılmamış olur (middleware yanıtla yazar) —
  // yalnız çereze bakılırsa ilk açılış "Geçersiz bağlantı"ya düşer.
  const demo = sp.demo === "1" && (payload.is_preview || sp.onizleme === "1");
  return <ResultClient thankyou={payload.theme.thankyou ?? null} demo={demo} />;
}
