// Katalog cache'ini anında düşür — panelde ürün/koleksiyon/varyant değişince
// backend burayı çağırır; yoksa vitrin 60 sn'ye kadar eski fiyatı, eski stok
// durumunu ya da silinmiş ürünü göstermeye devam eder.
// Koruma yok: tek etkisi önbellek tazelenmesi (veri sızdırmaz, yazma yapmaz).
import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

export async function POST() {
  // { expire: 0 } — Next 16 dokümanının DIŞ SİSTEM (webhook) senaryosu için
  // önerdiği biçim: etiket anında geçersizleşir, ilk istek taze veriyi görür.
  // "max" profili stale-while-revalidate'tir; panelde kaydeden kişi ilk
  // yenilemede hâlâ ESKİ içeriği görürdü.
  revalidateTag("katalog", { expire: 0 });
  return NextResponse.json({ revalidated: true });
}
