import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Ürünler — katalog yönetimi (Faz 4'te tam sayfa editöre genişleyecek).
export default function UrunlerPage() {
  const { storeId } = useStore()
  const [products, setProducts] = useState([])
  const [collections, setCollections] = useState([])
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)

  const load = useCallback(async () => {
    if (!storeId) return
    setLoading(true); setError('')
    try {
      const [p, c] = await Promise.all([
        api.get(`/api/catalog/products?store_id=${storeId}`),
        api.get(`/api/catalog/collections?store_id=${storeId}`),
      ])
      setProducts(p); setCollections(c)
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Ürünler yüklenemedi')
    } finally { setLoading(false) }
  }, [storeId])

  useEffect(() => { load() }, [load])

  const openDetail = async (id) => {
    try { setSelected(await api.get(`/api/catalog/products/${id}`)) }
    catch { setError('Ürün açılamadı') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Ürünler</h1>
        <span className="text-sm text-panel-muted">{products.length} ürün</span>
        <button onClick={() => setShowCreate(true)} className="btn-primary ml-auto">+ Yeni Ürün</button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && <p className="text-sm text-panel-muted">Yükleniyor…</p>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {products.map(p => (
          <button key={p.id} onClick={() => openDetail(p.id)}
            className="text-left card !p-0 overflow-hidden hover:shadow-md hover:border-panel-accent/40 transition">
            <div className="aspect-square bg-panel-input flex items-center justify-center">
              {p.cover_image
                ? <img src={p.cover_image} alt={p.title} className="w-full h-full object-cover" />
                : <span className="text-3xl opacity-30">🖼️</span>}
            </div>
            <div className="p-3">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm truncate">{p.title}</span>
                <StatusBadge status={p.status} />
              </div>
              <div className="text-xs text-panel-muted mt-1">
                {fmtPrice(p.base_price)} · {p.variant_count} varyant
              </div>
            </div>
          </button>
        ))}
      </div>
      {!loading && products.length === 0 && (
        <div className="card text-center !p-10">
          <div className="text-3xl">🛍️</div>
          <p className="mt-2 text-sm text-panel-muted">
            Henüz ürün yok — ilk ürününü ekleyerek satışa başla.
          </p>
          <button onClick={() => setShowCreate(true)} className="btn-primary mt-4">+ Yeni Ürün</button>
        </div>
      )}

      {showCreate && (
        <CreateProductModal storeId={storeId}
          onClose={() => setShowCreate(false)}
          onCreated={(p) => { setShowCreate(false); load(); setSelected(p) }} />
      )}
      {selected && (
        <ProductDetailModal product={selected} collections={collections}
          onClose={() => { setSelected(null); load() }}
          onRefresh={() => openDetail(selected.id)} />
      )}
    </div>
  )
}

export function StatusBadge({ status }) {
  const map = {
    draft: ['Taslak', 'bg-slate-100 text-slate-600'],
    active: ['Yayında', 'bg-emerald-100 text-emerald-700'],
    archived: ['Arşiv', 'bg-amber-100 text-amber-700'],
  }
  const [label, cls] = map[status] || [status, 'bg-slate-100 text-slate-600']
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${cls} shrink-0`}>{label}</span>
}

export function fmtPrice(v) {
  const n = Number(v)
  if (Number.isNaN(n)) return v
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n)
}

export function Modal({ title, children, onClose, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div className={`card w-full ${wide ? 'max-w-2xl' : 'max-w-md'} max-h-[85vh] overflow-y-auto !p-5`}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold truncate">{title}</h2>
          <button onClick={onClose} className="text-panel-muted hover:text-panel-ink text-lg leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

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
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Ürün adı</span>
          <input className="input mt-1" value={title} onChange={e => setTitle(e.target.value)}
            required maxLength={300} placeholder="Örn: Retro Dalga Telefon Kılıfı" />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Fiyat (₺)</span>
          <input className="input mt-1" value={price} onChange={e => setPrice(e.target.value)}
            required type="number" min="0" step="0.01" placeholder="349.90" />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Açıklama</span>
          <textarea className="input mt-1" rows={4} value={description}
            onChange={e => setDescription(e.target.value)} maxLength={20000} />
        </label>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button disabled={busy} className="btn-primary">
            {busy ? 'Kaydediliyor…' : 'Oluştur'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function ProductDetailModal({ product, collections = [], onClose, onRefresh }) {
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [variations, setVariations] = useState('')

  const patch = async (body) => {
    setBusy(true); setErr('')
    try { await api.patch(`/api/catalog/products/${product.id}`, body); await onRefresh() }
    catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Güncellenemedi') }
    finally { setBusy(false) }
  }

  const toggleCollection = async (cid) => {
    const current = new Set(product.collection_ids || [])
    current.has(cid) ? current.delete(cid) : current.add(cid)
    setBusy(true); setErr('')
    try {
      await api.put(`/api/catalog/products/${product.id}/collections`, { collection_ids: [...current] })
      await onRefresh()
    } catch { setErr('Koleksiyon güncellenemedi') }
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
    if (!window.confirm('Bu ürün tüm varyant ve görselleriyle silinecek. Emin misiniz?')) return
    setBusy(true)
    try { await api.del(`/api/catalog/products/${product.id}`); onClose() }
    catch { setErr('Ürün silinemedi'); setBusy(false) }
  }

  return (
    <Modal title={product.title} onClose={onClose} wide>
      <div className="space-y-5">
        <div className="flex items-center gap-2 flex-wrap text-sm">
          <StatusBadge status={product.status} />
          <span className="text-panel-muted">/{product.slug} · {fmtPrice(product.base_price)}</span>
          <div className="ml-auto flex gap-2">
            {product.status !== 'active' ? (
              <button disabled={busy} onClick={() => patch({ status: 'active' })}
                className="px-3 py-1 rounded-lg text-xs bg-emerald-100 text-emerald-700">Yayınla</button>
            ) : (
              <button disabled={busy} onClick={() => patch({ status: 'draft' })}
                className="px-3 py-1 rounded-lg text-xs bg-slate-100 text-slate-600">Taslağa Al</button>
            )}
            <button disabled={busy} onClick={removeProduct}
              className="px-3 py-1 rounded-lg text-xs bg-red-50 text-red-700">Sil</button>
          </div>
        </div>

        <section>
          <h3 className="text-sm font-medium mb-2">Görseller</h3>
          <div className="flex gap-2 flex-wrap">
            {product.images.map(im => (
              <div key={im.id} className="relative group">
                <img src={im.url} alt={im.alt || ''}
                  className="w-20 h-20 object-cover rounded-xl border border-panel-border" />
                <button onClick={() => removeImage(im.id)}
                  className="absolute -top-1.5 -right-1.5 hidden group-hover:block bg-red-600 text-white rounded-full w-5 h-5 text-xs">×</button>
              </div>
            ))}
            <label className="w-20 h-20 rounded-xl border border-dashed border-panel-border flex items-center justify-center cursor-pointer text-2xl text-panel-muted hover:text-panel-ink hover:border-slate-400">
              +
              <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                onChange={e => uploadImage(e.target.files?.[0])} />
            </label>
          </div>
        </section>

        {collections.length > 0 && (
          <section>
            <h3 className="text-sm font-medium mb-2">Koleksiyonlar</h3>
            <div className="flex gap-2 flex-wrap">
              {collections.map(c => {
                const active = (product.collection_ids || []).includes(c.id)
                return (
                  <button key={c.id} disabled={busy} onClick={() => toggleCollection(c.id)}
                    className={`px-3 py-1 rounded-full text-xs border transition ${active
                      ? 'border-panel-accent bg-emerald-50 text-emerald-700'
                      : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
                    {c.title}
                  </button>
                )
              })}
            </div>
          </section>
        )}

        <section>
          <h3 className="text-sm font-medium mb-2">Varyantlar ({product.variants.length})</h3>
          <div className="flex gap-2 mb-3">
            <input className="input flex-1" value={variations}
              onChange={e => setVariations(e.target.value)}
              placeholder="Renkler (virgülle): SİYAH, ŞEFFAF — boş = renksiz" />
            <button disabled={busy} onClick={bulkVariants} className="btn-ghost whitespace-nowrap text-xs">
              Telefon modellerinden üret
            </button>
          </div>
          <div className="max-h-64 overflow-y-auto border border-panel-border rounded-xl">
            <table className="w-full text-xs">
              <thead className="text-panel-muted bg-panel-input sticky top-0">
                <tr>
                  <th className="text-left px-3 py-2">Model</th>
                  <th className="text-left px-3 py-2">Renk</th>
                  <th className="text-right px-3 py-2">Stok</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {product.variants.map(v => (
                  <tr key={v.id} className="border-t border-panel-border">
                    <td className="px-3 py-1.5">{v.model_display}</td>
                    <td className="px-3 py-1.5">{v.variation || '—'}</td>
                    <td className="px-3 py-1.5 text-right">{v.track_stock ? v.quantity : '∞'}</td>
                    <td className="px-2 py-1.5 text-right">
                      <button onClick={() => removeVariant(v.id)} className="text-red-400 hover:text-red-600">×</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {product.variants.length === 0 && (
              <div className="text-xs text-panel-muted p-3">
                Henüz varyant yok — üstteki butonla telefon modellerinden üretin.
              </div>
            )}
          </div>
        </section>

        {err && <p className="text-sm text-red-600">{err}</p>}
      </div>
    </Modal>
  )
}
