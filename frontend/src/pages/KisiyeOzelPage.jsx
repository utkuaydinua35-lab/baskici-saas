import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, getToken } from '../lib/api'
import { useToast } from '../components/Toast'

const KALIP_TIPLERI = [
  { value: '', label: 'Belirtilmedi' },
  { value: 'siyah', label: 'Siyah' },
  { value: 'beyaz', label: 'Beyaz' },
  { value: 'parlak', label: 'Parlak' },
  { value: 'seffaf', label: 'Şeffaf' },
  { value: 'magsafe', label: 'MagSafe' },
]

const RENK_SECENEKLERI = [
  { name: 'Bordo', hex: '#800020' },
  { name: 'Fıstık Yeşil', hex: '#5C9F3F' },
  { name: 'Sarı', hex: '#F5E94E' },
  { name: 'Turuncu', hex: '#F58220' },
  { name: 'Siyah', hex: '#1A1A1A' },
  { name: 'Beyaz', hex: '#F5F5F5' },
  { name: 'Krem', hex: '#E8DBC0' },
  { name: 'Şeker Pembe', hex: '#E879BD' },
  { name: 'Toz Pembe', hex: '#F4BFD5' },
  { name: 'Haki', hex: '#4F7942' },
  { name: 'Mavi', hex: '#3DBDE0' },
  { name: 'Lacivert', hex: '#1F38C8' },
  { name: 'Lila', hex: '#B591D1' },
  { name: 'Kahverengi', hex: '#5C3317' },
  { name: 'Şeffaf', hex: 'transparent' },
  { name: 'Kırmızı', hex: '#E81515' },
  { name: 'Gri', hex: '#BCBCBC' },
]

