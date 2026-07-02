import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mesafeli Satış Sözleşmesi",
};

const SITE_NAME = process.env.SITE_NAME || "Bernz";

// NOT: Şablondur — yayına almadan önce satıcı unvan/adres/MERSİS bilgileri
// doldurulmalı ve hukuk danışmanına onaylatılmalıdır.
export default function DistanceSalesPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-bold">Mesafeli Satış Sözleşmesi</h1>
      <div className="mt-6 space-y-5 text-sm text-zinc-700 leading-relaxed">
        <section>
          <h2 className="font-semibold text-base text-zinc-900">1. Taraflar</h2>
          <p className="mt-1">
            İşbu sözleşme, {SITE_NAME} (&quot;Satıcı&quot;) ile sipariş formunda bilgileri yer
            alan müşteri (&quot;Alıcı&quot;) arasında, 6502 sayılı Tüketicinin Korunması
            Hakkında Kanun ve Mesafeli Sözleşmeler Yönetmeliği uyarınca elektronik
            ortamda kurulmuştur.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">2. Konu ve Ürün</h2>
          <p className="mt-1">
            Sözleşmenin konusu, Alıcı&apos;nın sipariş formunda belirttiği, telefon modeli
            ve tasarım seçimine göre <b>kişiye özel olarak üretilen</b> baskılı telefon
            kılıfı ürünlerinin satışı ve teslimidir. Ürün özellikleri ve toplam bedel
            (vergiler dahil) sipariş özetinde ve onay e-postasında belirtilir.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">3. Teslimat</h2>
          <p className="mt-1">
            Ürünler siparişe özel üretilir ve ödemenin onaylanmasından itibaren
            ortalama 1–3 iş günü içinde kargoya teslim edilir. Teslimat, Alıcı&apos;nın
            bildirdiği adrese kargo firması aracılığıyla yapılır. Kargo takip numarası
            Alıcı&apos;ya e-posta ile bildirilir.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">4. Cayma Hakkı</h2>
          <p className="mt-1">
            Mesafeli Sözleşmeler Yönetmeliği m.15/1-c uyarınca, <b>tüketicinin istekleri
            doğrultusunda ya da kişisel ihtiyaçlarına göre hazırlanan mallarda cayma
            hakkı kullanılamaz.</b> Telefon modeline ve tasarım seçimine göre üretilen
            kılıflar bu kapsamdadır. Ayıplı (hasarlı, baskı hatalı, yanlış model) ürünlerde
            Alıcı&apos;nın yasal hakları saklıdır — bkz. İade ve Değişim.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">5. Ödeme</h2>
          <p className="mt-1">
            Ödeme, BDDK lisanslı ödeme kuruluşunun güvenli sayfası üzerinden kredi/banka
            kartı ile alınır. Satıcı, kart bilgilerine erişemez ve bunları saklamaz.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">6. Uyuşmazlık</h2>
          <p className="mt-1">
            Uyuşmazlıklarda, Ticaret Bakanlığı&apos;nca ilan edilen parasal sınırlar
            dahilinde Alıcı&apos;nın yerleşim yerindeki Tüketici Hakem Heyetleri ve
            Tüketici Mahkemeleri yetkilidir.
          </p>
        </section>
      </div>
    </div>
  );
}
