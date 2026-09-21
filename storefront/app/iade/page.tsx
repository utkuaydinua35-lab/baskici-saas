import type { Metadata } from "next";
import { getThemePayload } from "@/lib/theme";

export const metadata: Metadata = {
  title: "İade ve Değişim",
};

export default async function ReturnsPage() {
  const { legal, contact, isletme } = await getThemePayload();
  if (legal.iade) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-bold">İade ve Değişim</h1>
        <div className="mt-6 text-sm text-zinc-700 leading-relaxed whitespace-pre-line">{legal.iade}</div>
      </div>
    );
  }
  // Varsayılan metin İŞLETMEYE göre kurulur. Eskiden tek bir şablon vardı ve
  // SİPARİŞE ÖZEL ÜRETİM yapan satıcıya özgüydü: "fikir değişikliğiyle iade
  // yok" diyordu. Bu istisna (Mesafeli Sözleşmeler Yönetmeliği m.15) yalnız
  // kişiye özel hazırlanan mallarda geçerli; standart ürün satan bir satıcıda
  // tüketiciyi 14 günlük YASAL cayma hakkından mahrum gösterir.
  const iletisim = contact.email
    ? <> <b>{contact.email}</b> adresine</>
    : " iletişim bilgilerimiz üzerinden";
  const tur = isletme.urun_turu ? `${isletme.urun_turu} ürünlerimiz` : "ürünlerimiz";

  if (!isletme.kisiye_ozel) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-bold">İade ve Değişim</h1>
        <div className="mt-6 space-y-5 text-sm text-zinc-700 leading-relaxed">
          <section>
            <h2 className="font-semibold text-base text-zinc-900">Cayma hakkı</h2>
            <p className="mt-1">
              Ürünü teslim aldığınız tarihten itibaren <b>14 gün içinde</b>, herhangi bir
              gerekçe göstermeden cayma hakkınızı kullanabilirsiniz. Cayma bildiriminizi
              {iletisim} iletmeniz yeterlidir. Ödemeniz, bildiriminizin bize ulaşmasından
              itibaren en geç 14 gün içinde iade edilir.
            </p>
          </section>
          <section>
            <h2 className="font-semibold text-base text-zinc-900">Hatalı veya hasarlı ürün</h2>
            <p className="mt-1">
              Ürününüz hatalı ya da hasarlı ulaştıysa, teslimattan sonra ürünün fotoğrafıyla
              birlikte{iletisim} bize ulaşın. Tüketici mevzuatından doğan haklarınız saklıdır.
            </p>
          </section>
        </div>
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
            {tur[0].toLocaleUpperCase("tr") + tur.slice(1)}, seçimleriniz doğrultusunda
            siparişinize özel üretilir. Bu nedenle yasal mevzuat gereği (Mesafeli
            Sözleşmeler Yönetmeliği m.15) <b>fikir değişikliği kaynaklı iade kabul
            edilememektedir.</b>
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">Hatalı veya hasarlı ürün</h2>
          <p className="mt-1">
            Ürününüz üretim hatalı, hasarlı ya da yanlış olarak ulaştıysa
            <b> ücretsiz olarak yenisini üretip gönderiyoruz.</b> Teslimattan itibaren 14 gün
            içinde, ürünün fotoğrafıyla birlikte{iletisim} bize ulaşmanız yeterli.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">Sipariş bilgisinde hata</h2>
          <p className="mt-1">
            Sipariş verirken yanlış bir seçim yaptıysanız ve siparişiniz henüz üretime
            girmediyse düzeltebiliriz — mümkün olan en kısa sürede bize ulaşın.
          </p>
        </section>
      </div>
    </div>
  );
}
