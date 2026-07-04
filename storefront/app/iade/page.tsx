import type { Metadata } from "next";
import { getThemePayload } from "@/lib/theme";

export const metadata: Metadata = {
  title: "İade ve Değişim",
};

export default async function ReturnsPage() {
  const { legal } = await getThemePayload();
  if (legal.iade) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-bold">İade ve Değişim</h1>
        <div className="mt-6 text-sm text-zinc-700 leading-relaxed whitespace-pre-line">{legal.iade}</div>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-bold">İade ve Değişim</h1>
      <div className="mt-6 space-y-5 text-sm text-zinc-700 leading-relaxed">
        <section>
          <h2 className="font-semibold text-base text-zinc-900">Kişiye özel üretim</h2>
          <p className="mt-1">
            Kılıflarımız, seçtiğiniz telefon modeline ve tasarıma göre siparişinize özel
            üretilir. Bu nedenle yasal mevzuat gereği (Mesafeli Sözleşmeler Yönetmeliği
            m.15/1-c) <b>fikir değişikliği kaynaklı iade kabul edilememektedir.</b>
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">Hatalı veya hasarlı ürün</h2>
          <p className="mt-1">
            Ürününüz baskı hatalı, hasarlı veya yanlış model olarak ulaştıysa üzülmeyin —
            <b> ücretsiz olarak yenisini üretip gönderiyoruz.</b> Teslimattan itibaren 14 gün
            içinde, sipariş onay e-postanızı yanıtlayarak ürünün fotoğrafıyla birlikte bize
            ulaşmanız yeterli. Talebiniz 2 iş günü içinde yanıtlanır.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">Yanlış model seçimi</h2>
          <p className="mt-1">
            Sipariş verirken yanlış telefon modeli seçtiyseniz ve siparişiniz henüz baskıya
            girmediyse düzeltebiliriz — mümkün olan en kısa sürede bize ulaşın.
          </p>
        </section>
      </div>
    </div>
  );
}
