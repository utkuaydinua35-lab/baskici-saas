import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Koleksiyonlar — ürün grupları (vitrinde sayfa + filtre olarak görünür).
export default function KoleksiyonlarPage() {
  const { storeId } = useStore()
  const [collections, setCollections] = useState([])
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    if (!storeId) return
    try { setCollections(await api.get(`/api/catalog/collections?store_id=${storeId}`)) }
    catch { setErr('Koleksiyonlar yüklenemedi') }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const create = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    setBusy(true); setErr('')
    try {
      await api.post('/api/catalog/collections', { store_id: storeId, title: title.trim() })
      setTitle(''); load()
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Oluşturulamadı')
    } finally { setBusy(false) }
  }

  const toggle = async (c) => {
    try { await api.patch(`/api/catalog/collections/${c.id}`, { is_active: !c.is_active }); load() }
    catch { setErr('Güncellenemedi') }
  }
  const rename = async (c) => {
    const t = window.prompt('Yeni koleksiyon adı:', c.title)
    if (!t || t === c.title) return
    try { await api.patch(`/api/catalog/collections/${c.id}`, { title: t }); load() }
    catch { setErr('Yeniden adlandırılamadı') }
  }
  const remove = async (c) => {
    if (!window.confirm(`"${c.title}" silinecek (ürünler silinmez). Emin misiniz?`)) return
    try { await api.del(`/api/catalog/collections/${c.id}`); load() }
    catch { setErr('Silinemedi') }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-xl font-semibold">Koleksiyonlar</h1>
      <form onSubmit={create} className="flex gap-2">
        <input className="input flex-1" value={title} onChange={e => setTitle(e.target.value)}
          maxLength={200} placeholder="Yeni koleksiyon adı (örn: Retro, Minimal)" />
        <button disabled={busy || !title.trim()} className="btn-primary">Ekle</button>
      </form>
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="card !p-0 divide-y divide-panel-border overflow-hidden">
        {collections.map(c => (
          <div key={c.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span className="font-medium">{c.title}</span>
            <span className="text-xs text-panel-muted">/{c.slug} · {c.product_count ?? 0} ürün</span>
            <div className="ml-auto flex items-center gap-2">
              <button onClick={() => toggle(c)}
                className={`text-xs px-2 py-0.5 rounded-full ${c.is_active
                  ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                {c.is_active ? 'Aktif' : 'Pasif'}
              </button>
              <button onClick={() => rename(c)} className="text-xs text-panel-muted hover:text-panel-ink">Adlandır</button>
              <button onClick={() => remove(c)} className="text-xs text-red-400 hover:text-red-600">Sil</button>
            </div>
          </div>
        ))}
        {collections.length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">
            Henüz koleksiyon yok. Ürünleri koleksiyona, ürün detayındaki çiplerden atarsınız.
          </div>
        )}
      </div>
    </div>
  )
}
