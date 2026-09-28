// Ayarlar → Pazarlama: Google ve Meta reklam pikseli kurulum rehberi.
//
// Vitrinin gerçekte gönderdiği olaylara göre yazıldı (storefront/lib/track.ts):
//   Meta  → PageView, ViewContent, AddToCart, InitiateCheckout, AddPaymentInfo,
//           Purchase (+ sunucudan Conversions API ile AYNI event_id)
//   GA4   → page_view, view_item, add_to_cart, begin_checkout, add_payment_info,
//           purchase (transaction_id + value + currency)
// Google Ads için ayrı kod alanı YOK — dönüşüm GA4'teki "purchase" olayından
// içe aktarılır; bu yüzden rehber o yolu anlatır.
import { useState } from 'react'

// Kimlik biçimi denetimi — en sık hatalar: GA4 alanına Google Ads (AW-) ya da
// eski Universal Analytics (UA-) kimliği, ya da kodun tamamını yapıştırmak.
export function pikselUyarisi(tur, deger) {
  const v = (deger || '').trim()
  // Kayıtlı gizli alan maskeli döner ("••••••••1234") — kayıtlıdır, denetlenmez
  if (!v || v.includes('••')) return null
  if (v.includes('<') || v.includes('script')) return 'Kodun tamamını değil yalnız kimliği (ID) yapıştırın.'
  if (tur === 'ga4') {
    if (/^AW-/i.test(v)) return 'Bu bir Google Ads kimliği (AW-). Buraya GA4 Ölçüm Kimliği (G-…) girilir — Google Ads dönüşümü GA4\'ten içe aktarılır (rehbere bakın).'
    if (/^UA-/i.test(v)) return 'UA- kimliği eski Universal Analytics\'e ait ve 2023\'te kapandı. GA4 Ölçüm Kimliği (G-…) gerekir.'
    if (/^GTM-/i.test(v)) return 'Bu bir Etiket Yöneticisi (GTM) kimliği. Buraya GA4 Ölçüm Kimliği (G-…) girilir.'
    if (!/^G-[A-Z0-9]{6,}$/i.test(v)) return 'GA4 Ölçüm Kimliği "G-" ile başlar, örn. G-AB12CD34EF.'
  }
  if (tur === 'meta' && !/^\d{14,17}$/.test(v)) return 'Meta Piksel Kimliği yalnız rakamdan oluşur (15-16 hane).'
  if (tur === 'capi' && v.length < 50) return 'Erişim anahtarı çok kısa görünüyor — Olay Yöneticisi\'nden tamamını kopyalayın.'
  return null
}

function Adim({ no, children }) {
  return (
    <li className="flex gap-2.5">
      <span className="shrink-0 grid h-5 w-5 place-items-center rounded-full bg-panel-input text-[11px] font-semibold">{no}</span>
      <div className="text-[12px] leading-relaxed text-panel-ink/90">{children}</div>
    </li>
  )
}

function Dis({ href, children }) {
  return <a href={href} target="_blank" rel="noopener noreferrer" className="underline hover:text-panel-ink">{children} ↗</a>
}

function Kart({ baslik, durum, acik, onToggle, children }) {
  return (
    <div className="rounded-xl border border-panel-border">
      <button type="button" onClick={onToggle}
        className="w-full flex items-center justify-between gap-2 px-3 py-2.5 text-left">
        <span className="text-sm font-medium">{baslik}</span>
        <span className="flex items-center gap-2">
          {durum}
          <span className="text-panel-muted text-xs">{acik ? '▲' : '▼'}</span>
        </span>
      </button>
      {acik && <div className="px-3 pb-3 space-y-3">{children}</div>}
    </div>
  )
}

function Rozet({ tamam, yazi }) {
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full ${tamam
      ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-500/15 text-panel-muted'}`}>{yazi}</span>
  )
}

