import { useCallback, useEffect, useRef, useState } from 'react'
import { api, getToken } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import SaveBar from '../components/SaveBar'
import { passkeySupported, registerPasskey } from '../lib/webauthn'
import { mutlak } from '../lib/taban'

// Mağaza Ayarları — kargo, min. sepet, ödeme, iletişim, yasal metinler.
// Tek kaynak Store.config; maskeli ('••') secretlar değiştirilmezse yazılmaz.
// Shopify tarzı SEKMELER: her konu kendi panelinde, Kaydet tüm sekmeleri kapsar.
const TABS = [
  { key: 'genel', label: 'Genel', icon: '🏬' },
  { key: 'kargo', label: 'Kargo & Sepet', icon: '📦' },
  { key: 'odeme', label: 'Ödeme', icon: '💳' },
  { key: 'baski', label: 'Baskı', icon: '🖨️' },
  { key: 'eposta', label: 'E-posta', icon: '🔔' },
  { key: 'pazarlama', label: 'Pazarlama', icon: '🎯' },
  { key: 'destek', label: 'Destek', icon: '🎧' },
  { key: 'guvenlik', label: 'Güvenlik', icon: '🔐' },
  { key: 'mobil', label: 'Mobil Uygulama', icon: '📱' },
  { key: 'entegrasyon', label: 'Entegrasyon', icon: '🔌' },
  { key: 'yayin', label: 'Yayın & Domain', icon: '🌐' },
  { key: 'yasal', label: 'Yasal', icon: '📄' },
]

