import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import SaveBar from '../components/SaveBar'
import { passkeySupported, registerPasskey } from '../lib/webauthn'

// Mağaza Ayarları — kargo, min. sepet, ödeme, iletişim, yasal metinler.
// Tek kaynak Store.config; maskeli ('••') secretlar değiştirilmezse yazılmaz.
// Shopify tarzı SEKMELER: her konu kendi panelinde, Kaydet tüm sekmeleri kapsar.
const TABS = [
  { key: 'genel', label: 'Genel', icon: '🏬' },
  { key: 'kargo', label: 'Kargo & Sepet', icon: '📦' },
  { key: 'odeme', label: 'Ödeme', icon: '💳' },
  { key: 'eposta', label: 'E-posta', icon: '🔔' },
  { key: 'pazarlama', label: 'Pazarlama', icon: '🎯' },
  { key: 'destek', label: 'Destek', icon: '🎧' },
  { key: 'guvenlik', label: 'Güvenlik', icon: '🔐' },
  { key: 'yayin', label: 'Yayın & Domain', icon: '🌐' },
  { key: 'yasal', label: 'Yasal', icon: '📄' },
]

export default function AyarlarPage() {
  const { storeId } = useStore()
  const [tab, setTab] = useState('genel')
  const [storeName, setStoreName] = useState('')
  const [cfg, setCfg] = useState({})
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const initialRef = useRef('')   // dirty takibi için ilk state imzası
  const snapshot = (name, config) => JSON.stringify([name, config])

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const r = await api.get(`/api/store-settings/${storeId}`)
      setStoreName(r.store_name || '')
      setCfg(r.config || {})
      initialRef.current = snapshot(r.store_name || '', r.config || {})
      setLoaded(true)
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Ayarlar yüklenemedi')
    }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setCfg(c => ({ ...c, [k]: v }))
  }

  const save = async () => {
    setBusy(true)
    try {
      const r = await api.patch(`/api/store-settings/${storeId}`, {
        store_name: storeName || null,
        config: cfg,
      })
      setCfg(r.config || {})
      initialRef.current = snapshot(storeName, r.config || {})
      toast.success('Ayarlar kaydedildi')
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  const discard = () => {
    const [name, config] = JSON.parse(initialRef.current || '["",{}]')
    setStoreName(name)
    setCfg(config)
  }

  // E-posta şablonu: formdaki taslak konu/girişle önizleme + test gönderimi
  const [emailPreview, setEmailPreview] = useState(null)   // {subject, html}
  const [testBusy, setTestBusy] = useState(false)
  const previewEmail = async (type, t) => {
    try {
      setEmailPreview(await api.post(`/api/store-settings/${storeId}/email-preview`,
        { type, subject: t.subject || '', intro: t.intro || '' }))
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Önizleme alınamadı')
    }
  }
  const testEmail = async (type, t) => {
    setTestBusy(true)
    try {
      const r = await api.post(`/api/store-settings/${storeId}/email-test`,
        { type, subject: t.subject || '', intro: t.intro || '' })
      toast.success(`Test maili gönderildi → ${r.to}`)
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Gönderilemedi')
    } finally { setTestBusy(false) }
  }
  const dirty = loaded && snapshot(storeName, cfg) !== initialRef.current

  if (!loaded) return <p className="text-sm text-panel-muted">Yükleniyor…</p>

  return (
    <div className="max-w-2xl space-y-4 pb-10">
      <SaveBar dirty={dirty} busy={busy} onSave={save} onDiscard={discard} />
      <h1 className="text-xl font-semibold">Ayarlar</h1>

      {/* Sekmeler — Kaydet çubuğu tüm sekmelerdeki değişiklikleri kapsar */}
      <div className="flex gap-1 border-b border-panel-border -mb-1 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3.5 py-2 text-[13px] whitespace-nowrap rounded-t-xl border-b-2 transition-all duration-150 ${
              tab === t.key
                ? 'border-panel-accent text-emerald-700 font-semibold bg-emerald-50'
                : 'border-transparent text-panel-muted hover:text-panel-ink hover:bg-panel-input'}`}>
            <span className="mr-1.5">{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      {tab === 'genel' && (
      <Section title="Mağaza Bilgileri" icon="🏬">
        <Field label="Mağaza adı">
          <input className="input mt-1" value={storeName} onChange={e => setStoreName(e.target.value)} maxLength={200} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="İletişim e-postası">
            <input className="input mt-1" type="email" value={cfg.contact_email || ''} onChange={set('contact_email')} />
          </Field>
          <Field label="Telefon">
            <input className="input mt-1" value={cfg.contact_phone || ''} onChange={set('contact_phone')} />
          </Field>
        </div>
        <Field label="Instagram (kullanıcı adı)">
          <input className="input mt-1" value={cfg.contact_instagram || ''} onChange={set('contact_instagram')} placeholder="@markam" />
        </Field>
      </Section>
      )}

      {tab === 'kargo' && (
      <Section title="Kargo ve Sepet" icon="📦">
        <div className="grid grid-cols-3 gap-3">
          <Field label="Kargo ücreti (₺)">
            <input className="input mt-1" type="number" step="0.01" min="0"
              value={cfg.shipping_fee || ''} onChange={set('shipping_fee')} placeholder="0 = ücretsiz" />
          </Field>
          <Field label="Ücretsiz kargo eşiği (₺)">
            <input className="input mt-1" type="number" step="0.01" min="0"
              value={cfg.free_shipping_over || ''} onChange={set('free_shipping_over')} placeholder="örn 500" />
          </Field>
          <Field label="Min. sipariş tutarı (₺)">
            <input className="input mt-1" type="number" step="0.01" min="0"
              value={cfg.min_order_amount || ''} onChange={set('min_order_amount')} placeholder="boş = yok" />
          </Field>
        </div>
        <Field label="KDV oranı (%)">
          <input className="input mt-1 !w-32" type="number" min="0" max="100" step="1"
            value={cfg.tax_rate ?? ''} onChange={set('tax_rate')} placeholder="20" />
          <p className="text-[11px] text-panel-muted mt-1">
            Vitrin fiyatları <b>KDV dahil</b> gösterilir; siparişte fatura için
            tutarın içindeki KDV ayrıştırılıp kaydedilir. Boş = %20.
          </p>
        </Field>
        <Field label="Kargo sözü (gün)">
          <input className="input mt-1 !w-32" type="number" min="1"
            value={cfg.sla_days || ''} onChange={set('sla_days')} placeholder="3" />
        </Field>

        <div className="pt-3 mt-2 border-t border-panel-border">
          <h3 className="text-sm font-semibold">💰 Kâr hesabı (yalnız rapor)</h3>
          <p className="text-[11px] text-panel-muted mt-0.5 mb-2">
            Bu değerler müşteriye hiçbir yerde görünmez; Analitik → Kâr Marjı
            raporunda net kârı hesaplamak için kullanılır.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Varsayılan birim maliyet (₺)">
              <input className="input mt-1" type="number" step="0.01" min="0"
                value={cfg.profit_default_unit_cost || ''}
                onChange={set('profit_default_unit_cost')} placeholder="ürün maliyeti boşsa" />
            </Field>
            <Field label="Ödeme komisyonu (%)">
              <input className="input mt-1" type="number" step="0.01" min="0" max="100"
                value={cfg.profit_commission_pct || ''}
                onChange={set('profit_commission_pct')} placeholder="örn 2.99" />
            </Field>
            <Field label="Sipariş başına kargo gideri (₺)">
              <input className="input mt-1" type="number" step="0.01" min="0"
                value={cfg.profit_shipping_cost || ''}
                onChange={set('profit_shipping_cost')} placeholder="örn 45" />
            </Field>
            <Field label="Sipariş başına paketleme (₺)">
              <input className="input mt-1" type="number" step="0.01" min="0"
                value={cfg.profit_packaging_cost || ''}
                onChange={set('profit_packaging_cost')} placeholder="örn 5" />
            </Field>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm mt-1">
          <input type="checkbox" checked={!!cfg.abandoned_reminder_enabled}
            onChange={set('abandoned_reminder_enabled')} />
          Terk edilmiş sepetlere otomatik hatırlatma e-postası gönder (sepet başına 1 kez)
        </label>
        <label className="flex items-center gap-2 text-sm mt-1">
          <input type="checkbox" checked={cfg.shipping_email_enabled !== false}
            onChange={set('shipping_email_enabled')} />
          Kargoya verilince müşteriye otomatik bildirim e-postası gönder (takip no ile, 1 kez)
        </label>
        <label className="flex items-center gap-2 text-sm mt-1">
          <input type="checkbox" checked={!!cfg.gift_wrap_enabled}
            onChange={set('gift_wrap_enabled')} />
          🎁 Ödeme sayfasında "hediye paketi istiyorum" seçeneği sun (ücretsiz, sipariş notuna düşer)
        </label>
      </Section>
      )}

      {tab === 'odeme' && (
      <Section title="Ödeme Sağlayıcı" icon="💳">
        <Field label="Sağlayıcı">
          <select className="input mt-1 !w-48" value={cfg.payment_provider || 'iyzico'} onChange={set('payment_provider')}>
            <option value="iyzico">iyzico</option>
            <option value="paytr">PayTR</option>
          </select>
        </Field>
        {(cfg.payment_provider || 'iyzico') === 'iyzico' ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="iyzico API Key">
                <input className="input mt-1 font-mono text-xs" value={cfg.iyzico_api_key || ''} onChange={set('iyzico_api_key')} />
              </Field>
              <Field label="iyzico Secret Key">
                <input className="input mt-1 font-mono text-xs" value={cfg.iyzico_secret_key || ''} onChange={set('iyzico_secret_key')} />
              </Field>
            </div>
            <Field label="iyzico ortamı">
              <select className="input mt-1 !w-64" value={cfg.iyzico_base_url || 'https://sandbox-api.iyzipay.com'}
                onChange={set('iyzico_base_url')}>
                <option value="https://sandbox-api.iyzipay.com">Sandbox (test)</option>
                <option value="https://api.iyzipay.com">Canlı</option>
              </select>
            </Field>
          </>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Merchant ID">
                <input className="input mt-1 font-mono text-xs" value={cfg.paytr_merchant_id || ''} onChange={set('paytr_merchant_id')} />
              </Field>
              <Field label="Merchant Key">
                <input className="input mt-1 font-mono text-xs" value={cfg.paytr_merchant_key || ''} onChange={set('paytr_merchant_key')} />
              </Field>
              <Field label="Merchant Salt">
                <input className="input mt-1 font-mono text-xs" value={cfg.paytr_merchant_salt || ''} onChange={set('paytr_merchant_salt')} />
              </Field>
            </div>
            <Field label="PayTR modu">
              <select className="input mt-1 !w-48" value={cfg.paytr_test_mode ?? '1'} onChange={set('paytr_test_mode')}>
                <option value="1">Test</option>
                <option value="0">Canlı</option>
              </select>
            </Field>
          </>
        )}
        <p className="text-xs text-panel-muted">
          🔒 Anahtarlar maskeli görünür; değiştirmediğiniz sürece üzerine yazılmaz.
          Kart bilgileri hiçbir zaman sunucularımıza gelmez.
        </p>
      </Section>
      )}

      {tab === 'eposta' && (
      <Section title="E-posta Bildirimleri" icon="🔔">
        <p className="text-[11px] text-panel-muted -mt-1">
          Müşteriye giden otomatik e-postaların konu ve giriş metnini özelleştirin.
          Boş bırakılan alanda hazır metin kullanılır.
        </p>
        {[
          ['siparis_onay', 'Sipariş onayı', 'Siparişiniz alındı — #1234'],
          ['kargo', 'Kargo bildirimi', 'Siparişiniz kargoya verildi 📦'],
          ['terk_sepet', 'Terk sepet hatırlatması', 'Sepetinizdeki ürünler sizi bekliyor 🛒'],
          ['odeme_linki', 'Ödeme linki (taslak sipariş)', 'Siparişiniz için ödeme bağlantınız 🧾'],
          ['stok', 'Stok bildirimi', '{Ürün} yeniden stokta 🔔'],
          ['hosgeldin', 'Hoş geldin (bülten kaydı)', 'Aramıza hoş geldiniz — %10 indirim 🎁'],
          ['yorum_daveti', 'Yorum daveti (teslimden 7 gün sonra)', 'Siparişinizi değerlendirir misiniz? ⭐'],
        ].map(([key, label, ph]) => {
          const t = (cfg.email_texts || {})[key] || {}
          const setT = (field) => (e) => setCfg(c => ({
            ...c,
            email_texts: { ...(c.email_texts || {}), [key]: { ...t, [field]: e.target.value } },
          }))
          return (
            <details key={key} className="border border-panel-border rounded-xl px-3 py-2">
              <summary className="text-sm font-medium cursor-pointer flex items-center gap-2">
                {label}
                {(t.subject || t.intro) && (
                  <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded-full">özel</span>
                )}
              </summary>
              <div className="mt-2 space-y-2">
                <input className="input" value={t.subject || ''} maxLength={200}
                  onChange={setT('subject')} placeholder={`Konu (varsayılan: ${ph})`} />
                <textarea className="input" rows={2} maxLength={1000} value={t.intro || ''}
                  onChange={setT('intro')}
                  placeholder="Giriş paragrafı — 'Merhaba {ad}' satırından hemen sonra eklenir (ops.)" />
                <div className="flex gap-2">
                  <button type="button" className="btn-ghost !py-1 text-xs"
                    onClick={() => previewEmail(key, t)}>👁 Önizle</button>
                  <button type="button" className="btn-ghost !py-1 text-xs" disabled={testBusy}
                    onClick={() => testEmail(key, t)}>
                    {testBusy ? 'Gönderiliyor…' : '✉️ Test maili gönder'}
                  </button>
                </div>
              </div>
            </details>
          )
        })}
      </Section>
      )}

      {/* E-posta önizleme modalı — formdaki taslak değerlerle render edilir */}
      {emailPreview && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
          onClick={() => setEmailPreview(null)}>
          <div className="bg-panel-card border border-panel-border rounded-2xl w-full max-w-2xl overflow-hidden"
            onClick={e => e.stopPropagation()}>
            <div className="px-4 py-2.5 flex items-center gap-2 border-b border-panel-border">
              <span className="text-sm font-medium truncate">📧 {emailPreview.subject}</span>
              <button onClick={() => setEmailPreview(null)}
                className="ml-auto text-panel-muted hover:text-panel-ink">×</button>
            </div>
            <iframe title="E-posta önizleme" srcDoc={emailPreview.html}
              className="w-full bg-white" style={{ height: 'min(70vh, 640px)' }} />
          </div>
        </div>
      )}

      {tab === 'pazarlama' && (
      <Section title="Pazarlama Pikselleri" icon="🎯">
        <p className="text-[11px] text-panel-muted -mt-1">
          ID'yi girip kaydedin — vitrin otomatik olarak sayfa görüntüleme, sepete ekleme,
          ödeme başlatma ve satın alma olaylarını göndermeye başlar.
        </p>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Meta Pixel ID">
            <input className="input mt-1 font-mono text-xs" value={cfg.meta_pixel_id || ''}
              onChange={set('meta_pixel_id')} placeholder="123456789012345" />
          </Field>
          <Field label="GA4 Ölçüm ID">
            <input className="input mt-1 font-mono text-xs" value={cfg.ga4_id || ''}
              onChange={set('ga4_id')} placeholder="G-XXXXXXXXXX" />
          </Field>
          <Field label="TikTok Pixel ID">
            <input className="input mt-1 font-mono text-xs" value={cfg.tiktok_pixel_id || ''}
              onChange={set('tiktok_pixel_id')} placeholder="XXXXXXXXXXXXXXXXXX" />
          </Field>
        </div>
        <div className="border-t border-panel-border pt-3 mt-1 space-y-2">
          <div className="text-sm font-medium">🛡 Meta Conversions API (sunucu taraflı)</div>
          <p className="text-[11px] text-panel-muted -mt-1">
            Reklam engelleyici / iOS kısıtları tarayıcı pikselini susturur — satın alma
            olayı sunucudan da gönderilir, Meta ikisini tekilleştirir (çift sayım olmaz).
            Jeton: Olay Yöneticisi → pikseliniz → Ayarlar → Conversions API →
            "Erişim anahtarı oluştur".
          </p>
          <Field label="CAPI erişim jetonu">
            <input className="input mt-1 font-mono text-xs" value={cfg.meta_capi_token || ''}
              onChange={set('meta_capi_token')} placeholder="EAAG..." />
          </Field>
          <Field label="Test olay kodu (ops. — yalnız test ederken doldurun)">
            <input className="input mt-1 font-mono text-xs !w-52" value={cfg.meta_test_event_code || ''}
              onChange={set('meta_test_event_code')} placeholder="TEST12345" />
          </Field>
          <p className="text-[11px] text-panel-muted">
            ⚠️ Test kodu doluyken olaylar yalnız "Olayları Test Et" ekranına düşer —
            doğrulama bitince bu alanı boşaltıp kaydedin.
          </p>
        </div>
      </Section>
      )}

      {tab === 'destek' && (
      <Section title="BERNZ Support — 7/24 Asistan" icon="🎧">
        <p className="text-[11px] text-panel-muted -mt-1">
          Vitrinin sağ altındaki sohbet balonu. Yapay zekâ DEĞİLDİR — sistem
          verisiyle çalışır: sipariş durumunu e-postayla bulur, model uygunluğunu
          katalogdan kontrol eder, kargo/iade sorularını yanıtlar. Aşağıya
          ekleyeceğiniz sorular asistanın bilgi tabanına eklenir.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={cfg.support_chat_enabled !== false}
            onChange={e => setCfg(c => ({ ...c, support_chat_enabled: e.target.checked }))} />
          Vitrinde destek balonunu göster
        </label>
        <div className="space-y-2">
          {(cfg.support_faq || []).map((f, i) => (
            <div key={i} className="border border-panel-border rounded-xl p-2.5 space-y-1.5">
              <div className="flex items-center gap-2">
                <input className="input flex-1" maxLength={200} value={f.q}
                  placeholder="Soru — örn. Kılıflar hangi malzemeden?"
                  onChange={e => setCfg(c => ({ ...c,
                    support_faq: c.support_faq.map((x, j) => j === i ? { ...x, q: e.target.value } : x) }))} />
                <button onClick={() => setCfg(c => ({ ...c,
                  support_faq: c.support_faq.filter((_, j) => j !== i) }))}
                  className="text-red-600 hover:text-red-600 text-sm">×</button>
              </div>
              <textarea className="input" rows={2} maxLength={2000} value={f.a}
                placeholder="Asistanın vereceği yanıt"
                onChange={e => setCfg(c => ({ ...c,
                  support_faq: c.support_faq.map((x, j) => j === i ? { ...x, a: e.target.value } : x) }))} />
            </div>
          ))}
          {(cfg.support_faq || []).length < 12 && (
            <button onClick={() => setCfg(c => ({ ...c,
              support_faq: [...(c.support_faq || []), { q: '', a: '' }] }))}
              className="btn-ghost !py-1.5 text-xs w-full">+ Soru Ekle</button>
          )}
        </div>
        <p className="text-[11px] text-panel-muted">
          💡 Önerilen sorular: kılıf malzemesi/baskı kalitesi, kişiye özel tasarım
          süreci, kapıda ödeme olup olmadığı, üretim süresi. Müşterileriniz sıkça
          ne soruyorsa buraya ekleyin — asistan yazılan mesajı anahtar
          kelimelerle bu listeden eşleştirir.
        </p>
      </Section>
      )}

      {tab === 'eposta' && (
      <Section title="Otomatik E-posta Akışları" icon="⚡">
        <p className="text-[11px] text-panel-muted -mt-1">
          Shopify'da ayrı uygulama gerektiren akışlar — burada yerleşik.
        </p>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5"
            checked={cfg.welcome_email_enabled !== false}
            onChange={e => setCfg(c => ({ ...c, welcome_email_enabled: e.target.checked }))} />
          <span>
            🎁 Hoş geldin e-postası
            <span className="block text-xs text-panel-muted">
              Bültene abone olana anında kişiye özel, tek kullanımlık indirim kodu gider.
            </span>
          </span>
        </label>
        <Field label="Hoş geldin indirimi (%)">
          <input className="input mt-1 !w-28" type="number" min="1" max="50"
            value={cfg.welcome_discount_percent ?? ''} onChange={set('welcome_discount_percent')}
            placeholder="10" />
        </Field>
        <label className="flex items-start gap-2 text-sm border-t border-panel-border pt-3">
          <input type="checkbox" className="mt-0.5"
            checked={cfg.review_invite_enabled !== false}
            onChange={e => setCfg(c => ({ ...c, review_invite_enabled: e.target.checked }))} />
          <span>
            ⭐ Yorum daveti
            <span className="block text-xs text-panel-muted">
              Sipariş teslim edildikten 7 gün sonra değerlendirme daveti gönderilir
              (sipariş başına tek sefer).
            </span>
          </span>
        </label>
      </Section>
      )}

      {tab === 'guvenlik' && <PasskeySection toast={toast} />}

      {tab === 'yayin' && (<>
      <Section title="Yayın Öncesi Kilit" icon="🔒">
        <Field label="Mağaza şifresi (boş = koruma kapalı)">
          <input className="input mt-1 !w-64" value={cfg.storefront_password || ''}
            onChange={set('storefront_password')} maxLength={100}
            placeholder="örn. onizleme2026" />
        </Field>
        <p className="text-[11px] text-panel-muted -mt-1">
          Doluyken vitrin ziyaretçilere kilit ekranı gösterir (Shopify password page).
          Yayına çıkarken bu alanı boşaltın.
        </p>
      </Section>

      <Section title="Domain Bağlama" icon="🌐">
        <Field label="Vitrin adresi (aktif)">
          <input className="input mt-1" value={cfg.storefront_url || ''} onChange={set('storefront_url')}
            placeholder="https://magaza.bernzcompany.com" />
        </Field>
        <p className="text-[11px] text-panel-muted -mt-1">
          Ödeme dönüş linkleri ve e-postalardaki adresler buradan üretilir.
        </p>
        <Field label="Kendi alan adınız (opsiyonel)">
          <input className="input mt-1" value={cfg.custom_domain || ''} onChange={set('custom_domain')}
            placeholder="markam.com" />
        </Field>
        <DomainVerify storeId={storeId} customDomain={cfg.custom_domain}
          onUseAsDomain={() => setCfg(c => ({ ...c, storefront_url: `https://${(c.custom_domain || '').trim()}` }))} />
      </Section>
      </>)}

      {tab === 'yasal' && (
      <Section title="Yasal Metinler" icon="📄">
        <p className="text-xs text-panel-muted -mt-1 mb-2">
          Boş bırakılan alanlarda vitrindeki hazır şablon metinler gösterilir.
        </p>
        <Field label="KVKK Aydınlatma Metni (özel)">
          <textarea className="input mt-1" rows={4} value={cfg.kvkk_text || ''} onChange={set('kvkk_text')} />
        </Field>
        <Field label="Mesafeli Satış Sözleşmesi (özel)">
          <textarea className="input mt-1" rows={4} value={cfg.mesafeli_satis_text || ''} onChange={set('mesafeli_satis_text')} />
        </Field>
        <Field label="İade ve Değişim (özel)">
          <textarea className="input mt-1" rows={4} value={cfg.iade_text || ''} onChange={set('iade_text')} />
        </Field>
      </Section>
      )}
    </div>
  )
}

