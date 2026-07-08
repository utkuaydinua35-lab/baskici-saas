import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

// action -> renk/ikon
const ACTION_STYLE = {
  stage_change: { icon: '🔄', color: 'bg-blue-500/15 text-blue-300' },
  acil: { icon: '🚨', color: 'bg-red-500/15 text-red-300' },
  acil_kaldir: { icon: '✓', color: 'bg-gray-500/15 text-gray-300' },
  iptal: { icon: '⊘', color: 'bg-red-500/15 text-red-300' },
  iptal_geri: { icon: '↩', color: 'bg-gray-500/15 text-gray-300' },
  hatali_gonderildi: { icon: '⚠', color: 'bg-amber-500/15 text-amber-300' },
  tedarik_bekle: { icon: '⏸', color: 'bg-amber-500/15 text-amber-300' },
  tedarik_devam: { icon: '▶', color: 'bg-gray-500/15 text-gray-300' },
  list_add: { icon: '➕', color: 'bg-emerald-500/15 text-emerald-300' },
  list_remove: { icon: '➖', color: 'bg-gray-500/15 text-gray-300' },
  paketlendi: { icon: '🏷️', color: 'bg-blue-500/15 text-blue-300' },
  kargoya_verildi: { icon: '🚚', color: 'bg-emerald-500/15 text-emerald-300' },
  askidan_karsilandi: { icon: '🎁', color: 'bg-emerald-500/15 text-emerald-300' },
}

function styleFor(action) {
  return ACTION_STYLE[action] || { icon: '•', color: 'bg-gray-500/15 text-gray-300' }
}

function fmtTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('tr-TR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Istanbul',
    })
  } catch { return iso }
}

function detailText(h) {
  if (h.action === 'stage_change') {
    return `${h.from_label || '?'} → ${h.to_label || '?'}`
  }
  if (h.note) return h.note
  return ''
}

export default function AuditPage() {
  const navigate = useNavigate()
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 1 })
  const [loading, setLoading] = useState(true)
  const [meta, setMeta] = useState({ actions: [], users: [] })
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({
    order_number: '', created_by: '', action: '', date_from: '', date_to: '',
  })
  const [searchInput, setSearchInput] = useState('')

  useEffect(() => {
    api.get('/api/audit/_meta').then(setMeta).catch(() => {})
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '50' })
      Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v) })
      const r = await api.get(`/api/audit?${params}`)
      setData(r)
    } catch {
      setData({ items: [], total: 0, page: 1, pages: 1 })
    } finally {
      setLoading(false)
    }
  }, [page, filters])

  useEffect(() => { load() }, [load])

  const applySearch = () => {
    setPage(1)
    setFilters(f => ({ ...f, order_number: searchInput.trim() }))
  }

  const setFilter = (key, value) => {
    setPage(1)
    setFilters(f => ({ ...f, [key]: value }))
  }

  const clearFilters = () => {
    setPage(1)
    setSearchInput('')
    setFilters({ order_number: '', created_by: '', action: '', date_from: '', date_to: '' })
  }

  const hasFilters = Object.values(filters).some(Boolean)

  return (
    <div className="mx-auto max-w-[1200px]">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">📜 Denetim Kaydı</h1>
        <p className="text-sm text-gray-500 mt-1">
          Sipariş üzerinde kim, ne zaman, hangi değişikliği yaptı — {data.total} kayıt
        </p>
      </div>

      {/* Filtreler */}
      <div className="card mb-4">
        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex-1 min-w-[160px]">
            <label className="text-[11px] text-gray-500 block mb-1">Sipariş No</label>
            <div className="flex gap-1">
              <input
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && applySearch()}
                placeholder="#1234"
                className="input !text-sm flex-1"
              />
              <button onClick={applySearch} className="btn-secondary !text-xs px-3">Ara</button>
            </div>
          </div>

          <div className="min-w-[140px]">
            <label className="text-[11px] text-gray-500 block mb-1">Kullanıcı</label>
            <select value={filters.created_by} onChange={e => setFilter('created_by', e.target.value)} className="input !text-sm w-full">
              <option value="">Tümü</option>
              {meta.users.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>

          <div className="min-w-[150px]">
            <label className="text-[11px] text-gray-500 block mb-1">Eylem</label>
            <select value={filters.action} onChange={e => setFilter('action', e.target.value)} className="input !text-sm w-full">
              <option value="">Tümü</option>
              {meta.actions.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </div>

          <div className="min-w-[130px]">
            <label className="text-[11px] text-gray-500 block mb-1">Başlangıç</label>
            <input type="date" value={filters.date_from} onChange={e => setFilter('date_from', e.target.value)} className="input !text-sm w-full" />
          </div>

          <div className="min-w-[130px]">
            <label className="text-[11px] text-gray-500 block mb-1">Bitiş</label>
            <input type="date" value={filters.date_to} onChange={e => setFilter('date_to', e.target.value)} className="input !text-sm w-full" />
          </div>

          {hasFilters && (
            <button onClick={clearFilters} className="btn-secondary !text-xs">✕ Temizle</button>
          )}
        </div>
      </div>

      {/* Tablo */}
      <div className="card !p-0 overflow-hidden">
        {loading ? (
          <div className="p-8 space-y-2">
            {[0, 1, 2, 3, 4].map(i => <div key={i} className="skeleton h-10 w-full rounded" />)}
          </div>
        ) : data.items.length === 0 ? (
          <div className="p-12 text-center text-gray-500">
            <div className="text-3xl mb-2">📭</div>
            <p className="text-sm">{hasFilters ? 'Filtreye uyan kayıt yok' : 'Henüz denetim kaydı yok'}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl text-sm">
              <thead>
                <tr>
                  <th>Tarih</th>
                  <th>Sipariş</th>
                  <th>Eylem</th>
                  <th>Detay</th>
                  <th>Kullanıcı</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map(h => {
                  const s = styleFor(h.action)
                  return (
                    <tr key={h.id}>
                      <td className="text-gray-400 whitespace-nowrap text-xs">{fmtTime(h.created_at)}</td>
                      <td>
                        <button
                          onClick={() => navigate(`/orders/${h.order_id}`, { state: { from: '/denetim' } })}
                          className="text-accent hover:underline font-medium"
                        >
                          {h.order_number || '—'}
                        </button>
                      </td>
                      <td>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] ${s.color}`}>
                          <span>{s.icon}</span>
                          <span>{h.action_label}</span>
                        </span>
                      </td>
                      <td className="text-gray-300 text-xs max-w-[280px] truncate">{detailText(h)}</td>
                      <td className="text-gray-400 text-xs whitespace-nowrap">{h.created_by || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Sayfalama */}
      {data.pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-gray-500">Sayfa {data.page} / {data.pages}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="btn-secondary !text-xs disabled:opacity-40"
            >← Önceki</button>
            <button
              onClick={() => setPage(p => Math.min(data.pages, p + 1))}
              disabled={page >= data.pages}
              className="btn-secondary !text-xs disabled:opacity-40"
            >Sonraki →</button>
          </div>
        </div>
      )}
    </div>
  )
}
