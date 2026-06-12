import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import AskiItemDialog from '../components/AskiItemDialog'

export default function AskiPage() {
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [totalQty, setTotalQty] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [checking, setChecking] = useState(false)
  const [msg, setMsg] = useState(null)

  const loadStores = async () => {
    try {
      const s = await api.get('/api/stores')
      const list = Array.isArray(s) ? s : []
      setStores(list)
      if (list.length && !storeId) setStoreId(list[0].id)
    } catch {}
  }

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (storeId) params.set('store_id', storeId)
      if (search) params.set('search', search)
      const r = await api.get(`/api/aski?${params}`)
      setItems(r.items || [])
      setTotal(r.total || 0)
      setTotalQty(r.total_quantity || 0)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadStores() }, [])
  useEffect(() => { if (storeId) load() }, [storeId])
  useEffect(() => {
    const t = setTimeout(load, 400)
    return () => clearTimeout(t)
    // eslint-disable-next-line
  }, [search])

  const handleDelete = async (id, code) => {
    if (!confirm(`Bu askı kaydı silinecek (${code || 'kayıt'}). Emin misin?`)) return
    try {
      await api.del(`/api/aski/${id}`)
      load()
    } catch (e) {
      alert(typeof e?.detail === 'string' ? e.detail : 'Silme başarısız')
    }
  }

  const handleCheck = async () => {
    setChecking(true); setMsg(null)
    try {
      const r = await api.post(`/api/aski/check-orders${storeId ? `?store_id=${storeId}` : ''}`, {})
      setMsg({ ok: true, text: r.message })
      load()
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Kontrol başarısız' })
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="max-w-[1400px]">
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🎁 Askıda Bekleyenler</h1>
          <p className="text-sm text-gray-500 mt-1">
            Hatalı üretilip stokta bekleyen ürünler. Yeni siparişlerde otomatik eşleşir, üretim atlanır.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleCheck}
            disabled={checking || !storeId}
            className="btn-secondary !text-sm disabled:opacity-50"
            title="Tüm açık siparişlerin line item'larını askı stokuyla eşleştir"
          >
            {checking ? '🔄 Kontrol ediliyor...' : '🔄 Açık Siparişleri Kontrol Et'}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            disabled={!storeId}
            className="btn-primary !text-sm disabled:opacity-50"
          >+ Yeni Askıya Ekle</button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Kpi label="TOPLAM KAYIT" value={total} color="gray" />
        <Kpi label="TOPLAM ADET" value={totalQty} color="accent" />
      </div>

      <div className="card mb-4 flex flex-wrap gap-2 !p-3">
        <select
          value={storeId}
          onChange={e => setStoreId(e.target.value)}
          className="input !text-xs !py-1.5"
        >
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <input
          type="text"
          placeholder="Ara: tasarım kodu, model, not..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="input !text-xs !py-1.5 flex-1 min-w-[200px]"
        />
      </div>

      {msg && (
        <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${
          msg.ok
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
            : 'bg-red-500/10 border-red-500/20 text-red-300'
        }`}>{msg.ok ? '✓ ' : '✗ '}{msg.text}</div>
      )}

      {loading && <div className="text-gray-500 text-sm text-center py-8">Yükleniyor...</div>}

      {!loading && items.length === 0 && (
        <div className="card text-center py-12 text-gray-500">
          <div className="text-3xl mb-2">🎁</div>
          Henüz askıda ürün yok. <br/>
          <span className="text-xs">Hatalı üretilen ama yeniden kullanılabilecek ürünleri burada tutarsın.</span>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="card !p-0 overflow-hidden">
          <div className="overflow-x-auto"><table className="w-full text-sm min-w-[640px]">
            <thead className="bg-brand-input border-b border-brand-border">
              <tr className="text-left text-xs text-gray-500">
                <th className="px-3 py-2 font-medium">Tasarım</th>
                <th className="px-3 py-2 font-medium">Model</th>
                <th className="px-3 py-2 font-medium">Varyasyon</th>
                <th className="px-3 py-2 font-medium text-center">Adet</th>
                <th className="px-3 py-2 font-medium">Not</th>
                <th className="px-3 py-2 font-medium">Eklendi</th>
                <th className="w-20 px-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border/50">
              {items.map(it => (
                <tr key={it.id} className={`hover:bg-brand-input/30 ${it.quantity === 0 ? 'opacity-50' : ''}`}>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      {it.design_thumbnail_url && (
                        <img src={it.design_thumbnail_url} alt="" className="w-8 h-8 rounded object-cover"
                             onError={e => { e.target.style.display = 'none' }} />
                      )}
                      <div className="min-w-0">
                        <div className="font-mono text-xs text-accent">{it.design_code || '?'}</div>
                        {it.design_name && (
                          <div className="text-[11px] text-gray-500 truncate max-w-[160px]">{it.design_name}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-gray-200">📱 {it.model}</td>
                  <td className="px-3 py-2">
                    {it.variation ? (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-700 text-gray-200 border border-gray-600">
                        {it.variation}
                      </span>
                    ) : <span className="text-[10px] text-gray-600">—</span>}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={`font-semibold ${it.quantity === 0 ? 'text-gray-500' : 'text-accent'}`}>
                      {it.quantity}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-400 max-w-[200px] truncate" title={it.note || ''}>
                    {it.note || '—'}
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
                    {it.created_at ? new Date(it.created_at).toLocaleDateString('tr-TR') : '—'}
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => setEditItem(it)}
                        className="w-7 h-7 flex items-center justify-center text-gray-500 hover:text-accent hover:bg-accent/10 rounded transition-colors"
                        title="Düzenle"
                      >✎</button>
                      <button
                        onClick={() => handleDelete(it.id, it.design_code)}
                        className="w-7 h-7 flex items-center justify-center text-red-400/70 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"
                        title="Sil"
                      >🗑</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}

      <AskiItemDialog
        open={showAdd}
        mode="create"
        storeId={storeId}
        stores={stores}
        onClose={() => setShowAdd(false)}
        onSaved={() => { setShowAdd(false); load() }}
      />

      <AskiItemDialog
        open={!!editItem}
        mode="edit"
        item={editItem}
        storeId={editItem?.store_id}
        stores={stores}
        onClose={() => setEditItem(null)}
        onSaved={() => { setEditItem(null); load() }}
      />
    </div>
  )
}

function Kpi({ label, value, color = 'gray' }) {
  const colors = { gray: 'text-gray-100', accent: 'text-accent' }
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-3">
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold ${colors[color]}`}>{value}</div>
    </div>
  )
}
