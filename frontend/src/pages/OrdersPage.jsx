import { useEffect, useState, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import ManualOrderDialog from '../components/ManualOrderDialog'

function ExportButton({ storeId }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const download = async (format) => {
    setOpen(false)
    setLoading(true)
    try {
      const params = new URLSearchParams({ format })
      if (storeId) params.set('store_id', storeId)
      const token = localStorage.getItem('baskici_token')
      const res = await fetch(`/api/orders/_export?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('İndirme hatası')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = format === 'xlsx' ? 'siparisler.xlsx' : 'siparisler.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // toast kullanamıyoruz burada, sessiz geç
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        disabled={loading}
        className="btn-secondary !text-xs disabled:opacity-50"
        title="Siparişleri dışa aktar"
      >
        {loading ? '⏳' : '📥'} İndir
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-30 bg-brand-card border border-brand-border rounded-lg shadow-xl py-1 min-w-[140px]">
          <button
            onClick={() => download('xlsx')}
            className="w-full text-left px-4 py-2 text-sm text-gray-200 hover:bg-brand-hover"
          >📊 Excel (.xlsx)</button>
          <button
            onClick={() => download('csv')}
            className="w-full text-left px-4 py-2 text-sm text-gray-200 hover:bg-brand-hover"
          >📄 CSV (.csv)</button>
        </div>
      )}
    </div>
  )
}

const STATUS_LABELS = {
  null: { label: 'Bekliyor', color: 'bg-amber-500/15 text-amber-400' },
  unfulfilled: { label: 'Hazırlanıyor', color: 'bg-amber-500/15 text-amber-400' },
  partial: { label: 'Kısmi', color: 'bg-blue-500/15 text-blue-400' },
  fulfilled: { label: 'Tamamlandı', color: 'bg-emerald-500/15 text-emerald-400' },
}

// stages.py ile aynı (toplu aşama değiştirme için)
const STAGES = [
  { no: 1, label: 'Yeni' },
  { no: 2, label: 'İşleniyor' },
  { no: 3, label: 'Barkod Oluştu' },
  { no: 4, label: 'Kalıba Alındı' },
  { no: 5, label: 'Baskıda' },
  { no: 6, label: 'Baskı Tamam' },
  { no: 7, label: 'Paketlendi' },
  { no: 8, label: 'Kargoda' },
  { no: 9, label: 'Teslim' },
]

// internal_lists etiketleri (order_detail VALID_LISTS ile aynı)
const BULK_LABELS = [
  { value: 'isaretlenenler', label: '⭐ İşaretlenenler' },
  { value: 'bugun', label: '📅 Bugün' },
  { value: 'sonra', label: '⏰ Sonra' },
  { value: 'kontrol', label: '🔍 Kontrol' },
  { value: 'baski', label: '🖨️ Baskı' },
  { value: 'export', label: '📤 Export' },
]

const TABS = [
  { key: 'tumu', label: 'Tümü', emoji: '📋' },
  { key: 'acil', label: 'Acil', emoji: '🔥', activeColor: 'text-red-300', activeBorder: 'border-red-500' },
  { key: 'barkod', label: 'Barkod', emoji: '🏷' },
  { key: 'tedarik', label: 'Tedarik', emoji: '📦' },
  { key: 'kaliplanmis', label: 'Kalıplanmış', emoji: '✓', activeColor: 'text-emerald-300', activeBorder: 'border-emerald-500' },
  { key: 'kalip_bekliyor', label: 'Kalıp Bekliyor', emoji: '🧩', activeColor: 'text-amber-300', activeBorder: 'border-amber-500' },
  { key: 'tamamlandi', label: 'Tamamlandı', emoji: '✅', activeColor: 'text-emerald-300', activeBorder: 'border-emerald-500' },
]

function moldBadge(kaliptaCount, totalLi) {
  if (!totalLi || kaliptaCount <= 0) return null
  if (kaliptaCount >= totalLi) {
    return { label: '🧩 Kalıpta', color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' }
  }
  return { label: `🧩 ${kaliptaCount}/${totalLi}`, color: 'bg-amber-500/15 text-amber-300 border-amber-500/30' }
}

function shopifyAdminUrl(store, externalId) {
  if (!externalId || !store) return null
  // Shopify store_url config içinde tutuluyor: store.config.store_url
  const domain = store?.config?.store_url || store?.shop_domain || store?.domain
  if (!domain) return null
  const clean = String(domain).replace(/^https?:\/\//, '').replace(/\/$/, '')
  return `https://${clean}/admin/orders/${externalId}`
}

export default function OrdersPage() {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [orders, setOrders] = useState([])
  const [total, setTotal] = useState(0)
  const [tabCounts, setTabCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [fetching, setFetching] = useState(null)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({
    store_id: localStorage.getItem('orders_store_id') || '',
    search: '',
    deadline: new URLSearchParams(window.location.search).get('deadline') || '',
  })
  const [tab, setTab] = useState(() => localStorage.getItem('orders_tab') || 'tumu')
  const [page, setPage] = useState(1)
  const [fetchMessage, setFetchMessage] = useState(null)
  const [expanded, setExpanded] = useState(new Set())   // expand edilmiş satır id'leri
  const [menuOrderId, setMenuOrderId] = useState(null)
  const [showManualOrder, setShowManualOrder] = useState(false)
  const [showTrash, setShowTrash] = useState(false)
  const [selected, setSelected] = useState(new Set())   // toplu işlem seçimi
  const [bulkBusy, setBulkBusy] = useState(false)
  const navigate = useNavigate()  // 3 nokta menüsü açık olan sipariş

  const loadStores = async () => {
    try {
      const s = await api.get('/api/stores')
      setStores(Array.isArray(s) ? s : [])
    } catch {}
  }

  const loadTabCounts = async () => {
    try {
      const params = new URLSearchParams()
      if (filters.store_id) params.set('store_id', filters.store_id)
      const r = await api.get(`/api/orders/_tab_counts?${params}`)
      setTabCounts(r || {})
    } catch {
      setTabCounts({})
    }
  }

  const loadOrders = async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ page, per_page: 50, tab })
      if (filters.store_id) params.set('store_id', filters.store_id)
      if (filters.search) params.set('search', filters.search)
      if (filters.deadline) params.set('deadline', filters.deadline)
      const r = await api.get(`/api/orders?${params}`)
      setOrders(r.items)
      setTotal(r.total)
    } catch (e) {
      setError(e.detail || 'Yükleme başarısız')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadStores() }, [])
  useEffect(() => { loadTabCounts() }, [filters.store_id])
  useEffect(() => { loadOrders() }, [filters.store_id, filters.deadline, tab, page])
  useEffect(() => { localStorage.setItem('orders_tab', tab) }, [tab])
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); loadOrders() }, 400)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.search])

  // Liste değişince seçimi temizle
  useEffect(() => { setSelected(new Set()) }, [tab, page, filters.store_id, filters.search, filters.deadline])

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }
  const allOnPageSelected = orders.length > 0 && orders.every(o => selected.has(o.id))
  const toggleSelectAll = () => {
    setSelected(prev => {
      if (orders.every(o => prev.has(o.id))) {
        const next = new Set(prev)
        orders.forEach(o => next.delete(o.id))
        return next
      }
      const next = new Set(prev)
      orders.forEach(o => next.add(o.id))
      return next
    })
  }

  const runBulk = async (action, value, confirmMsg) => {
    const ids = [...selected]
    if (ids.length === 0) return
    if (confirmMsg && !confirm(confirmMsg)) return
    setBulkBusy(true)
    try {
      const r = await api.post('/api/orders/_bulk', { ids, action, value })
      toast.success(`${r.affected} sipariş güncellendi`)
      setSelected(new Set())
      loadOrders()
      loadTabCounts()
    } catch (e) {
      toast.error(e.detail || 'Toplu işlem başarısız')
    } finally {
      setBulkBusy(false)
    }
  }

  const handleFetch = async (storeId) => {
    setFetching(storeId)
    setFetchMessage(null)
    try {
      const r = await api.post('/api/orders/fetch', { store_id: storeId })
      setFetchMessage({ success: r.success, message: r.message, duration: r.duration_seconds })
      loadOrders()
      loadTabCounts()
    } catch (e) {
      setFetchMessage({ success: false, message: e.detail || 'Çekme başarısız' })
    } finally {
      setFetching(null)
    }
  }

  const handleDelete = async (orderId, orderName) => {
    if (!confirm(`${orderName} silinecek. Emin misin?`)) return
    try {
      await api.del(`/api/orders/${orderId}`)
      loadOrders()
      loadTabCounts()
    } catch (e) {
      toast.error('Silme başarısız: ' + (e?.detail || ''))
    }
  }

  const storeName = (id) => stores.find(s => s.id === id)?.name || '?'
  // Bayii mağazaları /api/stores'ta gelmediği için önce order'ın store_name'i kullanılır
  const storeLabel = (o) => o.store_name || storeName(o.store_id)
  const storeOf = (id) => stores.find(s => s.id === id)

  const toggleExpand = (id) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const changeTab = (newTab) => {
    setTab(newTab)
    setPage(1)
    setExpanded(new Set())
  }

  return (
    <div className="max-w-[1400px]">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">Siparişler</h1>
          <p className="text-sm text-gray-500 mt-1">
            {tab === 'tumu' ? `Toplam ${total} sipariş` : `${total} ${TABS.find(t => t.key === tab)?.label.toLowerCase()} sipariş`}
          </p>
        </div>
        {stores.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setShowManualOrder(true)}
              className="btn-primary !text-xs"
              title="WhatsApp/telefon siparişlerini elle ekle"
            >+ Manuel Sipariş</button>
            <button
              onClick={() => setShowTrash(true)}
              className="btn-secondary !text-xs"
              title="Silinen siparişler (geri al)"
            >🗑 Çöp Kutusu</button>
            <ExportButton storeId={filters.store_id} />
            {stores.map(s => (
              <button
                key={s.id}
                onClick={() => handleFetch(s.id)}
                disabled={fetching !== null}
                className="btn-secondary !text-xs disabled:opacity-50"
                title={`${s.name} mağazasından sipariş çek`}
              >
                {fetching === s.id ? `${s.name} çekiliyor...` : `↓ ${s.name}`}
              </button>
            ))}
          </div>
        )}
      </div>

      {fetchMessage && (
        <div className={`text-sm rounded-lg px-3 py-2 mb-4 ${
          fetchMessage.success
            ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300'
            : 'bg-red-500/10 border border-red-500/20 text-red-400'
        }`}>
          {fetchMessage.success ? '✓ ' : '✗ '}{fetchMessage.message}
          {fetchMessage.duration && <span className="text-xs ml-2 opacity-70">({fetchMessage.duration}s)</span>}
        </div>
      )}

      {stores.length === 0 && (
        <div className="card text-center py-8">
          <div className="text-3xl mb-2">🏪</div>
          <p className="text-gray-400">Henüz mağaza yok. Önce <a href="/stores" className="text-accent hover:underline">Mağazalar</a> sayfasından bağlanmak gerek.</p>
        </div>
      )}

      {stores.length > 0 && (
        <>
          {/* Tab Bar */}
          <div className="border-b border-brand-border mb-4 overflow-x-auto">
            <div className="flex gap-0 min-w-fit">
              {TABS.map(t => {
                const isActive = tab === t.key
                const count = tabCounts[t.key] ?? 0
                return (
                  <button
                    key={t.key}
                    onClick={() => changeTab(t.key)}
                    className={`px-3 py-2 text-sm border-b-2 -mb-px flex items-center gap-1.5 whitespace-nowrap transition-colors ${
                      isActive
                        ? `${t.activeBorder || 'border-accent'} ${t.activeColor || 'text-accent'} font-medium`
                        : 'border-transparent text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    <span>{t.emoji}</span>
                    <span>{t.label}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ml-0.5 ${
                      isActive
                        ? 'bg-current/10'
                        : 'bg-brand-input text-gray-500'
                    }`}>{count}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Filtreler (basitleştirilmiş - tab'lar ana filtre) */}
          <div className="card mb-4 flex flex-wrap gap-2 !p-3">
            <select
              value={filters.store_id}
              onChange={e => { localStorage.setItem('orders_store_id', e.target.value); setFilters(f => ({ ...f, store_id: e.target.value })); setPage(1) }}
              className="input !text-xs !py-1.5"
            >
              <option value="">Tüm mağazalar</option>
              {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <input
              type="text"
              placeholder="Ara: sipariş no, isim, email..."
              value={filters.search}
              onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
              className="input !text-xs !py-1.5 flex-1 min-w-[200px]"
            />
            {/* Kargo sözü (SLA) hızlı filtreleri */}
            <div className="flex gap-1">
              {[
                { v: 'overdue', label: '⛔ Sözü geçen' },
                { v: 'bugun', label: '⏰ Bugün dolan' },
                { v: 'soon', label: '🚚 Yaklaşan' },
              ].map(b => (
                <button
                  key={b.v}
                  onClick={() => { setPage(1); setFilters(f => ({ ...f, deadline: f.deadline === b.v ? '' : b.v })) }}
                  className={`!text-xs px-2 py-1.5 rounded-lg border transition-colors ${
                    filters.deadline === b.v
                      ? 'bg-accent/20 text-accent border-accent/40'
                      : 'bg-brand-input text-gray-400 border-brand-border hover:text-gray-200'
                  }`}
                >{b.label}</button>
              ))}
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
              {error}
            </div>
          )}

          {loading && <div className="text-gray-500 text-sm text-center py-8">Yükleniyor...</div>}

          {!loading && orders.length === 0 && (
            <div className="card text-center py-12 text-gray-500">
              <div className="text-3xl mb-2">📦</div>
              Bu sekmede sipariş yok.
            </div>
          )}

          {!loading && orders.length > 0 && (
            <div className="card !p-0 overflow-visible">
              <div className="overflow-x-auto"><table className="w-full text-sm min-w-[640px]">
                <thead className="bg-brand-input border-b border-brand-border">
                  <tr className="text-left text-xs text-gray-500">
                    <th className="w-8 px-2 text-center">
                      <input
                        type="checkbox"
                        checked={allOnPageSelected}
                        onChange={toggleSelectAll}
                        className="accent-accent cursor-pointer"
                        title="Tümünü seç"
                      />
                    </th>
                    <th className="w-8 px-2"></th>
                    <th className="px-3 py-2 font-medium">Sipariş</th>
                    <th className="px-3 py-2 font-medium">Mağaza</th>
                    <th className="px-3 py-2 font-medium">Müşteri</th>
                    <th className="px-3 py-2 font-medium">Durum</th>
                    <th className="px-3 py-2 font-medium">Kalıba</th>
                    <th className="px-3 py-2 font-medium">Kalıp Kodları</th>
                    <th className="px-3 py-2 font-medium text-center">Ürün</th>
                    <th className="px-3 py-2 font-medium">Tarih</th>
                    <th className="w-20 px-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border/50">
                  {orders.map(o => {
                    const status = STATUS_LABELS[o.fulfillment_status ?? 'null']
                    const mold = moldBadge(o.kalipta_count || 0, o.total_li_count || o.item_count || 0)
                    const isExpanded = expanded.has(o.id)
                    const shopUrl = shopifyAdminUrl(storeOf(o.store_id), o.external_id)

                    return (
                      <>
                        <tr
                          key={o.id}
                          onClick={() => navigate(`/orders/${o.id}`)}
                          className={`hover:bg-brand-input/50 cursor-pointer ${
                            selected.has(o.id) ? 'bg-accent/5' : ''
                          } ${
                            o.is_acil ? 'border-l-2 border-l-red-500/60' : 'border-l-2 border-l-transparent'
                          }`}
                        >
                          <td className="px-2 py-2 text-center" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={selected.has(o.id)}
                              onChange={() => toggleSelect(o.id)}
                              className="accent-accent cursor-pointer"
                            />
                          </td>
                          <td className="px-2 py-2">
                            <button
                              onClick={(e) => { e.stopPropagation(); toggleExpand(o.id) }}
                              className="w-6 h-6 flex items-center justify-center text-gray-500 hover:text-gray-200 hover:bg-brand-border/50 rounded transition-colors"
                              title={isExpanded ? 'Gizle' : 'Detayları göster'}
                            >
                              {isExpanded ? '▼' : '▶'}
                            </button>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono text-accent">{o.name || `#${o.order_number}`}</span>
                              {o.is_acil && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-300 border border-red-500/30">🔥 Acil</span>}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-gray-400">{storeLabel(o)}</td>
                          <td className="px-3 py-2 text-gray-300 truncate max-w-[160px]">{o.customer_name || '—'}</td>
                          <td className="px-3 py-2">
                            <div className="flex flex-col gap-1 items-start">
                              <span className={`text-[10px] px-2 py-0.5 rounded-full ${status.color}`}>
                                {status.label}
                              </span>
                              <KargoBadge o={o} />
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            {mold ? (
                              <span className={`text-[10px] px-2 py-0.5 rounded-full border ${mold.color}`}>
                                {mold.label}
                              </span>
                            ) : (
                              <span className="text-[10px] text-gray-600">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            {o.molds?.length ? (
                              <div className="flex flex-wrap gap-1">
                                {o.molds.slice(0, 3).map(m => (
                                  <button key={m.id}
                                    onClick={(e) => { e.stopPropagation(); navigate(`/kalip/${m.id}`) }}
                                    title={`${m.kod} kalıbını aç`}
                                    className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20 hover:bg-purple-500/20 transition-colors">
                                    {m.kod}
                                  </button>
                                ))}
                                {o.molds.length > 3 && (
                                  <span className="text-[10px] text-gray-500">+{o.molds.length - 3}</span>
                                )}
                              </div>
                            ) : (
                              <span className="text-[10px] text-gray-600">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-center text-gray-400">{o.item_count}</td>
                          <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
                            <div>{o.created_at_platform ? new Date(o.created_at_platform).toLocaleDateString('tr-TR') : '—'}</div>
                            <DeadlineBadge order={o} />
                          </td>
                          <td className="px-2 py-2">
                            <div className="flex items-center gap-1 justify-end">
                              {shopUrl && (
                                <a
                                  href={shopUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="w-7 h-7 flex items-center justify-center text-gray-500 hover:text-emerald-300 hover:bg-emerald-500/10 rounded transition-colors"
                                  title="Shopify panelinde aç"
                                >
                                  ↗
                                </a>
                              )}
                              <RowMenu
                                open={menuOrderId === o.id}
                                onToggle={() => setMenuOrderId(menuOrderId === o.id ? null : o.id)}
                                onOpenDetail={() => { navigate(`/orders/${o.id}`); setMenuOrderId(null) }}
                                onOpenShopify={shopUrl ? () => { window.open(shopUrl, '_blank'); setMenuOrderId(null) } : null}
                                onDelete={() => { setMenuOrderId(null); handleDelete(o.id, o.name || `#${o.order_number}`) }}
                              />
                            </div>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="bg-brand-input/30">
                            <td></td>
                            <td colSpan={10} className="px-3 py-3">
                              <ExpandedRow orderId={o.id} />
                            </td>
                          </tr>
                        )}
                      </>
                    )
                  })}
                </tbody>
              </table></div>

              {total > 50 && (
                <div className="flex items-center justify-between px-3 py-2 border-t border-brand-border bg-brand-input/30 text-xs">
                  <span className="text-gray-500">
                    Sayfa {page} / {Math.ceil(total / 50)} · Toplam {total}
                  </span>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="btn-secondary !text-xs !py-1 !px-2 disabled:opacity-30"
                    >← Önceki</button>
                    <button
                      onClick={() => setPage(p => p + 1)}
                      disabled={page >= Math.ceil(total / 50)}
                      className="btn-secondary !text-xs !py-1 !px-2 disabled:opacity-30"
                    >Sonraki →</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Drawer */}
    
      <ManualOrderDialog
        open={showManualOrder}
        stores={stores}
        defaultStoreId={filters.store_id || stores[0]?.id}
        onClose={() => setShowManualOrder(false)}
        onCreated={(r) => {
          setShowManualOrder(false)
          loadOrders()
          loadTabCounts()
        }}
      />

      {showTrash && (
        <TrashDialog
          onClose={() => setShowTrash(false)}
          onRestored={() => { loadOrders(); loadTabCounts() }}
        />
      )}

      {selected.size > 0 && (
        <BulkBar
          count={selected.size}
          busy={bulkBusy}
          onClear={() => setSelected(new Set())}
          onStage={(no) => runBulk('stage', no)}
          onAcil={(v) => runBulk(v ? 'acil' : 'acil_kaldir')}
          onLabel={(action, val) => runBulk(action, val)}
          onDelete={() => runBulk('delete', null, `${selected.size} sipariş çöp kutusuna taşınacak. Emin misin?`)}
        />
      )}
</div>
  )
}

const KARGO_STATUS = {
  NEW: ['Hazırlanıyor', 'bg-gray-500/15 text-gray-300'],
  READY_TO_SHIP: ['Kargoya hazır', 'bg-gray-500/15 text-gray-300'],
  SHIPPED: ['Kargoda', 'bg-blue-500/15 text-blue-300'],
  OUT_FOR_DELIVERY: ['Dağıtımda', 'bg-blue-500/15 text-blue-300'],
  DELIVERED: ['Teslim edildi', 'bg-emerald-500/15 text-emerald-300'],
  NEEDS_SUPPORT: ['Destek gerek', 'bg-red-500/15 text-red-300'],
  DELAYED: ['Gecikti', 'bg-amber-500/15 text-amber-300'],
  RETURNING: ['İade ediliyor', 'bg-amber-500/15 text-amber-300'],
  RETURNED: ['İade edildi', 'bg-red-500/15 text-red-300'],
  LOST: ['Kayıp', 'bg-red-500/15 text-red-300'],
}

function KargoBadge({ o }) {
  if (!o?.kargo_status) return null
  const [label, color] = KARGO_STATUS[o.kargo_status] || [o.kargo_status, 'bg-gray-500/15 text-gray-300']
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full ${color}`}
      title={`${o.kargo_firma || 'Kargo'}${o.kargo_takip ? ' · ' + o.kargo_takip : ''}`}>
      🚚 {label}
    </span>
  )
}

function DeadlineBadge({ order }) {
  if (!order.kargo_deadline) return null
  // Kapanmış sipariş (Shopify'da kargolanmış/iade/iptal) ya da pipeline'da
  // kargolanmış (stage >= 8) ise uyarı gösterme
  if ((order.current_stage || 1) >= 8) return null
  if (order.fulfillment_status === 'fulfilled') return null
  if (order.cancelled_at) return null

  const dl = new Date(order.kargo_deadline)
  const now = new Date()
  const msLeft = dl - now
  const dayMs = 24 * 60 * 60 * 1000
  const daysLeft = Math.ceil(msLeft / dayMs)

  let cls, text
  if (msLeft < 0) {
    cls = 'bg-red-500/20 text-red-300 border-red-500/40'
    text = `⛔ ${Math.abs(daysLeft)} gün gecikti`
  } else if (daysLeft <= 0) {
    cls = 'bg-red-500/15 text-red-300 border-red-500/30'
    text = '⏰ Bugün son'
  } else if (daysLeft <= 1) {
    cls = 'bg-amber-500/15 text-amber-300 border-amber-500/30'
    text = '⏰ Yarın son'
  } else if (daysLeft <= 2) {
    cls = 'bg-amber-500/10 text-amber-300/90 border-amber-500/20'
    text = `🚚 ${daysLeft} gün`
  } else {
    cls = 'bg-brand-input text-gray-500 border-brand-border'
    text = `🚚 ${daysLeft} gün`
  }

  return (
    <span className={`inline-block mt-0.5 text-[9px] px-1.5 py-0.5 rounded-full border ${cls}`}
      title={`Kargo sözü: ${dl.toLocaleDateString('tr-TR')}`}>
      {text}
    </span>
  )
}

function BulkBar({ count, busy, onClear, onStage, onAcil, onLabel, onDelete }) {
  const [menu, setMenu] = useState(null)   // 'stage' | 'label' | null
  const ref = useRef(null)

  useEffect(() => {
    if (!menu) return
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setMenu(null) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [menu])

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[85] w-[95%] max-w-3xl animate-fadein" ref={ref}>
      <div className="bg-brand-card border border-brand-border rounded-xl shadow-2xl px-3 py-2.5 flex items-center gap-2 flex-wrap">
        <span className="text-sm text-gray-200 font-medium px-1">
          <span className="text-accent">{count}</span> seçili
        </span>
        <div className="h-5 w-px bg-brand-border mx-1" />

        {/* Aşama */}
        <div className="relative">
          <button
            onClick={() => setMenu(m => m === 'stage' ? null : 'stage')}
            disabled={busy}
            className="btn-secondary !text-xs disabled:opacity-50"
          >🔄 Aşama ▾</button>
          {menu === 'stage' && (
            <div className="absolute bottom-full mb-1 left-0 bg-brand-card border border-brand-border rounded-lg shadow-xl py-1 min-w-[160px] max-h-64 overflow-y-auto z-10">
              {STAGES.map(s => (
                <button key={s.no} onClick={() => { setMenu(null); onStage(s.no) }}
                  className="w-full text-left px-3 py-1.5 text-xs text-gray-200 hover:bg-brand-input">
                  {s.no}. {s.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Acil */}
        <button onClick={() => onAcil(true)} disabled={busy}
          className="btn-secondary !text-xs disabled:opacity-50">🔥 Acil</button>
        <button onClick={() => onAcil(false)} disabled={busy}
          className="btn-secondary !text-xs disabled:opacity-50">Acil Kaldır</button>

        {/* Etiket */}
        <div className="relative">
          <button
            onClick={() => setMenu(m => m === 'label' ? null : 'label')}
            disabled={busy}
            className="btn-secondary !text-xs disabled:opacity-50"
          >🏷️ Etiket ▾</button>
          {menu === 'label' && (
            <div className="absolute bottom-full mb-1 left-0 bg-brand-card border border-brand-border rounded-lg shadow-xl py-1 min-w-[180px] z-10">
              {BULK_LABELS.map(l => (
                <div key={l.value} className="flex items-center justify-between px-1">
                  <button onClick={() => { setMenu(null); onLabel('list_add', l.value) }}
                    className="flex-1 text-left px-2 py-1.5 text-xs text-gray-200 hover:bg-brand-input rounded">
                    {l.label}
                  </button>
                  <button onClick={() => { setMenu(null); onLabel('list_remove', l.value) }}
                    title="Etiketi kaldır"
                    className="px-2 py-1.5 text-xs text-gray-500 hover:text-red-400">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sil */}
        <button onClick={onDelete} disabled={busy}
          className="!text-xs px-3 py-1.5 rounded-lg bg-red-500/15 text-red-300 border border-red-500/30 hover:bg-red-500/25 disabled:opacity-50">
          🗑 Sil
        </button>

        <div className="flex-1" />
        <button onClick={onClear} className="text-gray-500 hover:text-gray-300 text-sm px-2">✕ Temizle</button>
      </div>
    </div>
  )
}

function TrashDialog({ onClose, onRestored }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)

  const load = async () => {
    setLoading(true)
    try { const r = await api.get('/api/orders/_trash'); setItems(r.items || []) }
    catch { setItems([]) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const restore = async (id) => {
    setBusy(id)
    try { await api.post(`/api/orders/${id}/restore`); setItems(prev => prev.filter(o => o.id !== id)); onRestored?.() }
    catch (e) { alert(e?.detail || e?.message || 'Geri alma başarısız') }
    finally { setBusy(null) }
  }

  const fmt = (iso) => { try { return new Date(iso).toLocaleString('tr-TR') } catch { return '' } }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-0 sm:p-4" onClick={onClose}>
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-brand-border bg-brand-card p-4 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-100">🗑 Çöp Kutusu — Silinen Siparişler</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 w-7 h-7 rounded-lg hover:bg-brand-input">✕</button>
        </div>
        {loading ? (
          <div className="text-sm text-gray-500 py-10 text-center">Yükleniyor...</div>
        ) : items.length === 0 ? (
          <div className="text-sm text-gray-500 py-10 text-center">Çöp kutusu boş.</div>
        ) : (
          <div className="space-y-1.5">
            {items.map(o => (
              <div key={o.id} className="flex items-center justify-between gap-3 rounded-lg border border-brand-border bg-brand-input/40 px-3 py-2">
                <div className="min-w-0">
                  <div className="text-sm text-gray-200">{o.order_number} <span className="text-gray-400">{o.customer_name || ''}</span></div>
                  <div className="text-[11px] text-gray-500">Silindi: {fmt(o.deleted_at)}</div>
                </div>
                <button onClick={() => restore(o.id)} disabled={busy === o.id}
                  className="shrink-0 text-xs px-3 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-50 transition-all font-medium">
                  {busy === o.id ? '...' : '↩ Geri Al'}</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function RowMenu({ open, onToggle, onOpenDetail, onOpenShopify, onDelete }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        onToggle()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open, onToggle])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={(e) => { e.stopPropagation(); onToggle() }}
        className="w-7 h-7 flex items-center justify-center text-gray-500 hover:text-gray-200 hover:bg-brand-border/50 rounded transition-colors"
        title="Daha fazla"
      >⋮</button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 w-48 bg-brand-card border border-brand-border rounded-lg shadow-2xl z-50 py-1"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={onOpenDetail}
            className="w-full px-3 py-1.5 text-left text-sm text-gray-300 hover:bg-brand-input flex items-center gap-2"
          >
            📋 Detayı Aç
          </button>
          {onOpenShopify && (
            <button
              onClick={onOpenShopify}
              className="w-full px-3 py-1.5 text-left text-sm text-gray-300 hover:bg-brand-input flex items-center gap-2"
            >
              ↗ Shopify'da Aç
            </button>
          )}
          <div className="border-t border-brand-border my-1" />
          <button
            onClick={onDelete}
            className="w-full px-3 py-1.5 text-left text-sm text-red-300 hover:bg-red-500/10 flex items-center gap-2"
          >
            🗑 Sipariş Sil
          </button>
        </div>
      )}
    </div>
  )
}

function ExpandedRow({ orderId }) {
  const [order, setOrder] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.get(`/api/orders/${orderId}`)
      .then(setOrder)
      .finally(() => setLoading(false))
  }, [orderId])

  if (loading) return <div className="text-xs text-gray-500">Yükleniyor...</div>
  if (!order) return <div className="text-xs text-gray-500">Veri yok</div>

  return (
    <div className="space-y-2">
      <div className="text-[11px] text-gray-500 mb-2">
        Ürünler ({order.line_items?.length || 0})
      </div>
      {(order.line_items || []).map(li => (
        <div key={li.id} className={`p-2 rounded border text-xs ${
          li.is_kaliba_eklendi
            ? 'bg-emerald-500/5 border-emerald-500/30'
            : 'bg-brand-card border-brand-border'
        }`}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="text-gray-200 truncate">{li.title}</div>
              {li.variant_title && <div className="text-[11px] text-gray-500 mt-0.5">{li.variant_title}</div>}
            </div>
            <div className="flex items-center gap-1 flex-wrap shrink-0">
              {li.is_kaliba_eklendi && (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  🧩 Kalıpta
                </span>
              )}
              {!li.is_hazir && (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
                  🏷 Barkod ❌
                </span>
              )}
              {li.tedarik_status === 'bekliyor' && (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/15 text-blue-300 border border-blue-500/30">
                  📦 Tedarik
                </span>
              )}
              <span className="text-gray-400 text-[11px]">x{li.quantity}</span>
            </div>
          </div>
          {li.properties?.length > 0 && (
            <div className="mt-1.5 pt-1.5 border-t border-brand-border/30 grid grid-cols-2 gap-x-3 gap-y-0.5">
              {li.properties.map((p, i) => (
                <div key={i} className="text-[10px] text-gray-500 truncate">
                  <span className="text-gray-600">{p.name}:</span> <span className="text-gray-400">{p.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function OrderDetailDrawer({ orderId, onClose }) {
  const [order, setOrder] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/api/orders/${orderId}`)
      .then(setOrder)
      .finally(() => setLoading(false))
  }, [orderId])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border-l border-brand-border w-full max-w-2xl h-full overflow-y-auto">
        <div className="sticky top-0 bg-brand-card border-b border-brand-border px-5 py-3 flex items-center justify-between z-10">
          <div className="flex-1 min-w-0">
            {order && (
              <>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-semibold text-gray-100">{order.name}</h2>
                  {order.is_acil && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-300 border border-red-500/30">
                      🔥 Acil
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{order.customer_name}</p>
              </>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none px-2">×</button>
        </div>
        <div className="p-5">
          {loading && <div className="text-gray-500 text-sm">Yükleniyor...</div>}
          {order && (
            <>
              <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
                <Field label="Durum" value={order.fulfillment_status || 'bekliyor'} />
                <Field label="Ödeme" value={order.financial_status || '—'} />
                <Field label="Email" value={order.customer_email || '—'} />
                <Field label="Tarih" value={order.created_at_platform ? new Date(order.created_at_platform).toLocaleString('tr-TR') : '—'} />
              </div>

              {order.mold_kodlari?.length > 0 && (
                <div className="mb-4 p-2 rounded-lg bg-purple-500/5 border border-purple-500/20">
                  <div className="text-[10px] uppercase text-purple-300 mb-1">Bağlı Kalıplar</div>
                  <div className="flex flex-wrap gap-1">
                    {order.mold_kodlari.map(k => (
                      <span key={k} className="text-[11px] px-2 py-0.5 rounded font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30">
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {order.note && (
                <div className="mb-4 p-2 rounded-lg bg-amber-500/5 border border-amber-500/15 text-xs text-amber-300">
                  <div className="text-[10px] uppercase opacity-70 mb-1">Sipariş notu</div>
                  {order.note}
                </div>
              )}

              <div className="mb-4">
                <h3 className="text-sm font-semibold text-gray-200 mb-2">Ürünler ({order.line_items.length})</h3>
                <div className="space-y-2">
                  {order.line_items.map(li => (
                    <div key={li.id} className={`p-2 rounded-lg border text-xs ${
                      li.is_kaliba_eklendi
                        ? 'bg-emerald-500/5 border-emerald-500/30'
                        : 'bg-brand-input border-brand-border'
                    }`}>
                      <div className="flex justify-between gap-2 items-start">
                        <div className="font-medium text-gray-200 flex-1">{li.title}</div>
                        <div className="flex items-center gap-1 shrink-0 flex-wrap">
                          {li.is_kaliba_eklendi && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                              🧩 Kalıba eklendi
                            </span>
                          )}
                          <span className="text-gray-400">x{li.quantity}</span>
                        </div>
                      </div>
                      {li.variant_title && <div className="text-gray-500 mt-0.5">{li.variant_title}</div>}
                      {li.sku && <div className="text-[10px] text-gray-600 mt-1 font-mono">SKU: {li.sku}</div>}
                      {li.properties.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-brand-border/50 space-y-0.5">
                          {li.properties.map((p, i) => (
                            <div key={i} className="text-[11px] text-gray-400">
                              <span className="text-gray-500">{p.name}:</span> {p.value}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <div className="text-[10px] uppercase text-gray-500 mb-0.5">{label}</div>
      <div className="text-gray-300">{value}</div>
    </div>
  )
}
