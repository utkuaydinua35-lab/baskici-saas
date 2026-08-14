import type { Metadata } from "next";
import { getThemePayload } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Gizlilik ve KVKK Aydınlatma Metni",
};

// Marka adı MAĞAZADAN gelir — env tek değer tutar, oysa aynı kurulumda
// birden fazla mağaza var ve her biri kendi unvanını göstermeli.

// NOT: Bu metin bir şablondur — yayına almadan önce şirket unvanı, adres ve
// iletişim bilgileri doldurulmalı, gerekirse hukuk danışmanına onaylatılmalıdır.
export default async function PrivacyPage() {
  const { legal, store_name: SITE_NAME } = await getThemePayload();
  if (legal.kvkk) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-bold">Gizlilik Politikası ve KVKK Aydınlatma Metni</h1>
        <div className="mt-6 text-sm text-zinc-700 leading-relaxed whitespace-pre-line">{legal.kvkk}</div>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 prose-sm">
      <h1 className="text-2xl font-bold">Gizlilik Politikası ve KVKK Aydınlatma Metni</h1>
      <div className="mt-6 space-y-5 text-sm text-zinc-700 leading-relaxed">
        <section>
          <h2 className="font-semibold text-base text-zinc-900">1. Veri Sorumlusu</h2>
          <p className="mt-1">
            6698 sayılı Kişisel Verilerin Korunması Kanunu (&quot;KVKK&quot;) uyarınca kişisel
            verileriniz, veri sorumlusu sıfatıyla {SITE_NAME} (&quot;Şirket&quot;) tarafından
            aşağıda açıklanan kapsamda işlenmektedir.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">2. İşlenen Kişisel Veriler</h2>
          <p className="mt-1">Sipariş verdiğinizde yalnızca siparişin ifası için zorunlu olan veriler işlenir:</p>
          <ul className="list-disc pl-5 mt-1 space-y-0.5">
            <li>Ad ve soyad</li>
            <li>E-posta adresi ve telefon numarası</li>
            <li>Teslimat adresi</li>
            <li>Sipariş içeriği ve ödeme durumu (tutar, ödeme yöntemi — <b>kart bilgileriniz hariç</b>)</li>
          </ul>
          <p className="mt-2">
            <b>Kart bilgileriniz hiçbir zaman sistemlerimize ulaşmaz ve saklanmaz.</b> Ödeme,
            BDDK lisanslı ödeme kuruluşunun (iyzico / PayTR) güvenli sayfasında gerçekleşir.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">3. İşleme Amaçları ve Hukuki Sebep</h2>
          <p className="mt-1">
            Verileriniz; siparişinizin alınması, üretilmesi, kargolanması, faturalandırılması
            ve sipariş durumu hakkında bilgilendirme yapılması amacıyla, KVKK m.5/2-c
            (&quot;sözleşmenin kurulması ve ifası için zorunlu olması&quot;) hukuki sebebine
            dayanarak işlenir. Pazarlama amaçlı hiçbir işleme, açık rızanız olmadan yapılmaz.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">4. Aktarım</h2>
          <p className="mt-1">
            Verileriniz yalnızca siparişin ifası için zorunlu taraflara aktarılır: ödeme
            kuruluşu (ödeme doğrulaması), kargo firması (teslimat) ve yasal zorunluluk
            halinde yetkili kurumlar. Verileriniz bunun dışında hiçbir üçüncü tarafla
            paylaşılmaz, satılmaz ve yurt dışına aktarılmaz.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">5. Saklama Süresi</h2>
          <p className="mt-1">
            Tamamlanmış siparişlere ait kayıtlar, vergi ve ticaret mevzuatının öngördüğü
            süre boyunca saklanır. Tamamlanmayan (ödemesi gerçekleşmeyen) sipariş
            denemelerine ait kişisel veriler en geç 90 gün içinde sistemlerimizden silinir.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">6. Haklarınız</h2>
          <p className="mt-1">
            KVKK m.11 uyarınca; verilerinize erişme, düzeltilmesini veya silinmesini isteme,
            işlemeye itiraz etme ve zarara uğramanız hâlinde tazmin talep etme haklarına
            sahipsiniz. Talepleriniz için sipariş onay e-postasını yanıtlayarak veya web
            sitemizdeki iletişim kanallarından bize ulaşabilirsiniz. Başvurular en geç 30
            gün içinde ücretsiz olarak sonuçlandırılır.
          </p>
        </section>
        <section>
          <h2 className="font-semibold text-base text-zinc-900">7. Çerezler</h2>
          <p className="mt-1">
            Sitemiz yalnızca alışveriş deneyimi için zorunlu depolama kullanır (sepet
            içeriği tarayıcınızda saklanır). Takip ve reklam çerezi kullanılmaz.
          </p>
        </section>
      </div>
    </div>
  );
}