function Section({ title, icon, children }) {
  return (
    <section className="card space-y-3">
      <h2 className="text-sm font-semibold flex items-center gap-2">
        <span>{icon}</span> {title}
      </h2>
      {children}
    </section>
  )
}

function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="text-panel-muted text-xs">{label}</span>
      {children}
    </label>
  )
}

// Özel domain DNS doğrulaması — kaydedilmiş custom_domain üzerinden çalışır.
// Geçiş anahtarları (passkey) — parmak izi / Face ID / güvenlik anahtarı ile
// şifresiz giriş. Anahtarlar Baskıcı paneliyle ORTAKTIR (aynı hesap).
function PasskeySection({ toast }) {
  const [keys, setKeys] = useState(null)
  const [only, setOnly] = useState(null)   // {enabled, passkey_count}
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [k, o] = await Promise.all([
        api.get('/api/auth/passkey'),
        api.get('/api/auth/passkey/only'),
      ])
      setKeys(k); setOnly(o)
    } catch { setKeys([]) }
  }, [])
  useEffect(() => { load() }, [load])

  const add = async () => {
    setBusy(true)
    try {
      const name = window.prompt('Bu cihaza bir ad verin', 'MacBook / iPhone')
      if (name === null) return
      await registerPasskey(name.trim() || 'Passkey')
      toast.success('Geçiş anahtarı eklendi ✓')
      load()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail
        : e?.name === 'NotAllowedError' ? 'İşlem iptal edildi' : 'Eklenemedi')
    } finally { setBusy(false) }
  }

  const remove = async (k) => {
    if (!window.confirm(`"${k.name}" silinecek. Emin misiniz?`)) return
    try { await api.del(`/api/auth/passkey/${k.id}`); toast.success('Silindi'); load() }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Silinemedi') }
  }

  const toggleOnly = async (enabled) => {
    try {
      const r = await api.post('/api/auth/passkey/only', { enabled })
      setOnly(o => ({ ...o, enabled: r.enabled }))
      toast.success(enabled ? 'Artık yalnızca geçiş anahtarıyla giriliyor'
        : 'Şifreyle giriş yeniden açıldı')
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Değiştirilemedi')
    }
  }

  return (
    <Section title="Geçiş Anahtarları (Passkey)" icon="🔑">
      <p className="text-[11px] text-panel-muted -mt-1">
        Parmak izi, Face ID veya güvenlik anahtarıyla şifresiz giriş yapın.
        Şifre çalınamaz ve sahte siteye kaptırılamaz. Eklediğiniz anahtarlar
        Baskıcı panelinde de geçerlidir.
      </p>
      {!passkeySupported() && (
        <p className="text-xs text-amber-700">
          Bu tarayıcı geçiş anahtarını desteklemiyor (güncel Chrome/Safari/Edge gerekir).
        </p>
      )}
      {keys === null ? (
        <p className="text-sm text-panel-muted">Yükleniyor…</p>
      ) : keys.length === 0 ? (
        <p className="text-sm text-panel-muted">Henüz geçiş anahtarı yok.</p>
      ) : (
        <div className="space-y-1.5">
          {keys.map(k => (
            <div key={k.id} className="flex items-center gap-2 border border-panel-border rounded-xl px-3 py-2 text-sm">
              <span>🔑</span>
              <span className="font-medium">{k.name}</span>
              <span className="text-xs text-panel-muted">
                {k.last_used_at
                  ? `son kullanım ${new Date(k.last_used_at).toLocaleDateString('tr-TR')}`
                  : 'hiç kullanılmadı'}
              </span>
              <button onClick={() => remove(k)}
                className="ml-auto text-xs text-red-600 hover:text-red-600">Sil</button>
            </div>
          ))}
        </div>
      )}
      <button onClick={add} disabled={busy || !passkeySupported()}
        className="btn-ghost !py-1.5 text-xs">
        {busy ? 'Bekleniyor…' : '+ Bu cihazı ekle'}
      </button>

      {only && (
        <label className="flex items-start gap-2 text-sm border-t border-panel-border pt-3 mt-1">
          <input type="checkbox" className="mt-0.5" checked={!!only.enabled}
            disabled={!only.enabled && (only.passkey_count || 0) < 1}
            onChange={e => toggleOnly(e.target.checked)} />
          <span>
            Yalnızca geçiş anahtarıyla giriş
            <span className="block text-xs text-panel-muted">
              Açıkken e-posta + şifre girişi reddedilir (en güvenli mod).
              {(only.passkey_count || 0) < 1 && ' Önce en az bir anahtar ekleyin.'}
            </span>
          </span>
        </label>
      )}
    </Section>
  )
}

