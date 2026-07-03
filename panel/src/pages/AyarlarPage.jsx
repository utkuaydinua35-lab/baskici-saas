import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Mağaza Ayarları — kargo, min. sepet, ödeme, iletişim, yasal metinler.
// Tek kaynak Store.config; maskeli ('••') secretlar değiştirilmezse yazılmaz.
export default function AyarlarPage() {
  const { storeId } = useStore()
  const [storeName, setStoreName] = useState('')
  const [cfg, setCfg] = useState({})
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)  // {ok, text}

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const r = await api.get(`/api/store-settings/${storeId}`)
      setStoreName(r.store_name || '')
      setCfg(r.config || {})
      setLoaded(true)
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Ayarlar yüklenemedi' })
    }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setCfg(c => ({ ...c, [k]: v }))
  }

  const save = async () => {
    setBusy(true); setMsg(null)
    try {
      const r = await api.patch(`/api/store-settings/${storeId}`, {
        store_name: storeName || null,
        config: cfg,
      })
      setCfg(r.config || {})
      setMsg({ ok: true, text: 'Ayarlar kaydedildi ✓' })
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi' })
    } finally { setBusy(false) }
  }

  if (!loaded) return <p className="text-sm text-panel-muted">Yükleniyor…</p>

  return (
    <div className="max-w-2xl space-y-4 pb-10">
      <div className="flex items-center gap-3 sticky top-0 bg-panel-bg py-2 z-10">
        <h1 className="text-xl font-semibold">Ayarlar</h1>
        {msg && (
          <span className={`text-sm ${msg.ok ? 'text-emerald-700' : 'text-red-600'}`}>{msg.text}</span>
        )}
        <button onClick={save} disabled={busy} className="btn-primary ml-auto">
          {busy ? 'Kaydediliyor…' : 'Kaydet'}
        </button>
      </div>

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
        <Field label="Kargo sözü (gün)">
          <input className="input mt-1 !w-32" type="number" min="1"
            value={cfg.sla_days || ''} onChange={set('sla_days')} placeholder="3" />
        </Field>
        <label className="flex items-center gap-2 text-sm mt-1">
          <input type="checkbox" checked={!!cfg.abandoned_reminder_enabled}
            onChange={set('abandoned_reminder_enabled')} />
          Terk edilmiş sepetlere otomatik hatırlatma e-postası gönder (sepet başına 1 kez)
        </label>
      </Section>

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