export default function PikselRehberi({ cfg }) {
  const [acik, setAcik] = useState(null)
  const ga4Tamam = !!cfg.ga4_id && !pikselUyarisi('ga4', cfg.ga4_id)
  const metaTamam = !!cfg.meta_pixel_id && !pikselUyarisi('meta', cfg.meta_pixel_id)
  const capiTamam = !!cfg.meta_capi_token && !pikselUyarisi('capi', cfg.meta_capi_token)
  const ac = k => setAcik(a => (a === k ? null : k))

  return (
    <div className="space-y-2">
      <div className="text-sm font-medium">📘 Kurulum rehberi</div>

      <Kart baslik="Google (Analytics 4 + Google Ads)" acik={acik === 'google'} onToggle={() => ac('google')}
        durum={<Rozet tamam={ga4Tamam} yazi={ga4Tamam ? 'GA4 bağlı' : 'kurulmadı'} />}>
        <div>
          <div className="text-xs font-semibold mb-1.5">A · Google Analytics 4 (ölçüm)</div>
          <ol className="space-y-1.5">
            <Adim no={1}><Dis href="https://analytics.google.com">analytics.google.com</Dis>'a mağazanın Google hesabıyla girin.
              Hesabınız yoksa <b>Ölçüme başla</b> → hesap adı → mülk adı (mağaza adı), saat dilimi <b>Türkiye</b>, para birimi <b>TL</b>.</Adim>
            <Adim no={2}><b>Yönetici</b> (sol alttaki dişli) → <b>Veri akışları</b> → <b>Akış ekle → Web</b>. Web sitesi adresine
              vitrininizin adresini yazın (örn. <code>https://magaza.alanadiniz.com</code>).</Adim>
            <Adim no={3}>Açılan pencerede <b>Ölçüm Kimliği</b>'ni (<code>G-</code> ile başlar) kopyalayın.</Adim>
            <Adim no={4}>Yukarıdaki <b>GA4 Ölçüm ID</b> alanına yapıştırıp <b>Kaydet</b>'e basın. Başka kod eklemeniz gerekmez;
              ürün görüntüleme, sepete ekleme, ödeme ve satın alma olayları vitrin tarafından otomatik gönderilir.</Adim>
            <Adim no={5}><b>Kontrol:</b> GA4 → <b>Raporlar → Gerçek zamanlı</b>'yı açın, vitrininizi başka bir sekmede gezin.
              1-2 dakika içinde kendinizi görmelisiniz.</Adim>
          </ol>
        </div>
        <div>
          <div className="text-xs font-semibold mb-1.5">B · Google Ads dönüşümü (satışları reklama bağlama)</div>
          <p className="text-[11px] text-panel-muted mb-1.5">
            Ayrı bir Google Ads kodu gerekmez: satış, GA4'teki <code>purchase</code> olayından içe aktarılır
            (sipariş numarası ve tutarıyla).
          </p>
          <ol className="space-y-1.5">
            <Adim no={1}>GA4 → <b>Yönetici → Ürün bağlantıları → Google Ads bağlantıları → Bağla</b> → reklam hesabınızı seçin.</Adim>
            <Adim no={2}><Dis href="https://ads.google.com">ads.google.com</Dis> → <b>Hedefler → Dönüşümler → Özet</b> →
              <b> + Yeni dönüşüm işlemi → İçe aktar → Google Analytics 4 mülkleri → Web</b>.</Adim>
            <Adim no={3}>Listeden <b>purchase</b>'ı seçip <b>İçe aktar ve devam et</b>. Değer olarak "her dönüşüm için farklı
              değer kullan"ı seçin — tutar vitrinden geliyor.</Adim>
            <Adim no={4}>Google Ads → <b>Yönetici → Hesap ayarları → Otomatik etiketleme</b> açık olsun (reklam tıklamasıyla
              satışın eşleşmesi için).</Adim>
            <Adim no={5}>İçe aktarılan dönüşümler Google Ads'te <b>24-48 saat</b> içinde görünmeye başlar; bu normaldir.</Adim>
          </ol>
        </div>
      </Kart>

      <Kart baslik="Meta (Facebook + Instagram reklamları)" acik={acik === 'meta'} onToggle={() => ac('meta')}
        durum={<span className="flex gap-1">
          <Rozet tamam={metaTamam} yazi={metaTamam ? 'Piksel bağlı' : 'kurulmadı'} />
          {metaTamam && <Rozet tamam={capiTamam} yazi={capiTamam ? 'CAPI açık' : 'CAPI yok'} />}
        </span>}>
        <div>
          <div className="text-xs font-semibold mb-1.5">A · Meta Pikseli</div>
          <ol className="space-y-1.5">
            <Adim no={1}><Dis href="https://business.facebook.com/events_manager2">Olay Yöneticisi</Dis>'ni
              (Events Manager) reklam hesabınızın bağlı olduğu işletme hesabıyla açın.</Adim>
            <Adim no={2}><b>Veri kaynaklarını bağla → Web → Meta Pikseli</b> → piksele bir ad verin (örn. mağaza adı) → Oluştur.
              Web sitesi adresi sorulursa vitrin adresinizi yazın.</Adim>
            <Adim no={3}>Kurulum yöntemi sorulduğunda kod kopyalamanız gerekmez. Pikselin <b>Ayarlar</b> sekmesindeki
              <b> Piksel Kimliği</b>'ni (15-16 haneli sayı) kopyalayın.</Adim>
            <Adim no={4}>Yukarıdaki <b>Meta Pixel ID</b> alanına yapıştırıp <b>Kaydet</b>'e basın.</Adim>
            <Adim no={5}><b>Kontrol:</b> Olay Yöneticisi → pikseliniz → <b>Olayları test et</b> → vitrin adresinizi yazıp
              <b> Web sitesini aç</b>. Açılan sekmede ürüne girin, sepete ekleyin: <code>PageView</code>,
              <code> ViewContent</code>, <code>AddToCart</code> ekranda görünmeli.</Adim>
          </ol>
        </div>
        <div>
          <div className="text-xs font-semibold mb-1.5">B · Conversions API (önerilir)</div>
          <p className="text-[11px] text-panel-muted mb-1.5">
            Reklam engelleyiciler ve iOS kısıtları tarayıcı pikselini susturur; satın alma olayı sunucudan da
            gönderilirse kaçan satışlar yakalanır. Meta iki kaynağı tekilleştirir, çift sayılmaz.
          </p>
          <ol className="space-y-1.5">
            <Adim no={1}>Olay Yöneticisi → pikseliniz → <b>Ayarlar → Conversions API → Erişim anahtarı oluştur</b>.</Adim>
            <Adim no={2}>Anahtarı (<code>EAA…</code> ile başlayan uzun metin) <b>CAPI erişim jetonu</b> alanına yapıştırıp kaydedin.
              Anahtar yalnız bir kez gösterilir — kaybederseniz yenisini oluşturun.</Adim>
            <Adim no={3}><b>Test etmek için:</b> <b>Olayları test et</b> sekmesindeki test kodunu (<code>TEST…</code>)
              <b> Test olay kodu</b> alanına girin, kendiniz küçük bir test siparişi verin; <code>Purchase</code> "Sunucu"
              kaynağıyla görünmeli.</Adim>
            <Adim no={4}><b>Test bitince test kodunu silip kaydedin</b> — doluyken satışlar reklam raporlarına değil yalnız
              test ekranına düşer.</Adim>
          </ol>
        </div>
        <div>
          <div className="text-xs font-semibold mb-1.5">C · Alan adı doğrulama</div>
          <ol className="space-y-1.5">
            <Adim no={1}><Dis href="https://business.facebook.com/settings">İşletme Ayarları</Dis> → <b>Marka güvenliği →
              Alan adları → Ekle</b> → alan adınızı yazın (örn. <code>alanadiniz.com</code>).</Adim>
            <Adim no={2}>Doğrulama yöntemi olarak <b>DNS TXT kaydı</b>'nı seçin; verilen kaydı alan adınızın DNS panelinde
              (ör. Cloudflare → DNS → Kayıt ekle → TXT) ekleyin, sonra Meta'da <b>Doğrula</b>'ya basın.</Adim>
          </ol>
        </div>
      </Kart>

      <Kart baslik="Olaylar görünmüyorsa" acik={acik === 'sorun'} onToggle={() => ac('sorun')} durum={null}>
        <ul className="list-disc pl-4 space-y-1 text-[12px] text-panel-ink/90">
          <li>Kimlik alanının altında sarı uyarı varsa önce onu düzeltin (yanlış tür kimlik en sık hata).</li>
          <li>Kaydettikten sonra vitrinin yenilenmesi <b>1 dakika</b> sürebilir.</li>
          <li>Tarayıcınızda reklam engelleyici açıksa piksel olaylarınızı göremezsiniz — engelleyicisiz bir pencerede deneyin.</li>
          <li>Meta "Test olay kodu" alanı doluysa satışlar reklam raporlarına düşmez; testten sonra boşaltın.</li>
          <li>Google Ads'te dönüşümün görünmesi 24-48 saat sürer; GA4 "Gerçek zamanlı"da görünüyorsa kurulum doğrudur.</li>
        </ul>
      </Kart>
    </div>
  )
}