export default function AyarlarPage() {
  const { storeId } = useStore()
  const [tab, setTab] = useState('genel')
  const [storeName, setStoreName] = useState('')
  const [cfg, setCfg] = useState({})
  const [odemeSonuc, setOdemeSonuc] = useState(null)
  const [odemeBusy, setOdemeBusy] = useState(false)
  const [iccBusy, setIccBusy] = useState(false)
  const [iccHata, setIccHata] = useState('')
  const iccRef = useRef(null)
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

  // CMYK ICC profili — baskı PDF'inde renk dönüşümü bununla yapılır
  const iccYukle = async (file) => {
    if (!file) return
    setIccBusy(true); setIccHata('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(mutlak(`/api/store-settings/${storeId}/cmyk-profili`), {
        method: 'POST', body: fd, headers: { Authorization: `Bearer ${getToken()}` },
      })
      const r = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(r.detail || 'Yüklenemedi')
      setCfg(c => ({ ...c, cmyk_icc_ad: r.ad, cmyk_icc_path: 'var' }))
      toast.success('CMYK profili yüklendi')
    } catch (e) {
      setIccHata(e.message || 'Yüklenemedi')
    } finally { setIccBusy(false); if (iccRef.current) iccRef.current.value = '' }
  }
  const iccSil = async () => {
    try {
      await api.del(`/api/store-settings/${storeId}/cmyk-profili`)
      setCfg(c => ({ ...c, cmyk_icc_ad: '', cmyk_icc_path: '' }))
    } catch { setIccHata('Silinemedi') }
  }

  // Ödeme sağlayıcı bağlantı testi — "ödeme başlatılamadı" hatasının sebebini
  // sağlayıcının kendi mesajıyla gösterir (sipariş oluşmaz, tahsilat yapılmaz).
  const odemeTesti = async () => {
    setOdemeBusy(true); setOdemeSonuc(null)
    try {
      setOdemeSonuc(await api.post(`/api/store-settings/${storeId}/odeme-testi`, {}))
    } catch (e) {
      setOdemeSonuc({
        ok: false, saglayici: cfg.payment_provider || 'iyzico', ortam: '—',
        mesaj: typeof e?.detail === 'string' ? e.detail : 'İstek başarısız',
      })
    } finally { setOdemeBusy(false) }
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
                ? 'border-panel-accent text-emerald-300 font-semibold bg-emerald-500/10'
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
        <KargoTanisi storeId={storeId} />

        {/* Eşik var ama ücret yoksa HER siparişte kargo bedava olur — eşik
            hiçbir işe yaramaz ve fark ancak siparişte görülür. */}
        {Number(cfg.free_shipping_over || 0) > 0 && !(Number(cfg.shipping_fee || 0) > 0) && (
          <p className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
            ⚠️ <b>Kargo ücreti boş.</b> Ücretsiz kargo eşiği
            {' '}{Number(cfg.free_shipping_over).toLocaleString('tr-TR')} ₺ olarak girilmiş,
            ama kargo ücreti girilmediği için <b>her siparişte kargo ücretsiz</b> oluyor —
            eşiğin bir etkisi yok. Eşiğin altındaki siparişlerden kargo almak için
            yukarıya kargo ücretini yazın.
          </p>
        )}

        <Field label="KDV oranı (%)">
          <input className="input mt-1 !w-32" type="number" min="0" max="100" step="1"
            value={cfg.tax_rate ?? ''} onChange={set('tax_rate')} placeholder="20" />
          <p className="text-[11px] text-panel-muted mt-1">
            Vitrin fiyatları <b>KDV dahil</b> gösterilir; siparişte fatura için
            tutarın içindeki KDV ayrıştırılıp kaydedilir. Boş = %20.
          </p>
        </Field>
        <Field label="Tasarım stüdyosu ürünü (URL/slug)">
          <input className="input mt-1" value={cfg.studio_product_slug || ''}
            onChange={set('studio_product_slug')} placeholder="kendi-tasarimin" />
          <p className="text-[11px] text-panel-muted mt-1">
            Müşteri stüdyoda tasarımını bitirip sepete eklediğinde bu ürün eklenir —
            <b> fiyat ve telefon modelleri</b> bu üründen gelir. Boşsa stüdyoda
            "Sepete Ekle" çalışmaz.
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

        {/* Bağlantı testi — "ödeme başlatılamadı" hatasının sebebini gösterir */}
        <div className="border-t border-panel-border pt-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={odemeTesti} disabled={odemeBusy}
              className="btn-ghost !py-1.5 text-xs disabled:opacity-40">
              {odemeBusy ? 'Test ediliyor…' : '🔌 Bağlantıyı test et'}
            </button>
            <span className="text-[11px] text-panel-muted">
              Sağlayıcıya gerçek bir ödeme başlatma isteği atar. Sipariş oluşmaz,
              tahsilat yapılmaz. Önce ayarları kaydedin.
            </span>
          </div>
          {odemeSonuc && (
            <div className={`text-xs rounded-xl px-3 py-2 border ${odemeSonuc.ok
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-red-500/10 border-red-500/30 text-red-300'}`}>
              <div className="font-medium">
                {odemeSonuc.ok ? '✅ Bağlantı çalışıyor' : '❌ Bağlantı kurulamadı'}
                <span className="font-normal opacity-70">
                  {' '}· {odemeSonuc.saglayici} · {odemeSonuc.ortam}
                </span>
              </div>
              <div className="mt-1 break-words">{odemeSonuc.mesaj}</div>
              {odemeSonuc.ipucu && (
                <div className="mt-1.5 opacity-80">💡 {odemeSonuc.ipucu}</div>
              )}
            </div>
          )}
        </div>
      </Section>
      )}

      {tab === 'baski' && (
      <Section title="Baskı Dosyaları" icon="🖨️">
        <p className="text-xs text-panel-muted -mt-1">
          Tasarım stüdyosundan gelen her sipariş için <b>iki dosya</b> üretilir:
          ekrandakiyle birebir <b>PNG</b> (300 DPI, RGB) ve matbaa/RIP için
          <b> PDF</b> — yazılar vektörel, sayfa gerçek mm ölçüsünde.
          İkisi de sipariş detayındaki tasarım kartından indirilir.
        </p>
        <div className={`text-xs rounded-xl px-3 py-2 border ${cfg.cmyk_icc_ad
          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          : 'bg-amber-500/10 border-amber-500/30 text-amber-300'}`}>
          {cfg.cmyk_icc_ad ? (
            <>✅ <b>PDF gerçek CMYK</b> üretiliyor — renkler yüklediğiniz
            profile ({cfg.cmyk_icc_ad}) göre dönüştürülüyor.</>
          ) : (
            <>ℹ️ <b>PDF şu an sRGB</b> (profil gömülü) olarak üretiliyor ve
            renkler ekrandakiyle aynı çıkıyor; dönüşümü matbaanın RIP'i kendi
            profiliyle yapar. Profil yüklerseniz dönüşümü biz yaparız ve
            renk makinenize göre kalibre olur.</>
          )}
        </div>

        <div className="rounded-xl border border-panel-border p-3 space-y-2">
          <div className="text-sm font-medium">CMYK renk profili (ICC)</div>
          <p className="text-xs text-panel-muted">
            Baskı makinenizin ya da matbaanızın profilini yükleyin; görseller,
            yazılar ve şekiller PDF'e bu profille CMYK olarak çevrilir.
            Profili matbaanızdan isteyin — profil MAKİNEYE ve KÂĞIDA özeldir,
            genel bir profil doğru sonuç vermez.
          </p>
          {cfg.cmyk_icc_ad ? (
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-300">
                ✓ {cfg.cmyk_icc_ad}
              </span>
              <button onClick={() => iccRef.current?.click()} className="underline text-panel-muted">
                değiştir
              </button>
              <button onClick={iccSil} className="underline text-red-300 ml-auto">kaldır</button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button onClick={() => iccRef.current?.click()} disabled={iccBusy}
                className="btn-ghost !py-1.5 text-xs disabled:opacity-40">
                {iccBusy ? 'Yükleniyor…' : '📥 ICC profili yükle'}
              </button>
              <span className="text-xs text-amber-300">
                Profil yok — basit dönüşüm kullanılıyor
              </span>
            </div>
          )}
          {iccHata && <p className="text-xs text-red-300">{iccHata}</p>}
          <input ref={iccRef} type="file" accept=".icc,.icm" className="hidden"
            onChange={e => iccYukle(e.target.files?.[0])} />
        </div>

        <p className="text-[11px] text-panel-muted">
          🖼️ Müşteri <b>PDF ve SVG</b> de yükleyebilir. Vektörel dosyalar baskı
          PDF'ine olduğu gibi gömülür (rasterleşmez); ekranda ise sunucunun
          ürettiği önizlemesi görünür. Fotoğraflar vektöre çevrilemez — onlar
          CMYK rastere dönüştürülür.
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
                  <span className="text-[10px] text-emerald-300 bg-emerald-500/10 px-1.5 py-0.5 rounded-full">özel</span>
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
                  className="text-red-300 hover:text-red-300 text-sm">×</button>
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

      {tab === 'baski' && (
      <Section title="Baskı Dosyaları" icon="🖨️">
        <p className="text-xs text-panel-muted -mt-1">
          Tasarım stüdyosundan gelen her sipariş için <b>iki dosya</b> üretilir:
          ekrandakiyle birebir <b>PNG</b> (300 DPI, RGB) ve matbaa/RIP için
          <b> PDF</b> — yazılar vektörel, renkler CMYK, sayfa gerçek mm ölçüsünde.
          İkisi de sipariş detayındaki tasarım kartından indirilir.
        </p>

        <div className="rounded-xl border border-panel-border p-3 space-y-2">
          <div className="text-sm font-medium">CMYK renk profili (ICC)</div>
          <p className="text-xs text-panel-muted">
            Baskı makinenizin ya da matbaanızın profilini yükleyin; müşteri
            fotoğrafları PDF'e bu profille CMYK'ya çevrilir. Yüklenmezse basit
            dönüşüm kullanılır — çalışır ama renkler makinenizin gerçek
            gamutuna göre ayarlanmaz.
          </p>
          {cfg.cmyk_icc_ad ? (
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-300">
                ✓ {cfg.cmyk_icc_ad}
              </span>
              <button onClick={() => iccRef.current?.click()} className="underline text-panel-muted">
                değiştir
              </button>
              <button onClick={iccSil} className="underline text-red-300 ml-auto">kaldır</button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button onClick={() => iccRef.current?.click()} disabled={iccBusy}
                className="btn-ghost !py-1.5 text-xs disabled:opacity-40">
                {iccBusy ? 'Yükleniyor…' : '📥 ICC profili yükle'}
              </button>
              <span className="text-xs text-amber-300">
                Profil yok — basit dönüşüm kullanılıyor
              </span>
            </div>
          )}
          {iccHata && <p className="text-xs text-red-300">{iccHata}</p>}
          <input ref={iccRef} type="file" accept=".icc,.icm" className="hidden"
            onChange={e => iccYukle(e.target.files?.[0])} />
        </div>

        <p className="text-[11px] text-panel-muted">
          🖼️ Müşteri <b>PDF ve SVG</b> de yükleyebilir. Vektörel dosyalar baskı
          PDF'ine olduğu gibi gömülür (rasterleşmez); ekranda ise sunucunun
          ürettiği önizlemesi görünür. Fotoğraflar vektöre çevrilemez — onlar
          CMYK rastere dönüştürülür.
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

      {tab === 'mobil' && <MobilSection toast={toast} />}

      {tab === 'entegrasyon' && <EntegrasyonSection storeId={storeId} cfg={cfg} toast={toast} />}

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

// ─── Kargo teşhisi ───────────────────────────────────────────
// "Ayar dolu görünüyor ama siparişte kargo alınmıyor" durumunun sebebini
// tahmin etmek yerine SUNUCUYA sorar: o sepet tutarı için hangi kargoyu
// uygulayacağını ve NEDEN uyguladığını söyler.
function KargoTanisi({ storeId }) {
  const [tutar, setTutar] = useState('400')
  const [sonuc, setSonuc] = useState(null)
  const [busy, setBusy] = useState(false)

  const sor = async () => {
    setBusy(true); setSonuc(null)
    try {
      setSonuc(await api.get(
        `/api/store-settings/${storeId}/kargo-tanisi?sepet=${Number(tutar) || 0}`))
    } catch (e) {
      setSonuc({ sebep: typeof e?.detail === 'string' ? e.detail : 'Sorgulanamadı' })
    } finally { setBusy(false) }
  }

  return (
    <div className="rounded-xl bg-panel-input p-3 space-y-2">
      <div className="flex items-end gap-2">
        <label className="text-[11px] text-panel-muted">
          Kargo testi — sepet tutarı (₺)
          <input className="input !py-1.5 !text-sm !w-28 mt-0.5" type="number" min="0"
            value={tutar} onChange={e => setTutar(e.target.value)} />
        </label>
        <button onClick={sor} disabled={busy} className="btn-ghost !py-1.5 text-xs disabled:opacity-50">
          {busy ? 'Sorgulanıyor…' : '🚚 Bu sepette kargo ne olur?'}
        </button>
      </div>
      {sonuc && (
        <div className="text-xs space-y-0.5">
          <div>
            <b>Uygulanacak kargo: {sonuc.uygulanacak_kargo ?? '—'} ₺</b>
          </div>
          <div className="text-panel-muted">{sonuc.sebep}</div>
          {sonuc.ayar_kargo_ucreti !== undefined && (
            <div className="text-[11px] text-panel-muted">
              Kayıtlı ayar → ücret: <b>{sonuc.ayar_kargo_ucreti ?? 'boş'}</b>
              {' '}· ücretsiz eşiği: <b>{sonuc.ayar_ucretsiz_esik ?? 'boş'}</b>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Entegrasyon anahtarları ─────────────────────────────────
// e-Fatura entegratörü (Birfatura, Nilvera…) ya da muhasebe yazılımı,
// siparişleri bu anahtarla okur. Faturayı GİB'e ileten taraf ONLARDIR;
// biz sipariş verisini veririz, sonucu geri yazarlar.
function EntegrasyonSection({ storeId, cfg, toast }) {
  const [items, setItems] = useState([])
  const [ad, setAd] = useState('Birfatura')
  const [yeni, setYeni] = useState(null)     // yalnız bir kez gösterilir
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  // Hatayı YUTMA: sunucunun söylediğini göster. Genel bir "üretilemedi"
  // mesajı, veritabanı migration'ının çalışmamış olması gibi tek satırlık
  // sorunları saatlerce gizliyordu.
  const hataMetni = (e, varsayilan) => {
    if (typeof e?.detail === 'string' && e.detail) return e.detail
    if (e?.status === 500) return `${varsayilan} — sunucu hatası (500). Veritabanı güncellemesi (alembic upgrade head) çalıştırılmış mı?`
    if (e?.status) return `${varsayilan} (HTTP ${e.status})`
    return varsayilan
  }

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      setItems((await api.get(`/api/store-settings/${storeId}/entegrasyon-anahtarlari`)).items || [])
    } catch (e) { setErr(hataMetni(e, 'Anahtarlar yüklenemedi')) }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const uret = async () => {
    setBusy(true); setErr('')
    try {
      const r = await api.post(`/api/store-settings/${storeId}/entegrasyon-anahtarlari`,
        { label: ad.trim() || 'Entegrasyon' })
      setYeni(r.anahtar)
      await load()
    } catch (e) { setErr(hataMetni(e, 'Anahtar üretilemedi')) }
    finally { setBusy(false) }
  }

  const iptal = async (k) => {
    if (!window.confirm(`"${k.label}" anahtarı iptal edilecek. Bu anahtarı kullanan sistem bağlantısını kaybeder. Emin misiniz?`)) return
    try { await api.del(`/api/store-settings/${storeId}/entegrasyon-anahtarlari/${k.id}`); load() }
    catch (e) { setErr(hataMetni(e, 'İptal edilemedi')) }
  }

  const kopyala = (metin) => {
    navigator.clipboard?.writeText(metin)
      .then(() => toast?.success?.('Kopyalandı'))
      .catch(() => {})
  }

  // Entegratöre verilecek adres — panel API'yi kendi kökünden çağırır
  // (ters vekil aynı origin'de sunuyor), dış sistem de aynı adresi kullanır
  const taban = `${window.location.origin}/api/entegrasyon/v1`

  return (
    <>
      <Section title="e-Fatura / Muhasebe Entegrasyonu" icon="🔌">
        <p className="text-xs text-panel-muted">
          Faturayı <b>entegratör keser</b> (GİB'e iletim mali mühür gerektirir).
          Buradan üreteceğiniz anahtarla entegratör siparişlerinizi okur,
          faturayı keser ve fatura numarasını sisteme geri yazar.
        </p>

        {err && <p className="text-sm text-red-300">{err}</p>}

        <div className="flex gap-2 items-end">
          <Field label="Anahtar adı (kim kullanacak?)">
            <input className="input mt-1 !w-56" value={ad} maxLength={80}
              onChange={e => setAd(e.target.value)} placeholder="Birfatura" />
          </Field>
          <button onClick={uret} disabled={busy} className="btn-primary !py-2 text-xs disabled:opacity-50">
            {busy ? 'Üretiliyor…' : '+ Anahtar üret'}
          </button>
        </div>

        {yeni && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 space-y-1.5">
            <div className="text-xs font-semibold text-amber-300">
              ⚠️ Anahtarı şimdi kopyalayın — bir daha gösterilmeyecek
            </div>
            <div className="flex gap-2 items-center">
              <code className="flex-1 text-[11px] bg-white rounded-lg px-2 py-1.5 break-all border border-amber-500/30">
                {yeni}
              </code>
              <button onClick={() => kopyala(yeni)} className="btn-ghost !py-1 text-xs">Kopyala</button>
            </div>
            <button onClick={() => setYeni(null)} className="text-[11px] text-panel-muted underline">
              Kopyaladım, gizle
            </button>
          </div>
        )}

        <div className="space-y-1.5">
          {items.map(k => (
            <div key={k.id} className="flex items-center gap-2 px-2.5 py-2 rounded-xl border border-panel-border text-xs">
              <span className="font-medium">{k.label}</span>
              <code className="text-[11px] text-panel-muted">{k.prefix}…</code>
              {k.is_active
                ? <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300">aktif</span>
                : <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/5 text-panel-muted">iptal</span>}
              <span className="ml-auto text-[11px] text-panel-muted">
                {k.last_used_at
                  ? `son bağlantı: ${new Date(k.last_used_at).toLocaleString('tr-TR')}`
                  : 'henüz bağlanmadı'}
              </span>
              {k.is_active && (
                <button onClick={() => iptal(k)} className="text-[11px] text-red-300">İptal</button>
              )}
            </div>
          ))}
          {items.length === 0 && (
            <p className="text-xs text-panel-muted">Henüz anahtar yok.</p>
          )}
        </div>
      </Section>

      <Section title="BirFatura — Özel Entegrasyon" icon="🧾">
        <p className="text-xs text-panel-muted">
          BirFatura panelinde <b>Mağazalarım → Özel Entegrasyon</b> ile mağaza
          eklerken istenen alanlar. BirFatura bu adrese kendisi bağlanır,
          siparişleri çeker, faturayı keser ve fatura numarasını buraya geri yazar.
        </p>
        <div className="space-y-2">
          {[
            ['Mağaza Adı', 'Mağaza adınız (BirFatura panelinde görünür)', null],
            ['Web Sitenizin Adresi', cfg.storefront_url || 'Ayarlar → Yayın & Domain\'da vitrin adresini girin', cfg.storefront_url],
            ['API Şifresi', 'Yukarıda ürettiğiniz anahtar', null],
            ['Satış Kanalı Url', cfg.storefront_url || '—', cfg.storefront_url],
          ].map(([etiket, deger, kopyalanabilir]) => (
            <div key={etiket} className="text-xs">
              <div className="text-panel-muted">{etiket}</div>
              <div className="flex gap-2 items-center mt-0.5">
                <code className="flex-1 bg-panel-input rounded-lg px-2 py-1.5 break-all">{deger}</code>
                {kopyalanabilir && (
                  <button onClick={() => kopyala(kopyalanabilir)} className="btn-ghost !py-1 text-xs">
                    Kopyala
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-panel-muted">
          BirFatura fatura kesim durumu olarak <b>“Ödendi”</b> seçilmelidir —
          ödenmiş ve iptal edilmemiş tüm siparişler bu durumda listelenir.
          Kesilen fatura numarası sipariş detayında görünür ve o sipariş bir
          daha faturalandırılmaz.
        </p>
      </Section>

      <Section title="Diğer Entegratörler / Muhasebe" icon="📋">
        <Field label="API adresi">
          <div className="flex gap-2 items-center mt-1">
            <code className="flex-1 text-[11px] bg-panel-input rounded-lg px-2 py-1.5 break-all">{taban}</code>
            <button onClick={() => kopyala(taban)} className="btn-ghost !py-1 text-xs">Kopyala</button>
          </div>
        </Field>
        <div className="text-[11px] text-panel-muted space-y-1">
          <p>Kimlik: <code>Authorization: Bearer &lt;anahtar&gt;</code></p>
          <p><b>Uçlar:</b></p>
          <ul className="list-disc list-inside space-y-0.5">
            <li><code>GET /saglik</code> — bağlantı testi</li>
            <li><code>GET /siparisler?durum=faturasiz&amp;limit=50&amp;offset=0</code> — faturalanacaklar</li>
            <li><code>GET /siparisler/&#123;siparis_no&#125;</code> — tek sipariş</li>
            <li><code>POST /siparisler/&#123;siparis_no&#125;/fatura</code> — sonucu geri yaz
              <br /><code>&#123;"durum":"kesildi","no":"…","ettn":"…","pdf_url":"…"&#125;</code></li>
          </ul>
          <p className="pt-1">
            Tutarlar faturaya hazır gelir: KDV (%{cfg.tax_rate ?? 20}) ayrıştırılmış,
            indirim kalemlere dağıtılmış, kargo ayrı kalem. Ödenmemiş ve iptal
            siparişler listelenmez; fatura numarası yazılan sipariş listeden düşer.
          </p>
        </div>
      </Section>
    </>
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
        <p className="text-xs text-amber-300">
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
                className="ml-auto text-xs text-red-300 hover:text-red-300">Sil</button>
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
          <span className={`text-xs ${result.verified ? 'text-emerald-300' : 'text-amber-300'}`}>
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

// ── Mobil uygulama (PWA) ──────────────────────────────────────
// Panel ayrı bir mobil uygulama DEĞİL: telefonda "Ana ekrana ekle" ile
// kurulur, tam ekran açılır ve bildirim alabilir. Kurulum cihaz başınadır,
// bildirim aboneliği de öyle — bu yüzden durum sunucudan değil TARAYICIDAN
// okunuyor.
function MobilSection({ toast }) {
  const [durum, setDurum] = useState(null)   // getPushState sonucu
  const [busy, setBusy] = useState(false)

  const oku = async () => {
    try {
      const { getPushState } = await import('../lib/push')
      setDurum(await getPushState())
    } catch { setDurum({ supported: false }) }
  }
  useEffect(() => { oku() }, [])

  const ua = typeof navigator !== 'undefined' ? navigator.userAgent : ''
  const iosCihaz = /iphone|ipad|ipod/i.test(ua)
  // iOS'ta bildirim YALNIZCA ana ekrana eklenmiş uygulamada çalışır
  const kuruluMu = typeof window !== 'undefined'
    && (window.navigator.standalone === true
        || window.matchMedia?.('(display-mode: standalone)')?.matches)

  const sar = async (fn, basarili) => {
    setBusy(true)
    try {
      await fn()
      toast.success(basarili)
      await oku()
    } catch (e) { toast.error(e?.message || 'İşlem başarısız') }
    finally { setBusy(false) }
  }

  const dene = async () => {
    try {
      const { testPush } = await import('../lib/push')
      const r = await testPush()
      if (r.sent > 0) toast.success('Deneme bildirimi gönderildi')
      else toast.error(r.reason || 'Gönderilemedi — önce bildirimi aç')
    } catch { toast.error('Gönderilemedi') }
  }

  return (
    <>
      <Section title="Telefona Kur" icon="📱">
        <p className="text-xs text-panel-muted -mt-1">
          Bu panel telefonda <b>uygulama gibi</b> çalışır: ana ekrana eklenir,
          kendi ikonuyla tam ekran açılır, adres çubuğu görünmez. App Store /
          Play Store gerekmez.
        </p>
        <div className={`text-xs rounded-xl px-3 py-2 border ${kuruluMu
          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          : 'bg-white/5 border-panel-border text-panel-muted'}`}>
          {kuruluMu
            ? '✅ Şu anda kurulu uygulamadan açtınız.'
            : 'Şu anda tarayıcıdan açtınız — aşağıdaki adımlarla ana ekrana ekleyin.'}
        </div>
        <div className="grid sm:grid-cols-2 gap-3 text-xs">
          <div className="rounded-xl border border-panel-border bg-white/[0.03] p-3">
            <div className="font-semibold mb-1.5">📱 iPhone / iPad (Safari)</div>
            <ol className="list-decimal pl-4 space-y-1 text-panel-muted">
              <li>Bu sayfayı <b>Safari</b> ile açın (Chrome olmaz)</li>
              <li>Alttaki <b>Paylaş</b> simgesine dokunun</li>
              <li><b>Ana Ekrana Ekle</b> → <b>Ekle</b></li>
            </ol>
          </div>
          <div className="rounded-xl border border-panel-border bg-white/[0.03] p-3">
            <div className="font-semibold mb-1.5">🤖 Android (Chrome)</div>
            <ol className="list-decimal pl-4 space-y-1 text-panel-muted">
              <li>Sağ üstteki <b>⋮</b> menüsüne dokunun</li>
              <li><b>Uygulamayı yükle</b> (ya da Ana ekrana ekle)</li>
              <li>Onaylayın</li>
            </ol>
          </div>
        </div>
      </Section>

      <Section title="Bildirimler" icon="🔔">
        <p className="text-xs text-panel-muted -mt-1">
          Telefonunuza şunlar bildirilir: <b>yeni sipariş</b>, yeni ürün yorumu,
          destek mesajı, müşteri tasarım onayı ve sabah özeti. Bildirim
          <b> cihaz başına</b> açılır — her telefonda ayrıca açmanız gerekir.
        </p>
        {!durum ? (
          <p className="text-xs text-panel-muted">Yükleniyor…</p>
        ) : !durum.supported ? (
          <p className="text-xs text-amber-300">Bu tarayıcı bildirim desteklemiyor.</p>
        ) : !durum.serverEnabled ? (
          <p className="text-xs text-amber-300">
            Sunucuda bildirim anahtarı (VAPID) tanımlı değil — kurulum için
            sunucu .env dosyasına eklenmeli.
          </p>
        ) : !durum.swHazir ? (
          <p className="text-xs text-amber-300">
            Uygulamanın arka plan servisi yüklenemedi. Uygulamayı tamamen
            kapatıp yeniden açın; sürmesi hâlinde ana ekrandaki simgeyi silip
            yeniden ekleyin.
          </p>
        ) : durum.permission === 'denied' ? (
          <p className="text-xs text-amber-300">
            Bildirim izni engellenmiş. Tarayıcı/telefon ayarlarından bu siteye
            izin verip tekrar deneyin.
          </p>
        ) : iosCihaz && !kuruluMu ? (
          <p className="text-xs text-amber-300">
            iPhone'da bildirim yalnızca <b>ana ekrana eklenmiş</b> uygulamada
            çalışır. Önce yukarıdaki adımlarla kurun, sonra uygulamadan açıp
            bildirimi etkinleştirin.
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            {durum.subscribed ? (
              <>
                <span className="text-[11px] px-2 py-1 rounded-full bg-emerald-500/10 text-emerald-300
                  border border-emerald-500/30">Bu cihazda açık</span>
                <button onClick={dene} className="btn-ghost !py-1.5 text-xs">🔔 Deneme gönder</button>
                <button disabled={busy} className="btn-ghost !py-1.5 text-xs"
                  onClick={() => sar(async () => (await import('../lib/push')).disablePush(),
                                     'Bildirimler kapatıldı')}>Kapat</button>
              </>
            ) : (
              <button disabled={busy} className="btn-primary !py-1.5 text-xs"
                onClick={() => sar(async () => (await import('../lib/push')).enablePush(),
                                   'Bildirimler açıldı')}>
                {busy ? 'Açılıyor…' : '🔔 Bildirimleri Aç'}
              </button>
            )}
          </div>
        )}
      </Section>
    </>
  )
}
