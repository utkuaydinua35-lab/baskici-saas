import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

// Vitrin (kendi mağazamız) katalog yönetimi — MVP: ürün listesi + oluşturma +
// varyant (telefon modellerinden toplu) + görsel yükleme.
export default function VitrinPage() {
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [products, setProducts] = useState([])
  const [selected, setSelected] = useState(null)   // detay açık ürün (full)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    api.get('/api/stores').then(list => {
      const sf = (Array.isArray(list) ? list : []).filter(s => s.platform === 'storefront')
      setStores(sf)
      if (sf.length > 0) setStoreId(sf[0].id)
    }).catch(e => setError(e.detail || 'Mağazalar yüklenemedi'))
  }, [])

  const load = useCallback(async (sid) => {
    if (!sid) { setProducts([]); return }
    setLoading(true); setError('')
    try {
      setProducts(await api.get(`/api/catalog/products?store_id=${sid}`))
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Ürünler yüklenemedi')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load(storeId) }, [storeId, load])

  const openDetail = async (id) => {
    try { setSelected(await api.get(`/api/catalog/products/${id}`)) }
    catch (e) { setError(e.detail || 'Ürün açılamadı') }
  }

  if (stores.length === 0) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold mb-3">Vitrin</h1>
        <div className="bg-brand-card border border-brand-border rounded-xl p-6 text-sm text-gray-400">
          Henüz bir vitrin mağazanız yok. <b>Atölyeler</b> sayfasından platformu
          <b> “Kendi Mağazam (Vitrin)”</b> olan bir mağaza ekleyin; sonra ürünlerinizi
          burada yönetebilirsiniz.
        </div>
        {error && <div className="mt-3 text-sm text-red-400">{error}</div>}
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Vitrin</h1>
        <select value={storeId} onChange={e => setStoreId(e.target.value)}
          className="bg-brand-input border border-brand-border rounded-lg px-3 py-1.5 text-sm">
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button onClick={() => setShowCreate(true)}
          className="ml-auto px-3 py-1.5 rounded-lg text-sm font-medium text-black"
          style={{ background: 'rgb(var(--accent-rgb))' }}>
          + Yeni Ürün
        </button>
      </div>

      {error && <div className="text-sm text-red-400">{error}</div>}
      {loading && <div className="text-sm text-gray-400">Yükleniyor…</div>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {products.map(p => (
          <button key={p.id} onClick={() => openDetail(p.id)}
            className="text-left bg-brand-card border border-brand-border rounded-xl overflow-hidden hover:border-gray-500 transition">
            <div className="aspect-square bg-brand-input flex items-center justify-center">
              {p.cover_image
                ? <img src={p.cover_image} alt={p.title} className="w-full h-full object-cover" />
                : <span className="text-3xl opacity-30">🖼️</span>}
            </div>
            <div className="p-3">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm truncate">{p.title}</span>
                <StatusBadge status={p.status} />
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {fmtPrice(p.base_price)} · {p.variant_count} varyant
              </div>
            </div>
          </button>
        ))}
      </div>
      {!loading && products.length === 0 && (
        <div className="text-sm text-gray-400">Bu mağazada henüz ürün yok.</div>
      )}

      {showCreate && (
        <CreateProductModal storeId={storeId}
          onClose={() => setShowCreate(false)}
          onCreated={(p) => { setShowCreate(false); load(storeId); setSelected(p) }} />
      )}
      {selected && (
        <ProductDetailModal product={selected}
          onClose={() => { setSelected(null); load(storeId) }}
          onRefresh={() => openDetail(selected.id)} />
      )}
    </div>
  )
}

function StatusBadge({ status }) {
  const map = {
    draft: ['Taslak', 'bg-gray-600/40 text-gray-300'],
    active: ['Yayında', 'bg-emerald-600/30 text-emerald-300'],
    archived: ['Arşiv', 'bg-amber-600/30 text-amber-300'],
  }
  const [label, cls] = map[status] || [status, 'bg-gray-600/40']
  return <span className={`text-[10px] px-1.5 py-0.5 rounded ${cls} shrink-0`}>{label}</span>
}

function fmtPrice(v) {
  const n = Number(v)
  if (Number.isNaN(n)) return v
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n)
}

function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="text-gray-400 text-xs">{label}</span>
      {children}
    </label>
  )
}

