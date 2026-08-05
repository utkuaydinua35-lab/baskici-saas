// Tema cache'ini anında düşür — panel "Kaydet ve Yayınla" sonrası backend
// çağırır; yoksa vitrin 60 sn eski temayı (eski favicon/renk/menü) gösterir.
// Koruma yok: tek etkisi cache tazelenmesi (veri sızdırmaz, yazma yapmaz).
import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

export async function POST() {
  // Panelden gelen sinyal → anında geçersiz kıl (bkz. revalidate-katalog).
  // "max" ile mağaza sahibi ilk yenilemede eski temayı görüyordu.
  revalidateTag("theme", { expire: 0 });
  return NextResponse.json({ revalidated: true });
}