export default function KisiyeOzelPage() {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [storesLoading, setStoresLoading] = useState(true)
  const [selectedStore, setSelectedStore] = useState('')

  const [orders, setOrders] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [stats, setStats] = useState(null)
  const [productsConfigured, setProductsConfigured] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [search, setSearch] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState('all')

  const [showProductsDialog, setShowProductsDialog] = useState(false)
  const [expanded, setExpanded] = useState(new Set())
  const [orderDetails, setOrderDetails] = useState({})

  useEffect(() => {
    let cancelled = false
    api.get('/api/stores')
      .then(s => {
        if (cancelled) return
        const list = Array.isArray(s) ? s : []
        setStores(list)
        if (list.length > 0) setSelectedStore(list[0].id)
      })
      .catch(e => !cancelled && setError(e.detail || 'Mağazalar yüklenemedi'))
      .finally(() => !cancelled && setStoresLoading(false))
    return () => { cancelled = true }
  }, [])

  const loadOrders = async () => {
    if (!selectedStore) return
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({
        store_id: selectedStore,
        page: String(page),
        per_page: '50',
      })
      if (search) params.set('search', search)
      if (statusFilter !== 'all') params.set('status', statusFilter)

      const [list, st] = await Promise.all([
        api.get(`/api/kisiye-ozel/orders?${params}`),
        api.get(`/api/kisiye-ozel/_stats?store_id=${selectedStore}`),
      ])
      setOrders(list.items || [])
      setTotal(list.total || 0)
      setProductsConfigured(list.products_configured)
      setStats(st)
    } catch (e) {
      setError(e.detail || 'Yükleme başarısız')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (selectedStore) setPage(1)
  }, [selectedStore, statusFilter])

  useEffect(() => { loadOrders() }, [selectedStore, page, statusFilter])

  useEffect(() => {
    if (!selectedStore) return
    const t = setTimeout(() => { setPage(1); loadOrders() }, 350)
    return () => clearTimeout(t)
    // eslint-disable-next-line
  }, [search])

  const toggleExpand = async (orderId) => {
    const next = new Set(expanded)
    if (next.has(orderId)) {
      next.delete(orderId)
      setExpanded(next)
      return
    }
    next.add(orderId)
    setExpanded(next)
    if (!orderDetails[orderId]) {
      try {
        const d = await api.get(`/api/kisiye-ozel/orders/${orderId}`)
        setOrderDetails(prev => ({ ...prev, [orderId]: d }))
      } catch (e) {
        setError(e.detail || 'Detay yüklenemedi')
      }
    }
  }

  const refreshOrderDetail = async (orderId) => {
    try {
      const d = await api.get(`/api/kisiye-ozel/orders/${orderId}`)
      setOrderDetails(prev => ({ ...prev, [orderId]: d }))
      loadOrders()
    } catch {}
  }

  return (
    <div className="max-w-7xl">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">✨</span>
          <div>
            <h1 className="text-2xl font-semibold text-gray-100">Kişiye Özel Tasarımlar</h1>
            <p className="text-xs text-gray-500 mt-0.5">Özel tasarım siparişleri</p>
          </div>
        </div>
      </div>

      {storesLoading && (
        <div className="card text-center py-8 text-gray-500">⏳ Yükleniyor...</div>
      )}

      {!storesLoading && stores.length === 0 && (
        <div className="card text-center py-8">
          <div className="text-3xl mb-2">🏪</div>
          <p className="text-gray-400">
            Henüz mağaza yok. Önce <a href="/stores" className="text-accent hover:underline">Mağazalar</a> sayfasına git.
          </p>
        </div>
      )}

      {!storesLoading && stores.length > 0 && (
        <>
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
              <StatCard label="Tasarım Bekliyor" value={stats.tasarim_bekliyor} color="amber" icon="⏰" />
              <StatCard label="Tasarım Hazır" value={stats.tasarim_hazir} color="emerald" icon="✓" />
              <StatCard label="Renk Bekliyor" value={stats.renk_bekliyor} color="red" icon="🎨" />
              <StatCard label="Toplam" value={stats.toplam} color="accent" icon="📊" />
            </div>
          )}

          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <div className="flex gap-2 items-center flex-wrap">
              <select
                value={selectedStore}
                onChange={e => setSelectedStore(e.target.value)}
                className="input !text-sm !py-1.5 w-full sm:w-auto sm:min-w-[180px]"
              >
                {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>

              <div className="flex gap-1 bg-brand-card border border-brand-border rounded-lg p-1">
                <TabBtn active={statusFilter === 'all'} onClick={() => setStatusFilter('all')}>
                  Tümü ({stats?.toplam || 0})
                </TabBtn>
                <TabBtn active={statusFilter === 'bekliyor'} onClick={() => setStatusFilter('bekliyor')}>
                  ● Bekliyor ({stats?.tasarim_bekliyor || 0})
                </TabBtn>
                <TabBtn active={statusFilter === 'hazir'} onClick={() => setStatusFilter('hazir')}>
                  ● Hazır ({stats?.tasarim_hazir || 0})
                </TabBtn>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setSearchOpen(o => !o)}
                className={`p-2 rounded-lg border transition-colors ${
                  searchOpen ? 'bg-accent/15 border-accent/40 text-accent' : 'bg-brand-card border-brand-border text-gray-400 hover:text-gray-200'
                }`}
                title="Ara"
              >🔍</button>
              <button onClick={() => setShowProductsDialog(true)} className="btn-secondary !text-sm flex items-center gap-1.5">
                📦 Ürünler
              </button>
              <button onClick={() => loadOrders()} className="p-2 rounded-lg border border-brand-border bg-brand-card text-gray-400 hover:text-gray-200" title="Yenile">
                ↻
              </button>
            </div>
          </div>

          {searchOpen && (
            <div className="card mb-3 !py-2">
              <input
                type="text"
                placeholder="Sipariş numarası, müşteri adı veya e-posta ara..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="input w-full !text-sm"
                autoFocus
              />
            </div>
          )}

          {!productsConfigured && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 mb-3 text-sm text-amber-300">
              <div className="font-medium">⚠ Henüz kişiye özel ürün tanımlanmadı</div>
              <p className="text-xs text-amber-300/70 mt-1">
                Hangi Shopify ürünlerinin "kişiye özel" sipariş sayılacağını belirleyin.
              </p>
              <button onClick={() => setShowProductsDialog(true)} className="mt-2 text-xs underline">
                Ürünleri Tanımla →
              </button>
            </div>
          )}

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
              {error}
            </div>
          )}

          <div className="card !p-0 overflow-hidden">
            {loading && <div className="text-gray-500 text-sm text-center py-12">Yükleniyor...</div>}

            {!loading && orders.length === 0 && productsConfigured && (
              <div className="text-center py-12 text-gray-500">
                <div className="text-3xl mb-2">✨</div>
                {search ? 'Arama sonucu yok.' : 'Bu mağazada henüz kişiye özel sipariş yok.'}
              </div>
            )}

            {!loading && orders.length > 0 && (
              <>
                <div className="bg-brand-input border-b border-brand-border px-3 py-2 grid grid-cols-12 gap-2 text-[10px] uppercase text-gray-500 font-medium items-center">
                  <div className="col-span-1"></div>
                  <div className="col-span-2">Sipariş</div>
                  <div className="col-span-3">Müşteri</div>
                  <div className="col-span-1">Ürün</div>
                  <div className="col-span-1">Durum</div>
                  <div className="col-span-1">Renkler</div>
                  <div className="col-span-2">Sipariş Tarihi</div>
                  <div className="col-span-1 text-right">İşlemler</div>
                </div>

                <div className="divide-y divide-brand-border/50">
                  {orders.map(o => (
                    <OrderRow
                      key={o.id}
                      order={o}
                      expanded={expanded.has(o.id)}
                      onToggle={() => toggleExpand(o.id)}
                      detail={orderDetails[o.id]}
                      onRefresh={() => refreshOrderDetail(o.id)}
                      storeId={selectedStore}
                    />
                  ))}
                </div>
              </>
            )}
          </div>

          {total > 50 && (
            <div className="flex justify-between items-center mt-3 text-xs text-gray-500">
              <span>Sayfa {page} / {Math.ceil(total / 50)} · {total} sipariş</span>
              <div className="flex gap-1">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="btn-secondary !text-xs disabled:opacity-30">← Önceki</button>
                <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 50)}
                  className="btn-secondary !text-xs disabled:opacity-30">Sonraki →</button>
              </div>
            </div>
          )}
        </>
      )}

      {showProductsDialog && (
        <ProductsDialog
          storeId={selectedStore}
          onClose={() => setShowProductsDialog(false)}
          onChanged={() => loadOrders()}
        />
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// OrderRow
// ═══════════════════════════════════════════════════════════

function OrderRow({ order, expanded, onToggle, detail, onRefresh, storeId }) {
  const statusBadge = order.status === 'hazir'
    ? <span className="inline-flex items-center gap-1 bg-emerald-500/15 text-emerald-300 text-[10px] px-2 py-0.5 rounded-full">● {order.hazir_qty} Hazır</span>
    : <span className="inline-flex items-center gap-1 bg-amber-500/15 text-amber-300 text-[10px] px-2 py-0.5 rounded-full">● {order.bekliyor_qty} Bekliyor</span>

  return (
    <div>
      <div
        className="px-3 py-3 grid grid-cols-12 gap-2 items-center hover:bg-brand-input/30 cursor-pointer"
        onClick={onToggle}
      >
        <div className="col-span-1 flex items-center gap-2">
          <span className="text-gray-500 text-sm">{expanded ? '▼' : '▶'}</span>
        </div>
        <div className="col-span-2">
          <span className="text-accent hover:underline font-mono text-xs">#{order.order_number}</span>
        </div>
        <div className="col-span-3 min-w-0">
          <div className="text-xs text-gray-200 truncate">{order.customer_name || '?'}</div>
          {order.customer_email && (
            <div className="text-[10px] text-gray-500 truncate">{order.customer_email}</div>
          )}
        </div>
        <div className="col-span-1 text-xs text-gray-300">{order.kisiye_ozel_count} ürün</div>
        <div className="col-span-1">{statusBadge}</div>
        <div className="col-span-1">
          {order.kilif_renkleri && order.kilif_renkleri.length > 0 ? (
            <div className="flex flex-wrap gap-0.5">
              {order.kilif_renkleri.slice(0, 3).map((r, i) => (
                <span key={i} className="text-[9px] bg-gray-700/30 text-gray-300 px-1 rounded">{r}</span>
              ))}
            </div>
          ) : (
            <span className="text-[10px] text-gray-600">—</span>
          )}
        </div>
        <div className="col-span-2 text-[11px] text-gray-400 whitespace-nowrap">
          {formatDate(order.created_at_platform)}
        </div>
        <div className="col-span-1 text-right">
          <button
            onClick={e => { e.stopPropagation(); onToggle() }}
            className={`text-[11px] px-2 py-1 rounded border ${
              expanded ? 'bg-brand-input border-brand-border text-gray-300' : 'border-brand-border text-gray-400 hover:text-gray-200'
            }`}
          >
            {expanded ? '∧ Kapat' : '∨ Aç'}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="bg-brand-card/40 border-t border-brand-border/50 px-3 py-3 space-y-2">
          {!detail && <div className="text-xs text-gray-500 text-center py-4">Yükleniyor...</div>}
          {detail && detail.line_items && (() => {
            const kisiyeItems = detail.line_items.filter(li => li.is_kisiye_ozel)
            if (kisiyeItems.length === 0) {
              return (
                <div className="text-xs text-gray-500 italic text-center py-2">
                  Bu siparişte kişiye özel ürün yok.
                </div>
              )
            }
            return kisiyeItems.map((li, idx) => (
              <LineItemCard
                key={li.id}
                item={li}
                storeId={storeId}
                productId={li.product_id}
                onRefresh={onRefresh}
                orderNumber={order.order_number}
                itemIndex={idx}
                totalKisiyeOzel={kisiyeItems.length}
              />
            ))
          })()}
        </div>
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// LineItemCard
// ═══════════════════════════════════════════════════════════

function LineItemCard({ item, storeId, productId, onRefresh, orderNumber, itemIndex, totalKisiyeOzel }) {
  const [showUpload, setShowUpload] = useState(false)
  const [savingColor, setSavingColor] = useState(false)
  const hasDesign = !!item.assigned_design

  const updateColor = async (which, value) => {
    setSavingColor(true)
    try {
      await api.patch(`/api/kisiye-ozel/line-items/${item.id}`, {
        [which]: value,
        fields_to_update: [which],
      })
      onRefresh()
    } catch (e) {
      toast.error(e.detail || 'Renk güncellenemedi')
    } finally {
      setSavingColor(false)
    }
  }

  const removeAssignedDesign = async () => {
    if (!confirm('Atanan tasarımı kaldır?')) return
    try {
      await api.patch(`/api/kisiye-ozel/line-items/${item.id}`, {
        assigned_design_id: null,
        fields_to_update: ['assigned_design_id'],
      })
      onRefresh()
    } catch (e) {
      toast.error(e.detail || 'Kaldırılamadı')
    }
  }

  return (
    <div className="bg-brand-input/40 border border-brand-border/60 rounded-lg p-3">
      <div className="grid grid-cols-12 gap-3 items-start">
        <div className="col-span-2">
          {item.customer_image_url ? (
            <a href={item.customer_image_url} target="_blank" rel="noreferrer" className="block">
              <img
                src={item.customer_image_url}
                alt=""
                className="w-full aspect-square object-cover rounded-lg border border-brand-border bg-brand-card"
                onError={e => { e.target.style.display = 'none' }}
              />
            </a>
          ) : (
            <div className="w-full aspect-square rounded-lg bg-brand-card border border-brand-border flex items-center justify-center text-gray-600">
              <span className="text-2xl">📷</span>
            </div>
          )}
        </div>

        <div className="col-span-4 min-w-0">
          <div className="text-sm text-gray-200 font-medium leading-tight">{item.title}</div>
          {item.model_info && (
            <div className="text-[11px] text-gray-400 mt-0.5">Model: {item.model_info}</div>
          )}
          {item.customer_note && (
            <div className="text-[11px] text-gray-300 mt-1.5 flex items-start gap-1">
              <span className="text-gray-500">💬</span>
              <span className="line-clamp-2">{item.customer_note}</span>
            </div>
          )}
          {item.customer_props && item.customer_props.length > 0 && (
            <div className="text-[10px] text-blue-300 mt-1 flex items-start gap-1">
              <span>📄</span>
              <span className="line-clamp-1">
                {item.customer_props.map(p => `${p.name}: ${p.value}`).join(' · ')}
              </span>
            </div>
          )}
        </div>

        <div className="col-span-1">
          {hasDesign ? (
            <span className="inline-flex items-center gap-1 bg-emerald-500/15 text-emerald-300 text-[10px] px-2 py-0.5 rounded-full">
              ● Hazır
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 bg-amber-500/15 text-amber-300 text-[10px] px-2 py-0.5 rounded-full">
              ● Bekleniyor
            </span>
          )}
        </div>

        <div className="col-span-3 space-y-1">
          <ColorRow label="Birincil" value={item.birincil_renk || ''} onChange={v => updateColor('birincil_renk', v)} disabled={savingColor} />
          <ColorRow label="İkincil" value={item.ikincil_renk || ''} onChange={v => updateColor('ikincil_renk', v)} disabled={savingColor} />
          <ColorRow label="Üçüncül" value={item.ucuncu_renk || ''} onChange={v => updateColor('ucuncu_renk', v)} disabled={savingColor} />
        </div>

        <div className="col-span-2 flex flex-col items-end gap-2">
          <div className="text-xs text-gray-400">x{item.quantity}</div>
          {hasDesign ? (
            <div className="flex flex-col items-end gap-1">
              <div className="flex items-center gap-1">
                {item.assigned_design.thumbnail_url ? (
                  <img src={item.assigned_design.thumbnail_url} alt="" className="w-8 h-8 object-cover rounded border border-emerald-500/30" />
                ) : (
                  <span className="text-emerald-400">📄</span>
                )}
                <span className="text-[10px] font-mono text-emerald-300">{item.assigned_design.code}</span>
              </div>
              <button onClick={removeAssignedDesign} className="text-[10px] text-red-400 hover:underline">Kaldır</button>
            </div>
          ) : (
            <button onClick={() => setShowUpload(true)} className="btn-primary !text-xs !py-1 !px-3 flex items-center gap-1">
              ↑ Yükle
            </button>
          )}
        </div>
      </div>

      {showUpload && (
        <LineItemUploadDialog
          lineItem={item}
          storeId={storeId}
          productId={productId}
          orderNumber={orderNumber}
          itemIndex={itemIndex}
          totalKisiyeOzel={totalKisiyeOzel}
          onClose={() => setShowUpload(false)}
          onSaved={() => { setShowUpload(false); onRefresh() }}
        />
      )}
    </div>
  )
}


function ColorRow({ label, value, onChange, disabled }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-gray-500 w-14 shrink-0">{label}:</span>
      <ColorSelect value={value} onChange={onChange} disabled={disabled} />
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// ColorSelect (portal-based)
// ═══════════════════════════════════════════════════════════

function ColorSwatch({ hex }) {
  if (hex === 'transparent') {
    return <span className="w-3 h-3 rounded-full border border-red-500 shrink-0" style={{ background: 'transparent' }} />
  }
  return <span className="w-3 h-3 rounded-full border border-white/20 shrink-0" style={{ background: hex }} />
}

function ColorSelect({ value, onChange, disabled }) {
  const btnRef = useRef(null)
  const [openRect, setOpenRect] = useState(null)
  const selected = RENK_SECENEKLERI.find(c => c.name === value)

  const handleToggle = () => {
    if (disabled) return
    if (openRect) { setOpenRect(null); return }
    if (btnRef.current) {
      const r = btnRef.current.getBoundingClientRect()
      const dropdownHeight = 256
      const spaceBelow = window.innerHeight - r.bottom
      const openUp = spaceBelow < dropdownHeight + 16 && r.top > dropdownHeight
      setOpenRect({
        top: openUp ? r.top - dropdownHeight - 4 : r.bottom + 4,
        left: r.left,
        width: Math.max(r.width, 160),
      })
    }
  }

  useEffect(() => {
    if (!openRect) return
    const close = () => setOpenRect(null)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [openRect])

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        className="flex-1 bg-brand-input border border-brand-border rounded px-2 py-1 text-[11px] text-left flex items-center gap-1.5 hover:border-gray-600 disabled:opacity-50"
      >
        {selected ? (
          <>
            <ColorSwatch hex={selected.hex} />
            <span className="truncate">{selected.name}</span>
          </>
        ) : (
          <span className="text-gray-500">Seçilmedi</span>
        )}
        <span className="ml-auto text-gray-600 text-[9px]">⌄</span>
      </button>

      {openRect && createPortal(
        <>
          <div className="fixed inset-0 z-[200]" onClick={() => setOpenRect(null)} />
          <div
            className="fixed z-[201] bg-brand-card border border-brand-border rounded-lg shadow-2xl max-h-64 overflow-y-auto"
            style={{ top: openRect.top, left: openRect.left, width: openRect.width }}
          >
            <button
              type="button"
              onClick={() => { onChange(''); setOpenRect(null) }}
              className={`w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 hover:bg-brand-input ${value === '' ? 'bg-accent/10 text-accent' : 'text-gray-300'}`}
            >
              <span className="w-3 h-3 shrink-0" />
              <span>Seçilmedi</span>
              {value === '' && <span className="ml-auto">✓</span>}
            </button>
            {RENK_SECENEKLERI.map(c => (
              <button
                key={c.name}
                type="button"
                onClick={() => { onChange(c.name); setOpenRect(null) }}
                className={`w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 hover:bg-brand-input ${value === c.name ? 'bg-accent/10 text-accent' : 'text-gray-300'}`}
              >
                <ColorSwatch hex={c.hex} />
                <span>{c.name}</span>
                {value === c.name && <span className="ml-auto">✓</span>}
              </button>
            ))}
          </div>
        </>,
        document.body
      )}
    </>
  )
}


// ═══════════════════════════════════════════════════════════
// LineItemUploadDialog
// ═══════════════════════════════════════════════════════════

function LineItemUploadDialog({ lineItem, storeId, productId, orderNumber, itemIndex, totalKisiyeOzel, onClose, onSaved }) {
  const fileInputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [filePreview, setFilePreview] = useState(null)
  const defaultCode = orderNumber
    ? (totalKisiyeOzel > 1 ? `${orderNumber}-${(itemIndex ?? 0) + 1}` : `${orderNumber}`)
    : ''
  const [code, setCode] = useState(defaultCode)
  const [name, setName] = useState('Kişiye Özel')
  const [kalipTipi, setKalipTipi] = useState('')
  const [birincil, setBirincil] = useState(lineItem.birincil_renk || '')
  const [ikincil, setIkincil] = useState(lineItem.ikincil_renk || '')
  const [ucuncu, setUcuncu] = useState(lineItem.ucuncu_renk || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    if (['image/svg+xml', 'image/png', 'image/jpeg'].includes(f.type)) {
      const reader = new FileReader()
      reader.onload = e => setFilePreview(e.target.result)
      reader.readAsDataURL(f)
    } else {
      setFilePreview(null)
    }
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!file) { setError('Dosya seçmek zorunlu'); return }
    if (!code.trim()) { setError('Tasarım kodu zorunlu'); return }

    setError('')
    setSaving(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('store_id', storeId)
      fd.append('code', code.trim())
      if (name) fd.append('name', name.trim())
      if (productId) fd.append('product_id', productId)
      if (kalipTipi) fd.append('kalip_tipi', kalipTipi)
      if (birincil) fd.append('birincil_renk', birincil)
      if (ikincil) fd.append('ikincil_renk', ikincil)
      if (ucuncu) fd.append('ucuncu_renk', ucuncu)
      fd.append('is_kisiye_ozel', 'true')
      fd.append('line_item_id', lineItem.id)

      const res = await fetch('/api/designs', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${getToken()}` },
        body: fd,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      onSaved()
    } catch (err) {
      setError(err.message || 'Kaydedilemedi')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex justify-between items-start p-5 pb-3 shrink-0 border-b border-brand-border">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Kişiye Özel Tasarım Yükle</h2>
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{lineItem.title}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>

        <div className="overflow-y-auto px-5 py-4 flex-1">
          <form onSubmit={onSubmit} className="space-y-3" id="li-upload-form">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Dosya</label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-brand-border rounded-lg p-6 text-center cursor-pointer hover:border-accent/50 transition-colors"
              >
                <input ref={fileInputRef} type="file" accept=".svg,.png,.jpg,.jpeg,.pdf"
                       onChange={e => handleFile(e.target.files?.[0])} className="hidden" />
                {file ? (
                  <div className="space-y-2">
                    {filePreview && <img src={filePreview} alt="" className="max-h-32 mx-auto rounded" />}
                    <div className="text-sm text-gray-300">{file.name}</div>
                    <div className="text-[10px] text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
                  </div>
                ) : (
                  <>
                    <div className="text-2xl mb-1">📤</div>
                    <div className="text-sm text-gray-300">Dosya seçmek için tıklayın</div>
                    <div className="text-[10px] text-gray-500 mt-1">SVG, PNG, JPG veya PDF · max 50 MB</div>
                  </>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Tasarım Kodu *</label>
                <input type="text" required value={code} onChange={e => setCode(e.target.value)}
                       className="input w-full font-mono" placeholder="Sipariş numarası" />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">İsim</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} className="input w-full" />
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">Kalıp Tipi</label>
              <select value={kalipTipi} onChange={e => setKalipTipi(e.target.value)} className="input w-full">
                {KALIP_TIPLERI.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">Renkler</label>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <span className="text-[10px] text-gray-500">🔴 Birincil</span>
                  <ColorSelect value={birincil} onChange={setBirincil} />
                </div>
                <div>
                  <span className="text-[10px] text-gray-500">🔵 İkincil</span>
                  <ColorSelect value={ikincil} onChange={setIkincil} />
                </div>
                <div>
                  <span className="text-[10px] text-gray-500">🟢 Üçüncül</span>
                  <ColorSelect value={ucuncu} onChange={setUcuncu} />
                </div>
              </div>
            </div>

            <div className="bg-accent/5 border border-accent/20 rounded-lg p-2 text-[11px] text-accent/80">
              ✨ Bu tasarım otomatik olarak <strong>kişiye özel</strong> olarak işaretlenecek ve bu sipariş kalemine bağlanacak.
            </div>

            {error && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}
          </form>
        </div>

        <div className="flex gap-2 justify-end p-5 pt-3 border-t border-brand-border shrink-0">
          <button type="button" onClick={onClose} className="btn-secondary">İptal</button>
          <button type="submit" form="li-upload-form" disabled={saving || !file} className="btn-primary">
            {saving ? 'Yükleniyor...' : 'Yükle ve Bağla'}
          </button>
        </div>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// ProductsDialog — Hangi Shopify ürünleri kişiye özel sayılsın
// ═══════════════════════════════════════════════════════════

function ProductsDialog({ storeId, onClose, onChanged }) {
  const [selected, setSelected] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showPicker, setShowPicker] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get(`/api/kisiye-ozel/products?store_id=${storeId}`)
      setSelected(r.items || [])
    } catch (e) {
      setError(e.detail || 'Yüklenemedi')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [storeId])

  const addProduct = async (p) => {
    setError('')
    try {
      await api.post('/api/kisiye-ozel/products', {
        store_id: storeId,
        product_id: p.id,
        product_title: p.title,
        product_image_url: p.image_url,
      })
      await load()
      onChanged()
    } catch (e) {
      setError(e.detail || 'Eklenemedi')
    }
  }

  const removeProduct = async (kopId) => {
    if (!confirm('Bu ürünü kişiye özel listesinden kaldır?')) return
    try {
      await api.del(`/api/kisiye-ozel/products/${kopId}`)
      await load()
      onChanged()
    } catch (e) {
      toast.error(e.detail || 'Silinemedi')
    }
  }

  const selectedIds = new Set(selected.map(s => s.product_id))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex justify-between items-start p-5 pb-3 shrink-0 border-b border-brand-border">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Kişiye Özel Ürünler</h2>
            <p className="text-xs text-gray-500 mt-1">
              Bu listede olan ürünler sipariş line item'ında geçerse o sipariş "kişiye özel" olarak işaretlenir
            </p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>

        <div className="overflow-y-auto px-5 py-4 flex-1">
          {loading && <div className="text-center text-gray-500 text-sm py-8">Yükleniyor...</div>}

          {!loading && (
            <>
              <div className="flex items-center justify-between mb-3">
                <div className="text-xs text-gray-400">
                  {selected.length} ürün işaretli
                </div>
                <button
                  onClick={() => setShowPicker(true)}
                  className="btn-primary !text-xs flex items-center gap-1"
                >+ Ürün Ekle</button>
              </div>

              {selected.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <div className="text-3xl mb-2">📦</div>
                  <p className="text-sm">Henüz kişiye özel ürün tanımlanmadı.</p>
                  <p className="text-[11px] text-gray-600 mt-1">+ Ürün Ekle ile Shopify ürünlerinden seç.</p>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {selected.map(s => (
                    <div key={s.id} className="flex items-center gap-2 bg-brand-input border border-brand-border rounded-lg p-2">
                      {s.product_image_url ? (
                        <img src={s.product_image_url} alt="" className="w-12 h-12 rounded object-cover shrink-0" />
                      ) : (
                        <div className="w-12 h-12 rounded bg-brand-card flex items-center justify-center text-gray-600 shrink-0">📦</div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-200 truncate">{s.product_title || `Ürün #${s.product_id}`}</div>
                        <div className="text-[10px] text-gray-500 font-mono">ID: {s.product_id}</div>
                      </div>
                      <button
                        onClick={() => removeProduct(s.id)}
                        className="text-xs text-red-400 hover:text-red-300 px-2"
                      >🗑</button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mt-3">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end p-5 pt-3 border-t border-brand-border shrink-0">
          <button onClick={onClose} className="btn-secondary">Kapat</button>
        </div>
      </div>

      {showPicker && (
        <ProductPicker
          storeId={storeId}
          excludeIds={selectedIds}
          onSelect={p => { addProduct(p); setShowPicker(false) }}
          onClose={() => setShowPicker(false)}
        />
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// ProductPicker — Shopify ürünlerinden seç (DesignsPage'dekiyle aynı pattern)
// ═══════════════════════════════════════════════════════════

function ProductPicker({ storeId, excludeIds, onSelect, onClose }) {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const delay = search ? 400 : 0
    const t = setTimeout(async () => {
      if (cancelled) return
      setLoading(true)
      setError('')
      try {
        const params = new URLSearchParams({ store_id: storeId })
        if (search) params.set('search', search)
        const r = await api.get(`/api/designs/_meta/products?${params}`)
        if (cancelled) return
        setProducts(r.items || [])
      } catch (e) {
        if (cancelled) return
        setError(e.detail || 'Ürünler yüklenemedi')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, delay)
    return () => { cancelled = true; clearTimeout(t) }
    // eslint-disable-next-line
  }, [search])

  const filteredProducts = products.filter(p => !excludeIds || !excludeIds.has(p.id))

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl p-4 w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-lg font-semibold text-gray-100">Ürün Seç</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>
        <input
          type="text" placeholder="Ürün ara..."
          value={search} onChange={e => setSearch(e.target.value)}
          className="input w-full !text-sm mb-3" autoFocus
        />
        {error && (
          <div className="text-xs text-red-400 bg-red-500/10 rounded p-2 mb-2">{error}</div>
        )}
        <div className="flex-1 overflow-y-auto space-y-1">
          {loading && <div className="text-center py-8 text-gray-500 text-sm">Yükleniyor...</div>}
          {!loading && filteredProducts.length === 0 && (
            <div className="text-center py-8 text-gray-500 text-sm">
              {products.length > 0 ? 'Tüm ürünler zaten ekli ✓' : 'Ürün bulunamadı'}
            </div>
          )}
          {filteredProducts.map(p => (
            <button
              key={p.id}
              onClick={() => onSelect(p)}
              className="w-full flex items-center gap-2 p-2 bg-brand-input hover:bg-brand-input/70 border border-brand-border rounded-lg text-left transition-colors"
            >
              {p.image_url ? (
                <img src={p.image_url} alt="" className="w-10 h-10 rounded object-cover shrink-0" />
              ) : (
                <div className="w-10 h-10 rounded bg-brand-card flex items-center justify-center text-gray-600 shrink-0">📦</div>
              )}
              <div className="flex-1 min-w-0">
                <div className="text-xs text-gray-200 truncate">{p.title}</div>
                <div className="text-[10px] text-gray-500 font-mono">ID: {p.id}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// Yardımcılar
// ═══════════════════════════════════════════════════════════

function formatDate(iso) {
  if (!iso) return '?'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '?'
  return d.toLocaleDateString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function StatCard({ label, value, color = 'gray', icon }) {
  const colors = {
    gray: { text: 'text-gray-200', border: 'border-l-gray-500/60', icon: 'bg-gray-500/15 text-gray-300' },
    amber: { text: 'text-amber-400', border: 'border-l-amber-500/60', icon: 'bg-amber-500/15 text-amber-300' },
    emerald: { text: 'text-emerald-400', border: 'border-l-emerald-500/60', icon: 'bg-emerald-500/15 text-emerald-300' },
    red: { text: 'text-red-400', border: 'border-l-red-500/60', icon: 'bg-red-500/15 text-red-300' },
    accent: { text: 'text-accent', border: 'border-l-accent/60', icon: 'bg-accent/15 text-accent' },
  }
  const c = colors[color]
  return (
    <div className={`bg-brand-card border border-brand-border ${c.border} border-l-4 rounded-lg p-4 flex items-center gap-3`}>
      <div className={`w-10 h-10 rounded-lg ${c.icon} flex items-center justify-center text-lg shrink-0`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[11px] text-gray-400">{label}</div>
        <div className={`text-2xl font-semibold ${c.text}`}>{value}</div>
      </div>
    </div>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
        active ? 'bg-accent/15 text-accent' : 'text-gray-400 hover:text-gray-200'
      }`}
    >{children}</button>
  )
}
