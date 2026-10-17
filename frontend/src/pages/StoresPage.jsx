import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

export default function StoresPage({ embedded = false }) {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [platforms, setPlatforms] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [testingId, setTestingId] = useState(null)
  const [testResult, setTestResult] = useState({})  // { storeId: {success, message} }
  const [oauthBanner, setOauthBanner] = useState(null)

  // OAuth callback'inden dönen ?oauth=success|error query'sini yakala
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const oauth = params.get('oauth')
    if (oauth === 'success') {
      const reauth = params.get('reauth')
      setOauthBanner({ ok: true, text: reauth ? 'Mağaza yeniden yetkilendirildi (yeni token alındı).' : 'Mağaza OAuth ile başarıyla bağlandı.' })
      window.history.replaceState({}, '', window.location.pathname)
    } else if (oauth === 'error') {
      const reason = params.get('reason') || 'bilinmeyen hata'
      setOauthBanner({ ok: false, text: `OAuth başarısız: ${reason}` })
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [s, p] = await Promise.all([
        api.get('/api/stores'),
        api.get('/api/stores/_meta/platforms'),
      ])
      setStores(s)
      setPlatforms(p)
    } catch (e) {
      setError(e.detail || 'Yükleme başarısız')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleTest = async (storeId) => {
    setTestingId(storeId)
    try {
      const r = await api.post(`/api/stores/${storeId}/test`, {})
      setTestResult(prev => ({ ...prev, [storeId]: r }))
    } catch (e) {
      setTestResult(prev => ({
        ...prev,
        [storeId]: { success: false, message: e.detail || 'Hata' },
      }))
    } finally {
      setTestingId(null)
    }
  }

  const handleDelete = async (store) => {
    if (!confirm(`"${store.name}" mağazasını silmek istiyor musun?\n\nBu işlem geri alınamaz.`)) return
    try {
      await api.del(`/api/stores/${store.id}`)
      loadData()
    } catch (e) {
      toast.error(`Silme başarısız: ${e.detail || e.message}`)
    }
  }

  const handleReauth = async (store) => {
    setError('')
    try {
      const r = await api.post(`/api/stores/${store.id}/reauth`, {})
      if (r?.install_url) window.location.href = r.install_url
      else setError('install_url alınamadı')
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Yeniden yetkilendirme başlatılamadı')
    }
  }

  return (
    <div className={embedded ? "" : "max-w-4xl"}>
      <div className="flex items-center justify-between mb-6">
        <div>
          {!embedded && <h1 className="text-2xl font-semibold text-gray-100">Mağazalar</h1>}
          {!embedded && <p className="text-sm text-gray-500 mt-1">
            Shopify ve İkas mağazalarını bağla
          </p>}
          {embedded && <p className="text-sm text-gray-500">Shopify ve İkas mağazalarını bağla</p>}
        </div>
        <button onClick={() => setShowAddDialog(true)} className="btn-primary">
          + Yeni Mağaza
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-4">
          {error}
        </div>
      )}
      {oauthBanner && (
        <div className={`text-sm rounded-lg px-3 py-2 mb-4 border ${
          oauthBanner.ok
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
            : 'bg-red-500/10 border-red-500/20 text-red-400'
        }`}>{oauthBanner.ok ? '✓ ' : '✗ '}{oauthBanner.text}</div>
      )}

      {loading && <div className="text-gray-500 text-sm">Yükleniyor...</div>}

      {!loading && stores.length === 0 && (
        <div className="card text-center py-12">
          <div className="text-4xl mb-3">🏪</div>
          <h3 className="text-gray-300 font-medium mb-1">Henüz mağaza yok</h3>
          <p className="text-sm text-gray-500 mb-4">
            İlk mağazanı ekleyerek başla. Shopify ya da İkas seçebilirsin.
          </p>
          <button onClick={() => setShowAddDialog(true)} className="btn-primary">
            İlk Mağazayı Ekle
          </button>
        </div>
      )}

      <div className="space-y-3">
        {stores.map(store => {
          const result = testResult[store.id]
          return (
            <div key={store.id} className="card">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-gray-100">{store.name}</span>
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-brand-input text-gray-400">
                      {store.platform}
                    </span>
                    {!store.is_active && (
                      <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-red-500/15 text-red-400">
                        pasif
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 font-mono">{store.slug}</div>

                  {/* Config preview (maskelenmiş) — kendi editörü olanlar hariç.
                      Nesne/dizi değerler ham gösterilmez ([object Object] yerine
                      özet); vitrin mağazasının bu alanları mağaza panelinden yönetilir. */}
                  <div className="mt-3 space-y-1">
                    {Object.entries(store.config || {}).filter(([k]) => k !== 'sla_days' && k !== 'kargo_handler' && !(store.platform === 'storefront' && k === 'shop_domain')).map(([k, v]) => (
                      <div key={k} className="text-xs flex gap-2">
                        <span className="text-gray-500 w-32 shrink-0">{k}:</span>
                        <span className="text-gray-300 font-mono truncate">
                          {Array.isArray(v) ? `[${v.length} kayıt]`
                            : (v !== null && typeof v === 'object') ? `{${Object.keys(v).length} alan}`
                            : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Tasarım paylaşımı — aynı işletmenin iki kanalı tek havuzu kullansın */}
                  <TasarimPaylasimi store={store} tumStores={stores} onSaved={loadData} />

                  {/* Vitrin alan adı — kurulumda yanlış yazılırsa buradan düzeltilir */}
                  {store.platform === 'storefront' && <AlanAdiEditor store={store} onSaved={loadData} />}

                  {/* Kargo SLA (söz tarihi gün sayısı) */}
                  <SlaEditor store={store} onSaved={loadData} />

                  {/* Kargo firması (Basit Kargo handlerCode) — gönderide kullanılır */}
                  {store.platform !== 'bayii' && <KargoEditor />}

                  {/* Test sonucu */}
                  {result && (
                    <div className={`mt-3 text-xs rounded-lg px-3 py-2 ${
                      result.success
                        ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300'
                        : 'bg-red-500/10 border border-red-500/20 text-red-400'
                    }`}>
                      {result.success ? '✓ ' : '✗ '}{result.message}
                    </div>
                  )}
                </div>

                <div className="flex flex-col gap-1.5 shrink-0">
                  <button
                    onClick={() => handleTest(store.id)}
                    disabled={testingId === store.id}
                    className="btn-secondary !text-xs !py-1 !px-2 disabled:opacity-50"
                  >
                    {testingId === store.id ? 'Test...' : '🔌 Bağlantı'}
                  </button>
                  {store.config?.auth_type === 'oauth' && (
                    <button
                      onClick={() => handleReauth(store)}
                      className="btn-secondary !text-xs !py-1 !px-2"
                      title="Token süresi dolduysa yeniden bağlan (kalıcı token)"
                    >
                      🔐 Yeniden Yetkilendir
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(store)}
                    className="text-xs px-2 py-1 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    Sil
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {showAddDialog && (
        <AddStoreDialog
          platforms={platforms}
          onClose={() => setShowAddDialog(false)}
          onSaved={() => { setShowAddDialog(false); loadData() }}
        />
      )}
    </div>
  )
}

/**
 * Tasarım paylaşımı — aynı atölyedeki mağazalar tek tasarım havuzunu kullansın.
 *
 * Aynı işletmenin iki kanalı olabiliyor (eski Shopify mağazası + kendi vitrini);
 * tasarımlar mağazaya bağlı olduğu için vitrin tarafında "bu mağazada o kodlu
 * tasarım yok" çıkıyordu. İşaretlenen mağazalar birbirinin tasarımlarını görür.
 *
 * Bayi mağazaları KASITLI olarak dışarıda: onların kendi kodlu katalogları ana
 * mağazaya karışmamalı. Bu yüzden paylaşım işaretlenerek açılıyor.
 */
function TasarimPaylasimi({ store, tumStores, onSaved }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const acik = !!store.tasarim_grubu
  // Bayi mağazalarında bu seçenek hiç görünmesin
  if (store.platform === 'bayii') return null

  const ortaklar = (tumStores || []).filter(
    s => s.id !== store.id && s.tasarim_grubu && s.tasarim_grubu === store.tasarim_grubu)

  const degistir = async (e) => {
    const yeni = e.target.checked
    setBusy(true)
    try {
      await api.patch(`/api/stores/${store.id}`, { tasarim_grubu: yeni ? 'ortak' : '' })
      toast.success(yeni ? 'Tasarımlar ortak havuza alındı' : 'Paylaşım kapatıldı')
      onSaved()
    } catch (e2) { toast.error(e2?.detail || 'Kaydedilemedi') }
    finally { setBusy(false) }
  }

  return (
    <div className="mt-3">
      <label className="flex items-center gap-2 cursor-pointer select-none">
        <input type="checkbox" checked={acik} disabled={busy} onChange={degistir}
               className="accent-accent" />
        <span className="text-xs text-gray-300">🎨 Tasarımlar ortak</span>
      </label>
      <p className="text-[10px] text-gray-600 mt-0.5">
        {acik
          ? (ortaklar.length
              ? `${ortaklar.map(s => s.name).join(', ')} ile aynı tasarım havuzunu kullanıyor.`
              : 'İşaretli tek mağaza bu — ortak olması için diğer mağazayı da işaretle.')
          : 'İşaretlenen mağazalar birbirinin tasarımlarını görür ve kullanır (bayiler hariç).'}
      </p>
    </div>
  )
}

function AlanAdiEditor({ store, onSaved }) {
  const toast = useToast()
  const original = store.config?.shop_domain ?? ''
  const [val, setVal] = useState(original)
  const [busy, setBusy] = useState(false)
  const dirty = val.trim() !== original

  const save = async () => {
    setBusy(true)
    try {
      const r = await api.patch(`/api/stores/${store.id}`, { config: { shop_domain: val } })
      setVal(r?.config?.shop_domain ?? val.trim())   // sunucu temizlenmiş halini döner
      toast.success('Vitrin alan adı güncellendi')
      onSaved?.()
    } catch (e) {
      toast.error(e.detail || 'Kaydedilemedi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <span className="text-xs text-gray-500">🌐 Vitrin alan adı:</span>
      <input
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && dirty) save(); if (e.key === 'Escape') setVal(original) }}
        placeholder="magaza.alanadiniz.com"
        className="input !text-xs !py-1 w-56 font-mono"
      />
      {dirty && (
        <>
          <button onClick={save} disabled={busy || !val.trim()} className="btn-primary !text-[11px] !py-1 !px-2 disabled:opacity-50">
            {busy ? '...' : 'Kaydet'}
          </button>
          <button onClick={() => setVal(original)} disabled={busy} className="btn-secondary !text-[11px] !py-1 !px-2">
            Vazgeç
          </button>
        </>
      )}
    </div>
  )
}

function SlaEditor({ store, onSaved }) {
  const toast = useToast()
  const [val, setVal] = useState(store.config?.sla_days ?? '')
  const [busy, setBusy] = useState(false)
  const original = store.config?.sla_days ?? ''
  const dirty = String(val) !== String(original)

  const save = async () => {
    setBusy(true)
    try {
      const n = val === '' ? null : parseInt(val, 10)
      await api.patch(`/api/stores/${store.id}`, { config: { sla_days: n } })
      toast.success('Kargo SLA güncellendi')
      onSaved?.()
    } catch (e) {
      toast.error(e.detail || 'Kaydedilemedi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-3 flex items-center gap-2">
      <span className="text-xs text-gray-500">🚚 Kargo SLA:</span>
      <input
        type="number" min="0" max="60"
        value={val}
        onChange={e => setVal(e.target.value)}
        placeholder="—"
        className="input !text-xs !py-1 w-16 text-center"
      />
      <span className="text-xs text-gray-500">gün</span>
      {dirty && (
        <button onClick={save} disabled={busy} className="btn-primary !text-[11px] !py-1 !px-2 disabled:opacity-50">
          {busy ? '...' : 'Kaydet'}
        </button>
      )}
      <span className="text-[10px] text-gray-600">(sipariş tarihi + gün = kargo sözü)</span>
    </div>
  )
}


function KargoEditor() {
  // Kargo yolu artık mağaza başına seçilmiyor: tüm gönderiler Sürat'a doğrudan
  // gider (backend packaging.kargo_handler_kodu). Basit Kargo aracısı kapalı;
  // eskiden bayi/vitrin mağazalarında ayar boş kalıp Basit Kargo'ya düşüyor ve
  // Sürat takip kodu oluşmuyordu.
  return (
    <div className="mt-2 flex items-center gap-2">
      <span className="text-xs text-gray-500">📦 Kargo:</span>
      <span className="text-xs text-gray-300">Sürat Kargo — doğrudan</span>
    </div>
  )
}

function AddStoreDialog({ platforms, onClose, onSaved }) {
  const [platform, setPlatform] = useState(platforms[0]?.id || 'shopify')
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [config, setConfig] = useState({})
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  // Shopify için: 'token' (custom app) | 'oauth' (Client ID/Secret + handshake)
  const [shopifyAuthMode, setShopifyAuthMode] = useState('token')
  const platformMeta = platforms.find(p => p.id === platform)
  const isShopify = platform === 'shopify'
  const isOAuth = isShopify && shopifyAuthMode === 'oauth'

  const handleOAuthStart = async () => {
    setError('')
    if (!name.trim() || !slug.trim()) {
      setError('Görünen ad ve slug zorunlu')
      return
    }
    if (!config.store_url?.trim() || !config.client_id?.trim() || !config.client_secret?.trim()) {
      setError('Mağaza URL, Client ID ve Client Secret zorunlu')
      return
    }
    setSaving(true)
    try {
      const r = await api.post('/api/stores/oauth/start', {
        store_url: config.store_url.trim(),
        client_id: config.client_id.trim(),
        client_secret: config.client_secret.trim(),
        name: name.trim(),
        slug: slug.trim(),
      })
      if (r?.install_url) {
        window.location.href = r.install_url
      } else {
        setError('install_url alınamadı')
        setSaving(false)
      }
    } catch (err) {
      setError(typeof err?.detail === 'string' ? err.detail : 'OAuth başlatılamadı')
      setSaving(false)
    }
  }

  // Otomatik slug üret name'den
  const handleNameChange = (v) => {
    setName(v)
    if (!slug || slug === slugify(name)) {
      setSlug(slugify(v))
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (isOAuth) {
      return handleOAuthStart()
    }

    // Token mode (eski mantık)
    for (const f of platformMeta?.fields || []) {
      if (f.required && !config[f.key]?.trim()) {
        setError(`"${f.label}" zorunlu`)
        return
      }
    }

    setSaving(true)
    try {
      await api.post('/api/stores', { name, slug, platform, config })
      onSaved()
    } catch (err) {
      setError(err.detail || 'Kaydetme başarısız')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl p-5 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">Yeni Mağaza Ekle</h2>

        <form onSubmit={handleSubmit} className="space-y-3">
          {/* Platform */}
          <div>
            <label className="text-xs text-gray-400 block mb-1">Platform</label>
            <div className="grid grid-cols-2 gap-2">
              {platforms.map(p => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => { setPlatform(p.id); setConfig({}) }}
                  className={`px-3 py-2 rounded-lg text-sm border transition-colors ${
                    platform === p.id
                      ? 'bg-accent/15 border-accent/50 text-accent'
                      : 'bg-brand-input border-brand-border text-gray-300 hover:border-gray-600'
                  }`}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>

          {/* Name */}
          <div>
            <label className="text-xs text-gray-400 block mb-1">Görünen ad</label>
            <input
              type="text"
              required
              value={name}
              onChange={e => handleNameChange(e.target.value)}
              className="input w-full"
              placeholder="Örn: BERNZ Company"
            />
          </div>

          {/* Slug */}
          <div>
            <label className="text-xs text-gray-400 block mb-1">Slug (kısa kod)</label>
            <input
              type="text"
              required
              pattern="[a-z0-9\-]+"
              value={slug}
              onChange={e => setSlug(e.target.value.toLowerCase())}
              className="input w-full font-mono"
              placeholder="bernz"
            />
            <p className="text-[10px] text-gray-600 mt-1">Sadece küçük harf, rakam, tire</p>
          </div>

          {/* Shopify için: OAuth / Token toggle */}
          {isShopify && (
            <div>
              <label className="text-xs text-gray-400 block mb-1">Bağlanma Yöntemi</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => { setShopifyAuthMode('token'); setConfig({}) }}
                  className={`px-2 py-1.5 rounded-lg text-xs border transition-colors ${
                    shopifyAuthMode === 'token'
                      ? 'bg-accent/15 border-accent/50 text-accent'
                      : 'bg-brand-input border-brand-border text-gray-400 hover:border-gray-600'
                  }`}
                >
                  🔑 Custom App<br/><span className="text-[10px] opacity-70">(eski, access_token ile)</span>
                </button>
                <button
                  type="button"
                  onClick={() => { setShopifyAuthMode('oauth'); setConfig({}) }}
                  className={`px-2 py-1.5 rounded-lg text-xs border transition-colors ${
                    shopifyAuthMode === 'oauth'
                      ? 'bg-accent/15 border-accent/50 text-accent'
                      : 'bg-brand-input border-brand-border text-gray-400 hover:border-gray-600'
                  }`}
                >
                  🔐 OAuth<br/><span className="text-[10px] opacity-70">(2026+, Client ID/Secret)</span>
                </button>
              </div>
            </div>
          )}

          {/* Shopify OAuth alanları */}
          {isOAuth && (
            <>
              <div>
                <label className="text-xs text-gray-400 block mb-1">
                  Mağaza URL <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={config.store_url || ''}
                  onChange={e => setConfig(prev => ({ ...prev, store_url: e.target.value }))}
                  className="input w-full"
                  placeholder="lunera.myshopify.com"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">
                  Client ID <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={config.client_id || ''}
                  onChange={e => setConfig(prev => ({ ...prev, client_id: e.target.value }))}
                  className="input w-full font-mono"
                  placeholder="Shopify Partner Dashboard'dan alın"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">
                  Client Secret <span className="text-red-400">*</span>
                </label>
                <input
                  type="password"
                  value={config.client_secret || ''}
                  onChange={e => setConfig(prev => ({ ...prev, client_secret: e.target.value }))}
                  className="input w-full font-mono"
                  placeholder="••••••••"
                />
              </div>
              <div className="text-[11px] text-gray-500 bg-brand-input/40 rounded-lg p-2 border border-brand-border/50">
                <div className="text-amber-400 mb-1">⚠ Shopify Partner Dashboard'da yapılması gerekenler:</div>
                <ul className="space-y-0.5 list-disc list-inside opacity-90">
                  <li>App URL: <span className="font-mono">https://studio.bernzcompany.com</span></li>
                  <li>Allowed redirection URL: <span className="font-mono break-all">https://studio.bernzcompany.com/api/stores/oauth/callback</span></li>
                  <li>API access scopes: read/write_orders, read_products, read/write_fulfillments, read_customers</li>
                </ul>
              </div>
            </>
          )}

          {/* Token mode veya non-Shopify platform-specific fields */}
          {!isOAuth && platformMeta?.fields.map(f => (
            <div key={f.key}>
              <label className="text-xs text-gray-400 block mb-1">
                {f.label} {f.required && <span className="text-red-400">*</span>}
              </label>
              <input
                type={f.type === 'password' ? 'password' : 'text'}
                value={config[f.key] || ''}
                onChange={e => setConfig(prev => ({ ...prev, [f.key]: e.target.value }))}
                className="input w-full"
                placeholder={f.placeholder || f.default || ''}
                defaultValue={f.default}
              />
            </div>
          ))}

          {platformMeta?.not && (
            <p className="text-[11px] text-gray-500 bg-brand-input/40 rounded-lg px-3 py-2 border border-brand-border/50">
              {platformMeta.not}
            </p>
          )}

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">
              İptal
            </button>
            <button type="submit" disabled={saving} className="btn-primary flex-1">
              {saving
                ? (isOAuth ? 'Shopify\'a yönlendiriliyor...' : 'Kaydediliyor...')
                : (isOAuth ? '🔐 Shopify\'a Bağlan' : 'Kaydet')
              }
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


// Helpers
const TR_MAP = {ç:'c',ğ:'g',ı:'i',ö:'o',ş:'s',ü:'u',Ç:'c',Ğ:'g',İ:'i',Ö:'o',Ş:'s',Ü:'u'}
function slugify(text) {
  return (text || '')
    .split('').map(c => TR_MAP[c] || c).join('')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 50)
}
