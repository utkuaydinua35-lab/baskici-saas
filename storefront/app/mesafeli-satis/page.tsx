import type { Metadata } from "next";
import { getThemePayload } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Mesafeli Satış Sözleşmesi",
};

// Marka adı MAĞAZADAN gelir — env tek değer tutar, oysa aynı kurulumda
// birden fazla mağaza var ve her biri kendi unvanını göstermeli.

// NOT: Şablondur — yayına almadan önce satıcı unvan/adres/MERSİS bilgileri
// doldurulmalı ve hukuk danışmanına onaylatılmalıdır.
export default async function DistanceSalesPage() {
  const { legal, isletme, store_name: SITE_NAME } = await getThemePayload();
  // Ürün tanımı, teslim süresi ve cayma istisnası İŞLETMEYE göre — eskiden
  // BERNZ'in şartları (baskılı telefon kılıfı, 1–3 iş günü, cayma yok)
  // her mağazanın sözleşmesine sabit yazılıydı.
  const urun = isletme.urun_turu || "ürün";
  if (legal.mesafeli_satis) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-bold">Mesafeli Satış Sözleşmesi</h1>
        <div className="mt-6 text-sm text-zinc-700 leading-relaxed whitespace-pre-line">{legal.mesafeli_satis}</div>
      </div>
    );
  }
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
            Sözleşmenin konusu, Alıcı&apos;nın sipariş formunda belirttiği
            {isletme.kisiye_ozel
              ? <>, tercihleri doğrultusunda <b>kişiye özel olarak üretilen</b> {urun}</>
              : <> {urun}</>} ürünlerinin satışı ve teslimidir. Ürün özellikleri ve toplam
            bedel (vergiler dahil) sipariş özetinde ve onay e-postasında belirtilir.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">3. Teslimat</h2>
          <p className="mt-1">
            {isletme.kisiye_ozel ? "Ürünler siparişe özel üretilir ve ödemenin" : "Ürünler ödemenin"}
            {" "}onaylanmasından itibaren{" "}
            {isletme.teslim_suresi
              ? <>ortalama {isletme.teslim_suresi} içinde</>
              // Süre tanımlı değilse yasal üst sınır — boş bir taahhüt yazılmaz
              : <>yasal süre olan 30 günü aşmamak kaydıyla</>}
            {" "}kargoya teslim edilir. Teslimat, Alıcı&apos;nın
            bildirdiği adrese kargo firması aracılığıyla yapılır. Kargo takip numarası
            Alıcı&apos;ya e-posta ile bildirilir.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">4. Cayma Hakkı</h2>
          {isletme.kisiye_ozel ? (
            <p className="mt-1">
              Mesafeli Sözleşmeler Yönetmeliği m.15 uyarınca, <b>tüketicinin istekleri
              doğrultusunda ya da kişisel ihtiyaçlarına göre hazırlanan mallarda cayma
              hakkı kullanılamaz.</b> Alıcı&apos;nın tercihine göre üretilen ürünler bu
              kapsamdadır. Ayıplı (hasarlı, üretim hatalı, yanlış) ürünlerde Alıcı&apos;nın
              yasal hakları saklıdır — bkz. İade ve Değişim.
            </p>
          ) : (
            // Standart ürün: YASAL 14 günlük cayma hakkı. Eskiden istisna metni
            // her mağazaya gidiyordu ve bu durumda hukuken geçersizdi.
            <p className="mt-1">
              Alıcı, malın kendisine teslim edildiği tarihten itibaren <b>14 gün içinde</b>
              {" "}herhangi bir gerekçe göstermeksizin ve cezai şart ödemeksizin cayma hakkını
              kullanabilir. Cayma bildiriminin Satıcı&apos;ya ulaşmasından itibaren en geç 14
              gün içinde ödeme iade edilir — bkz. İade ve Değişim.
            </p>
          )}
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