const inputCls = 'mt-1 w-full bg-brand-input border border-brand-border rounded-lg px-3 py-2 text-sm'

function CreateProductModal({ storeId, onClose, onCreated }) {
  const [title, setTitle] = useState('')
  const [price, setPrice] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      const p = await api.post('/api/catalog/products', {
        store_id: storeId, title, base_price: price, description: description || null,
      })
      onCreated(p)
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Ürün oluşturulamadı')
    } finally { setBusy(false) }
  }

  return (
    <Modal title="Yeni Ürün" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Ürün adı">
          <input className={inputCls} value={title} onChange={e => setTitle(e.target.value)}
            required maxLength={300} placeholder="Örn: Retro Dalga Telefon Kılıfı" />
        </Field>
        <Field label="Fiyat (₺)">
          <input className={inputCls} value={price} onChange={e => setPrice(e.target.value)}
            required type="number" min="0" step="0.01" placeholder="349.90" />
        </Field>
        <Field label="Açıklama (düz metin)">
          <textarea className={inputCls} rows={4} value={description}
            onChange={e => setDescription(e.target.value)} maxLength={20000} />
        </Field>
        {err && <div className="text-sm text-red-400">{err}</div>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-gray-400">Vazgeç</button>
          <button disabled={busy} className="px-4 py-1.5 rounded-lg text-sm font-medium text-black disabled:opacity-50"
            style={{ background: 'rgb(var(--accent-rgb))' }}>
            {busy ? 'Kaydediliyor…' : 'Oluştur'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function ProductDetailModal({ product, onClose, onRefresh }) {
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [variations, setVariations] = useState('')

  const patch = async (body) => {
    setBusy(true); setErr('')
    try { await api.patch(`/api/catalog/products/${product.id}`, body); await onRefresh() }
    catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Güncellenemedi') }
    finally { setBusy(false) }
  }

  const bulkVariants = async () => {
    setBusy(true); setErr('')
    try {
      const vars = variations.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
      const r = await api.post(`/api/catalog/products/${product.id}/variants/bulk`, { variations: vars })
      await onRefresh()
      if (r.created === 0) setErr('Yeni varyant eklenmedi (hepsi zaten mevcut olabilir)')
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Varyantlar oluşturulamadı') }
    finally { setBusy(false) }
  }

  const uploadImage = async (file) => {
    if (!file) return
    setBusy(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      await api.postForm(`/api/catalog/products/${product.id}/images`, fd)
      await onRefresh()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Görsel yüklenemedi') }
    finally { setBusy(false) }
  }

  const removeImage = async (id) => {
    setBusy(true)
    try { await api.del(`/api/catalog/images/${id}`); await onRefresh() }
    catch { setErr('Görsel silinemedi') }
    finally { setBusy(false) }
  }

  const removeVariant = async (id) => {
    setBusy(true)
    try { await api.del(`/api/catalog/variants/${id}`); await onRefresh() }
    catch { setErr('Varyant silinemedi') }
    finally { setBusy(false) }
  }

  const removeProduct = async () => {
    if (!window.confirm('Bu ürün, tüm varyantları ve görselleriyle silinecek. Emin misiniz?')) return
    setBusy(true)
    try { await api.del(`/api/catalog/products/${product.id}`); onClose() }
    catch { setErr('Ürün silinemedi'); setBusy(false) }
  }

  return (
    <Modal title={product.title} onClose={onClose} wide>
      <div className="space-y-5">
        <div className="flex items-center gap-2 flex-wrap text-sm">
          <StatusBadge status={product.status} />
          <span className="text-gray-400">/{product.slug}</span>
          <span className="text-gray-400">· {fmtPrice(product.base_price)}</span>
          <div className="ml-auto flex gap-2">
            {product.status !== 'active' && (
              <button disabled={busy} onClick={() => patch({ status: 'active' })}
                className="px-3 py-1 rounded-lg text-xs bg-emerald-600/30 text-emerald-300">Yayınla</button>
            )}
            {product.status === 'active' && (
              <button disabled={busy} onClick={() => patch({ status: 'draft' })}
                className="px-3 py-1 rounded-lg text-xs bg-gray-600/40 text-gray-300">Taslağa Al</button>
            )}
            <button disabled={busy} onClick={removeProduct}
              className="px-3 py-1 rounded-lg text-xs bg-red-600/25 text-red-300">Sil</button>
          </div>
        </div>

        <section>
          <h3 className="text-sm font-medium mb-2">Görseller</h3>
          <div className="flex gap-2 flex-wrap">
            {product.images.map(im => (
              <div key={im.id} className="relative group">
                <img src={im.url} alt={im.alt || ''} className="w-20 h-20 object-cover rounded-lg border border-brand-border" />
                <button onClick={() => removeImage(im.id)}
                  className="absolute -top-1.5 -right-1.5 hidden group-hover:block bg-red-600 text-white rounded-full w-5 h-5 text-xs">×</button>
              </div>
            ))}
            <label className="w-20 h-20 rounded-lg border border-dashed border-brand-border flex items-center justify-center cursor-pointer text-2xl text-gray-500 hover:text-gray-300">
              +
              <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                onChange={e => uploadImage(e.target.files?.[0])} />
            </label>
          </div>
        </section>

        <section>
          <h3 className="text-sm font-medium mb-2">Varyantlar ({product.variants.length})</h3>
          <div className="flex gap-2 mb-3">
            <input className={inputCls + ' mt-0 flex-1'} value={variations}
              onChange={e => setVariations(e.target.value)}
              placeholder="Renkler (virgülle): SİYAH, ŞEFFAF — boş bırakılırsa renksiz" />
            <button disabled={busy} onClick={bulkVariants}
              className="px-3 py-2 rounded-lg text-xs bg-brand-input border border-brand-border whitespace-nowrap">
              Telefon modellerinden üret
            </button>
          </div>
          <div className="max-h-64 overflow-y-auto border border-brand-border rounded-lg">
            <table className="w-full text-xs">
              <thead className="text-gray-400 bg-brand-input sticky top-0">
                <tr>
                  <th className="text-left px-3 py-2">Model</th>
                  <th className="text-left px-3 py-2">Renk</th>
                  <th className="text-right px-3 py-2">Stok</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {product.variants.map(v => (
                  <tr key={v.id} className="border-t border-brand-border/50">
                    <td className="px-3 py-1.5">{v.model_display}</td>
                    <td className="px-3 py-1.5">{v.variation || '—'}</td>
                    <td className="px-3 py-1.5 text-right">{v.track_stock ? v.quantity : '∞'}</td>
                    <td className="px-2 py-1.5 text-right">
                      <button onClick={() => removeVariant(v.id)} className="text-red-400/70 hover:text-red-400">×</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {product.variants.length === 0 && (
              <div className="text-xs text-gray-500 p-3">Henüz varyant yok — üstteki butonla telefon modellerinden üretin.</div>
            )}
          </div>
        </section>

        {err && <div className="text-sm text-red-400">{err}</div>}
      </div>
    </Modal>
  )
}

function Modal({ title, children, onClose, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div className={`bg-brand-card border border-brand-border rounded-2xl p-5 w-full ${wide ? 'max-w-2xl' : 'max-w-md'} max-h-[85vh] overflow-y-auto`}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold truncate">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-lg leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}
