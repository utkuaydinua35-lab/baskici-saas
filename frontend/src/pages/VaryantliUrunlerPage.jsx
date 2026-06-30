import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

// Kılıf varyasyonu seçenekleri (Design.kalip_tipi -> mold_planner normalize_variation)
const VARYASYONLAR = ['SİYAH', 'BEYAZ', 'ŞEFFAF', 'PARLAK', 'MAGSAFE']

export default function VaryantliUrunlerPage() {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState(localStorage.getItem('vu_store') || '')
  const [designs, setDesigns] = useState([])
  const [unmatched, setUnmatched] = useState([])
  const [loading, setLoading] = useState(false)
  const [selProduct, setSelProduct] = useState('')  // product_id
  const [search, setSearch] = useState('')

  useEffect(() => {
    api.get('/api/stores?include_bayii=true').then(s => {
      const list = Array.isArray(s) ? s : []
      setStores(list)
      if (!storeId && list[0]) { setStoreId(list[0].id); localStorage.setItem('vu_store', list[0].id) }
    }).catch(() => {})
  }, [])

  const load = async (sid = storeId) => {
    if (!sid) return
    setLoading(true)
    try {
      const [d, u] = await Promise.all([
        api.get(`/api/designs?store_id=${sid}&per_page=500`).catch(() => ({})),
        api.get(`/api/designs/_meta/unmatched-products?store_id=${sid}`).catch(() => ({})),
      ])
      setDesigns(d?.items || d?.designs || (Array.isArray(d) ? d : []))
      setUnmatched(u?.items || [])
    } catch { toast.error('Yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [storeId])

  // Ürün listesi: tasarımı olan ürünler + sipariş ürünleri (birleşik)
  const products = useMemo(() => {
    const map = new Map()
    for (const d of designs) {
      if (!d.product_id) continue
      if (!map.has(d.product_id)) map.set(d.product_id, { product_id: d.product_id, title: d.product_title || '', image: d.product_image_url || '', variants: 0 })
      if ((d.variant_title || '').trim()) map.get(d.product_id).variants++
    }
    for (const u of unmatched) {
      if (!map.has(u.product_id)) map.set(u.product_id, { product_id: u.product_id, title: u.sample_title || '', image: u.sample_image || '', variants: 0 })
    }
    return [...map.values()].sort((a, b) => (b.variants - a.variants) || (a.title || '').localeCompare(b.title || '', 'tr'))
  }, [designs, unmatched])

  const filteredProducts = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return products
    return products.filter(p => (p.title || '').toLowerCase().includes(q) || (p.product_id || '').toLowerCase().includes(q))
  }, [products, search])

  const variantDesigns = useMemo(
    () => designs.filter(d => d.product_id === selProduct && (d.variant_title || '').trim()),
    [designs, selProduct])
  const prodInfo = products.find(p => p.product_id === selProduct)

  return (
    <div className="mx-auto w-full max-w-[1100px] page-enter">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-1">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🎭 Varyantlı Ürünler</h1>
          <p className="text-sm text-gray-500 mt-1">Müşterinin seçtiği varyanta göre farklı tasarım + kılıf varyasyonu ile kalıba eklenir.</p>
        </div>
        <select value={storeId} onChange={e => { setStoreId(e.target.value); localStorage.setItem('vu_store', e.target.value); setSelProduct('') }}
          className="input !text-sm !py-1.5 min-w-[180px]">
          <optgroup label="Mağazalar">
            {stores.filter(s => s.platform !== 'bayii').map(s => <option key={s.id} value={s.id}>🏪 {s.name}</option>)}
          </optgroup>
          <optgroup label="Bayiler">
            {stores.filter(s => s.platform === 'bayii').map(s => <option key={s.id} value={s.id}>🤝 {(s.name || '').replace(/^Bayii:\s*/, '')}</option>)}
          </optgroup>
        </select>
      </div>

      <div className="grid md:grid-cols-[300px_1fr] gap-4 mt-4">
        {/* Ürün listesi */}
        <div className="card !p-0 overflow-hidden self-start">
          <div className="px-3 py-2 border-b border-brand-border text-xs text-gray-500 uppercase tracking-wide">Ürün seç</div>
          <div className="p-2 border-b border-brand-border">
            <input className="input w-full !text-sm !py-1.5" placeholder="🔍 Ürün ara (ad / id)"
              value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <div className="max-h-[70vh] overflow-y-auto">
            {loading ? <div className="p-4 text-sm text-gray-500">Yükleniyor…</div>
              : filteredProducts.length === 0 ? <div className="p-4 text-sm text-gray-600">{search.trim() ? 'Eşleşen ürün yok.' : 'Ürün yok.'}</div>
              : filteredProducts.map(p => (
                <button key={p.product_id} onClick={() => setSelProduct(p.product_id)}
                  className={`w-full text-left px-3 py-2.5 border-b border-brand-border/40 flex items-center gap-2.5 hover:bg-brand-input/40 ${selProduct === p.product_id ? 'bg-accent/10' : ''}`}>
                  {p.image ? <img src={p.image} alt="" className="w-9 h-9 rounded object-cover shrink-0" />
                    : <div className="w-9 h-9 rounded bg-brand-input shrink-0" />}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-gray-200 truncate">{p.title || `Ürün ${p.product_id}`}</div>
                    <div className="text-[11px] text-gray-500">{p.variants > 0 ? `${p.variants} varyant` : 'varyant yok'}</div>
                  </div>
                </button>
              ))}
          </div>
        </div>

        {/* Seçili ürünün varyantları + ekleme */}
        <div>
          {!selProduct ? (
            <div className="card text-center py-16 text-gray-500"><div className="text-4xl mb-2">🎭</div>Soldan bir ürün seç.</div>
          ) : (
            <>
              <div className="card mb-3 flex items-center gap-3">
                {prodInfo?.image && <img src={prodInfo.image} alt="" className="w-12 h-12 rounded object-cover" />}
                <div>
                  <div className="text-sm font-semibold text-gray-100">{prodInfo?.title || `Ürün ${selProduct}`}</div>
                  <div className="text-[11px] text-gray-500 font-mono">product_id: {selProduct}</div>
                </div>
              </div>

              {variantDesigns.length > 0 && (
                <div className="space-y-2 mb-3">
                  {variantDesigns.map(d => (
                    <div key={d.id} className="card !py-2.5 flex items-center gap-3">
                      {d.thumbnail_url ? <img src={d.thumbnail_url} alt="" className="w-10 h-10 rounded object-cover" />
                        : <div className="w-10 h-10 rounded bg-brand-input" />}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-200">Müşteri seçimi: <b className="text-accent">{d.variant_title}</b></div>
                        <div className="text-[11px] text-gray-500">Kılıf: {d.kalip_tipi || '—'} · kod: {d.code}</div>
                      </div>
                      <button onClick={() => delVariant(d)} className="text-xs text-red-400 hover:text-red-300 shrink-0">Sil</button>
                    </div>
                  ))}
                </div>
              )}

              <AddVariantForm storeId={storeId} product={prodInfo} onAdded={() => load()} />
            </>
          )}
        </div>
      </div>
    </div>
  )

  async function delVariant(d) {
    if (!confirm(`"${d.variant_title}" varyantı silinsin mi?`)) return
    try { await api.del(`/api/designs/${d.id}`); toast.success('Silindi'); load() }
    catch (e) { toast.error(e.detail || 'Silinemedi') }
  }
}

function AddVariantForm({ storeId, product, onAdded }) {
  const toast = useToast()
  const [variantAdi, setVariantAdi] = useState('')
  const [varyasyon, setVaryasyon] = useState('SİYAH')
  const [kod, setKod] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!variantAdi.trim()) { toast.error('Müşteri varyant adını yaz (örn. Şeffaf)'); return }
    if (!file) { toast.error('Tasarım dosyası seç'); return }
    const code = (kod.trim() || `${(product?.product_id || '').slice(-5)}-${variantAdi.trim()}`).slice(0, 50)
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('store_id', storeId)
      fd.append('code', code)
      fd.append('product_id', product.product_id)
      if (product?.title) fd.append('product_title', product.title)
      if (product?.image) fd.append('product_image_url', product.image)
      fd.append('variant_title', variantAdi.trim())
      fd.append('kalip_tipi', varyasyon)
      await api.postForm('/api/designs', fd)
      toast.success('Varyant eklendi')
      setVariantAdi(''); setKod(''); setFile(null); setVaryasyon('SİYAH')
      onAdded?.()
    } catch (e) { toast.error(e.detail || 'Eklenemedi') }
    finally { setBusy(false) }
  }

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-gray-200 mb-3">＋ Varyant ekle</h3>
      <div className="grid sm:grid-cols-2 gap-2.5">
        <div>
          <label className="block text-[10px] uppercase text-gray-500 mb-1">Müşteri varyant adı (property değeri)</label>
          <input className="input w-full !text-sm" placeholder="örn. Şeffaf" value={variantAdi} onChange={e => setVariantAdi(e.target.value)} />
        </div>
        <div>
          <label className="block text-[10px] uppercase text-gray-500 mb-1">Kılıf varyasyonu</label>
          <select className="input w-full !text-sm" value={varyasyon} onChange={e => setVaryasyon(e.target.value)}>
            {VARYASYONLAR.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-[10px] uppercase text-gray-500 mb-1">Tasarım kodu (boş = otomatik)</label>
          <input className="input w-full !text-sm" placeholder="otomatik" value={kod} onChange={e => setKod(e.target.value)} />
        </div>
        <div>
          <label className="block text-[10px] uppercase text-gray-500 mb-1">Tasarım dosyası</label>
          <input type="file" accept="image/png,image/jpeg,image/webp,application/pdf"
            onChange={e => setFile(e.target.files?.[0] || null)} className="text-xs text-gray-400 w-full" />
        </div>
      </div>
      <p className="text-[11px] text-gray-500 mt-2">Müşteri Shopify'da bu adı (ya da içeren bir değer) seçtiğinde bu tasarım + kılıf varyasyonu kalıba eklenir.</p>
      <div className="flex justify-end mt-3">
        <button onClick={submit} disabled={busy} className="btn-primary !text-sm disabled:opacity-50">{busy ? 'Ekleniyor…' : 'Varyantı Kaydet'}</button>
      </div>
    </div>
  )
}
