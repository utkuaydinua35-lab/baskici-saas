import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

const PRINT_STATUSES = [
  { value: 'bekliyor', label: 'Bekliyor', icon: '⏳', cls: 'text-amber-300 bg-amber-500/10 border-amber-500/30' },
  { value: 'basildi', label: 'Basıldı', icon: '✓', cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30' },
  { value: 'eksik_var', label: 'Eksik Var', icon: '⚠️', cls: 'text-red-300 bg-red-500/10 border-red-500/30' },
  { value: 'hatali_basildi', label: 'Hatalı Basıldı', icon: '✕', cls: 'text-rose-400 bg-rose-500/10 border-rose-500/30' },
]
const STATUS_MAP = Object.fromEntries(PRINT_STATUSES.map(s => [s.value, s]))

export default function BaskiciPaneliPage() {
  const toast = useToast()
  const [molds, setMolds] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [analyzing, setAnalyzing] = useState({})    // { moldId: true }
  const [busyStatus, setBusyStatus] = useState({})

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/molds')
      setMolds(Array.isArray(r) ? r : (r?.items || []))
    } catch { toast.error('Kalıplar yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const counts = useMemo(() => {
    const c = { all: molds.length, bekliyor: 0, basildi: 0, eksik_var: 0, hatali_basildi: 0 }
    for (const m of molds) c[m.print_status || 'bekliyor'] = (c[m.print_status || 'bekliyor'] || 0) + 1
    return c
  }, [molds])

  const filtered = useMemo(() => {
    return molds.filter(m => {
      if (filter !== 'all' && (m.print_status || 'bekliyor') !== filter) return false
      if (search) {
        const q = search.toLowerCase()
        const hay = `${m.kod || ''} ${m.variation || ''} ${(m.kalip_kodlari || []).join(' ')}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [molds, filter, search])

  const analyze = async (mold, force = false) => {
    setAnalyzing(s => ({ ...s, [mold.id]: true }))
    try {
      const res = await api.get(`/api/molds/${mold.id}/analyze${force ? '?force=true' : ''}`)
      setMolds(prev => prev.map(m => m.id === mold.id
        ? { ...m, print_analysis: res, print_status: res.has_stock_issues ? 'eksik_var' : (m.print_status === 'eksik_var' ? 'bekliyor' : m.print_status) }
        : m))
      if (res.has_stock_issues) toast.error(`${mold.kod}: ${res.missing_stock.length} modelde stok eksiği`)
      else toast.success(`${mold.kod}: stok yeterli`)
    } catch { toast.error('Analiz başarısız') }
    finally { setAnalyzing(s => ({ ...s, [mold.id]: false })) }
  }

  const setStatus = async (mold, status) => {
    setBusyStatus(s => ({ ...s, [mold.id]: true }))
    try {
      await api.patch(`/api/molds/${mold.id}/print-status`, { status })
      setMolds(prev => prev.map(m => m.id === mold.id ? { ...m, print_status: status } : m))
      toast.success(`${mold.kod} → ${STATUS_MAP[status]?.label || status}`)
    } catch { toast.error('Durum güncellenemedi') }
    finally { setBusyStatus(s => ({ ...s, [mold.id]: false })) }
  }

  const analyzeAll = async () => {
    const pending = molds.filter(m => (m.print_status || 'bekliyor') !== 'basildi')
    if (!pending.length) { toast.info('Analiz edilecek kalıp yok'); return }
    toast.info(`${pending.length} kalıp analiz ediliyor…`)
    for (const m of pending) { await analyze(m, true) }
    toast.success('Toplu analiz tamamlandı')
  }

  return (
    <div className="animate-fadein">
      <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🖨️ Baskıcı Paneli</h1>
          <p className="text-sm text-gray-500 mt-1">Kalıpları analiz et, stok eksiklerini gör, baskı durumlarını yönet.</p>
        </div>
        <div className="flex gap-2">
          <a href="/stok" className="btn-secondary !text-sm whitespace-nowrap">🗃️ Stok</a>
          <button onClick={analyzeAll} className="btn-secondary !text-sm whitespace-nowrap">⚡ Tümünü Analiz Et</button>
        </div>
      </div>

      {/* Durum filtreleri */}
      <div className="flex gap-1.5 flex-wrap my-4">
        <FilterBtn active={filter === 'all'} onClick={() => setFilter('all')} label="Tümü" count={counts.all} cls="text-gray-200 bg-brand-input border-brand-border" />
        {PRINT_STATUSES.map(s => (
          <FilterBtn key={s.value} active={filter === s.value} onClick={() => setFilter(s.value)}
            label={`${s.icon} ${s.label}`} count={counts[s.value] || 0} cls={s.cls} />
        ))}
        <div className="flex-1 min-w-[160px]">
          <input className="input w-full !py-1.5 text-sm" placeholder="Kalıp ara… (kod / kalıp kodları)"
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">{[0,1,2].map(i => <div key={i} className="card"><div className="skeleton h-5 w-44 mb-3 rounded" /><div className="skeleton h-3 w-full rounded" /></div>)}</div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12 text-gray-500"><div className="text-4xl mb-2">🖨️</div>
          {molds.length === 0 ? 'Henüz kalıp yok. Kalıp Oluşturucu\'dan kalıp üret.' : 'Bu filtrede kalıp yok.'}</div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {filtered.map(m => (
            <MoldCard key={m.id} mold={m}
              analyzing={!!analyzing[m.id]} busyStatus={!!busyStatus[m.id]}
              onAnalyze={analyze} onSetStatus={setStatus} />
          ))}
        </div>
      )}
    </div>
  )
}

function FilterBtn({ active, onClick, label, count, cls }) {
  return (
    <button onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${active ? cls + ' ring-1 ring-white/20' : 'text-gray-400 bg-transparent border-brand-border hover:bg-brand-input'}`}>
      {label} <span className="ml-1 opacity-70">{count}</span>
    </button>
  )
}

function MoldCard({ mold, analyzing, busyStatus, onAnalyze, onSetStatus }) {
  const st = STATUS_MAP[mold.print_status || 'bekliyor']
  const an = mold.print_analysis
  const [open, setOpen] = useState(false)
  const [showItems, setShowItems] = useState(false)
  const items = mold.items || []
  const [noteOpen, setNoteOpen] = useState(false)
  const [note, setNote] = useState(mold.print_note || '')
  const [noteBusy, setNoteBusy] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)

  const saveNote = async () => {
    setNoteBusy(true)
    try {
      await api.patch(`/api/molds/${mold.id}/print-status`, { note })
      mold.print_note = note
      setNoteOpen(false)
    } catch { /* sessiz */ }
    finally { setNoteBusy(false) }
  }

  const downloadPdf = async () => {
    setPdfBusy(true)
    try {
      const res = await fetch(`/api/molds/${mold.id}/pdf`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('baskici_token')}` },
      })
      if (!res.ok) throw new Error('PDF üretilemedi')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `kalip_${mold.kod || mold.id}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch { /* sessiz */ }
    finally { setPdfBusy(false) }
  }

  return (
    <div className={`card !p-4 ${mold.print_status === 'eksik_var' ? 'ring-1 ring-red-500/30' : ''} ${mold.print_status === 'hatali_basildi' ? 'ring-1 ring-rose-500/40' : ''}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-gray-100 break-all">{mold.kod}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-input text-gray-400">{mold.variation}</span>
          </div>
          <button onClick={() => setShowItems(v => !v)} className="text-xs text-gray-500 mt-0.5 hover:text-gray-300 transition-colors">
            {mold.kilif_sayisi} kılıf · {(mold.kalip_kodlari || []).length} kalıp kodu
            <span className="ml-1 text-accent">{showItems ? '▲ içeriği gizle' : '▼ içeriği gör'}</span>
          </button>
        </div>
        <span className={`text-[11px] px-2 py-1 rounded-lg border whitespace-nowrap ${st.cls}`}>{st.icon} {st.label}</span>
      </div>

      {/* Analiz sonucu */}
      {an && an.total_cases > 0 && (
        <div className={`rounded-lg border p-2.5 my-2 text-xs ${an.has_stock_issues ? 'border-red-500/30 bg-red-500/5' : 'border-emerald-500/25 bg-emerald-500/5'}`}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-gray-300 font-medium">Toplam {an.total_cases} kılıf</span>
            <button onClick={() => setOpen(o => !o)} className="text-[10px] text-gray-500 hover:text-gray-300">{open ? 'gizle' : 'detay'}</button>
          </div>
          {an.has_stock_issues ? (
            <div>
              <div className="text-red-300 font-medium mb-1">⚠️ STOK EKSİĞİ — {an.missing_stock.length} model</div>
              {(open ? an.missing_stock : an.missing_stock.slice(0, 3)).map((it, i) => (
                <div key={i} className="flex items-center gap-2 py-0.5">
                  <span className="text-red-400 font-semibold tabular-nums">-{it.missing}</span>
                  <span className="text-gray-400">{it.variation}</span>
                  <span className="text-gray-300">{it.model}</span>
                  {it.not_in_system ? <span className="text-[10px] text-red-400/80">📦 stokta yok</span>
                    : <span className="text-[10px] text-gray-500">({it.in_stock} mevcut)</span>}
                </div>
              ))}
              {!open && an.missing_stock.length > 3 && <div className="text-[10px] text-gray-500 mt-0.5">+{an.missing_stock.length - 3} model daha…</div>}
            </div>
          ) : (
            <div className="text-emerald-300">✓ Tüm modeller için stok yeterli</div>
          )}
        </div>
      )}

      {/* Kalip icerigi — slotlar */}
      {showItems && (
        <div className="rounded-lg border border-brand-border bg-brand-input/30 p-2 my-2">
          {items.length === 0 ? (
            <div className="text-xs text-gray-500 text-center py-2">Bu kalıpta slot bilgisi yok.</div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {items.map((it, i) => (
                <div key={i} className="flex items-center gap-2 bg-brand-card rounded-md p-1.5 border border-brand-border/50">
                  <div className="shrink-0 w-9 h-9 rounded bg-brand-input overflow-hidden flex items-center justify-center">
                    {it.thumbnail_url
                      ? <img src={it.thumbnail_url} alt="" className="w-full h-full object-contain" />
                      : <span className="text-[9px] text-gray-600">{it.slot_index != null ? `#${it.slot_index + 1}` : '—'}</span>}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[11px] text-gray-200 truncate font-medium">{it.model || '—'}</div>
                    <div className="text-[10px] text-gray-500 truncate">{it.design_code || it.kalip_rengi || '—'}</div>
                    {it.order_number && <div className="text-[9px] text-gray-600 truncate">#{it.order_number}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Not */}
      {(noteOpen || mold.print_note) && (
        <div className="my-2">
          {noteOpen ? (
            <div className="flex gap-1.5">
              <input className="input flex-1 !text-xs" value={note} onChange={e => setNote(e.target.value)} placeholder="Kalıp notu…" />
              <button onClick={saveNote} disabled={noteBusy} className="btn-primary !text-xs">{noteBusy ? '…' : 'Kaydet'}</button>
            </div>
          ) : (
            <div className="text-xs text-amber-300/90 bg-amber-500/5 border border-amber-500/20 rounded px-2 py-1 flex items-center gap-1">
              📝 {mold.print_note}
            </div>
          )}
        </div>
      )}

      {/* Aksiyonlar */}
      <div className="flex items-center gap-1.5 flex-wrap mt-2">
        <button onClick={() => onAnalyze(mold, true)} disabled={analyzing}
          className="btn-secondary !text-xs">{analyzing ? 'Analiz…' : (an ? '↻ Yeniden Analiz' : '🔍 Analiz Et')}</button>
        <button onClick={downloadPdf} disabled={pdfBusy} className="btn-secondary !text-xs">{pdfBusy ? 'PDF…' : '⬇️ PDF'}</button>
        <button onClick={() => setNoteOpen(v => !v)} className={`btn-secondary !text-xs ${mold.print_note ? '!text-amber-300' : ''}`}>📝 Not</button>
        <div className="flex-1" />
        {mold.print_status !== 'basildi' && (
          <button onClick={() => onSetStatus(mold, 'basildi')} disabled={busyStatus}
            className="!text-xs px-2 py-1 rounded-lg text-emerald-300 hover:bg-emerald-500/10 border border-emerald-500/25">✓ Basıldı</button>
        )}
        {mold.print_status !== 'hatali_basildi' && (
          <button onClick={() => onSetStatus(mold, 'hatali_basildi')} disabled={busyStatus}
            className="!text-xs px-2 py-1 rounded-lg text-rose-400 hover:bg-rose-500/10 border border-rose-500/25">✕ Hatalı</button>
        )}
        {mold.print_status !== 'bekliyor' && (
          <button onClick={() => onSetStatus(mold, 'bekliyor')} disabled={busyStatus}
            className="!text-xs px-2 py-1 rounded-lg text-amber-300 hover:bg-amber-500/10 border border-amber-500/25">⏳ Bekliyor</button>
        )}
      </div>
    </div>
  )
}