function DomainVerify({ storeId, customDomain, onUseAsDomain }) {
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const verify = async () => {
    setBusy(true); setResult(null)
    try {
      setResult(await api.post(`/api/store-settings/${storeId}/verify-domain`,
        { domain: (customDomain || '').trim() }))
    }
    catch (e) {
      setResult({ verified: false, message: typeof e?.detail === 'string' ? e.detail : 'Doğrulama başarısız' })
    } finally { setBusy(false) }
  }

  if (!customDomain?.trim()) {
    return (
      <p className="text-[11px] text-panel-muted">
        Alan adınızı yazın, <b>Kaydet</b>'e basın; ardından DNS yönlendirmesini yapıp doğrulayın.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <div className="bg-panel-input rounded-xl p-3 text-xs space-y-1">
        <div className="font-medium">DNS ayarları (alan adı sağlayıcınızın panelinden):</div>
        <div className="font-mono">A kaydı &nbsp; @ → sunucu IP&apos;niz</div>
        <div className="font-mono">CNAME &nbsp;&nbsp; www → {customDomain.trim()}</div>
        <div className="text-panel-muted">Değişikliklerin yayılması birkaç saat sürebilir.</div>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={verify} disabled={busy} className="btn-ghost !py-1.5 text-xs">
          {busy ? 'Kontrol ediliyor…' : '🔍 DNS Doğrula'}
        </button>
        {result && (
          <span className={`text-xs ${result.verified ? 'text-emerald-700' : 'text-amber-700'}`}>
            {result.message}
          </span>
        )}
      </div>
      {result?.verified && (
        <button onClick={onUseAsDomain} className="text-xs text-panel-accent underline">
          Vitrin adresini https://{customDomain.trim()} olarak ayarla (sonra Kaydet&apos;e basın)
        </button>
      )}
    </div>
  )
}
