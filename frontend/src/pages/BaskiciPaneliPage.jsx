import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, fetchYetkili } from '../lib/api'
import { useToast } from '../components/Toast'
import EmptyState from '../components/EmptyState'
import { renk } from '../lib/durum'
import { mutlak } from '../lib/taban'

// Renkler ortak olcekten (lib/durum) — ayni anlam her sayfada ayni renk.
const PRINT_STATUSES = [
  { value: 'bekliyor',       label: 'Bekliyor',       icon: '⏳', cls: renk('bekliyor').cls },
  { value: 'basildi',        label: 'Basıldı',        icon: '✓',  cls: renk('tamam').cls },
  { value: 'eksik_var',      label: 'Eksik Var',      icon: '⚠️', cls: renk('uyari').cls },
  { value: 'hatali_basildi', label: 'Hatalı Basıldı', icon: '✕',  cls: renk('hata').cls },
]
const STATUS_MAP = Object.fromEntries(PRINT_STATUSES.map(s => [s.value, s]))

export default function BaskiciPaneliPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [molds, setMolds] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [analyzing, setAnalyzing] = useState({})    // { moldId: true }
  const [busyStatus, setBusyStatus] = useState({})
  const [totalMissing, setTotalMissing] = useState(null)   // modal verisi
  const [tmBusy, setTmBusy] = useState(false)
  const [requiredModels, setRequiredModels] = useState(null)  // gerekli modeller modal
  const [rmBusy, setRmBusy] = useState(false)
  const [preview, setPreview] = useState(null)             // buyuk onizleme {url, title}
  const [confirmPrint, setConfirmPrint] = useState(null)   // eksik stoklu basildi onayi {mold}
  const [clearBusy, setClearBusy] = useState(false)

  const load = async (sid = storeId) => {
    setLoading(true)
    try {
      const r = await api.get(`/api/molds${sid ? `?store_id=${sid}` : ''}`)
      const all = Array.isArray(r) ? r : (r?.items || [])
      // Bos (hic kilif yok) + taslak (stage 1, henuz kaydedilmemis) kaliplar panele dusmez
      setMolds(all.filter(m => (m.kilif_sayisi || 0) > 0 && (m.current_stage == null || (m.current_stage > 1 && m.current_stage < 5))))
    } catch { toast.error('Kalıplar yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [storeId])
  useEffect(() => {
    api.get('/api/stores?include_bayii=true').then(s => setStores(Array.isArray(s) ? s : [])).catch(() => {})
  }, [])

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

  const requestStatus = (mold, status) => {
    if (status === 'basildi' && (mold.print_status === 'eksik_var' || (mold.print_analysis && mold.print_analysis.has_stock_issues))) {
      setConfirmPrint({ mold, status })
      return
    }
    setStatus(mold, status)
  }

  const clearPrinted = async () => {
    if (!confirm('Basılmış tüm kalıpları silmek istiyor musun? (Geri alınamaz — slotlar yeniden planlanır)')) return
    setClearBusy(true)
    try {
      const r = await api.post('/api/molds/print/bulk-delete', { only_printed: true })
      toast.success(`${r.deleted_count} basılmış kalıp silindi`)
      load()
    } catch { toast.error('Temizlenemedi') }
    finally { setClearBusy(false) }
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

  // Varsayılan: YALNIZ panelde duran, basılmamış kalıplarda gerekenler.
  // siparisler=true → kalıba hiç girmeyen ürünlerin (aksesuar) açık sipariş
  // ihtiyacı da eklenir; bu ayrı bir soru olduğu için isteğe bağlı.
  const loadTotalMissing = async (siparisler = false) => {
    setTmBusy(true)
    try {
      const r = await api.get(`/api/molds/print/total-missing${siparisler ? '?siparisler=true' : ''}`)
      setTotalMissing(r)
    } catch { toast.error('Toplam eksik hesaplanamadı') }
    finally { setTmBusy(false) }
  }

  const loadRequiredModels = async () => {
    setRmBusy(true)
    try {
      const r = await api.get('/api/molds/print/required-models')
      setRequiredModels(r)
    } catch { toast.error('Gerekli modeller hesaplanamadı') }
    finally { setRmBusy(false) }
  }

  const copyRequiredModels = async () => {
    if (!requiredModels?.items?.length) return
    const text = requiredModels.items
      .map(it => it.kaynak === 'siparis'
        // Aksesuarda varyasyon yok; tedarikçiye grup adıyla gitmeli.
        ? `${it.count} ad ${it.grup} — ${it.model}`
        : `${it.count} ad ${String(it.variation || '').toUpperCase()} ${it.model}`)
      .join('\n')
    try { await navigator.clipboard.writeText(text); toast.success('Liste kopyalandı') }
    catch { toast.error('Kopyalanamadı') }
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
          <button onClick={loadRequiredModels} disabled={rmBusy} className="btn-secondary !text-sm whitespace-nowrap">{rmBusy ? '…' : '📋 Gerekli Modeller'}</button>
          <button onClick={() => loadTotalMissing(false)} disabled={tmBusy} className="btn-secondary !text-sm whitespace-nowrap">{tmBusy ? '…' : '📊 Toplam Eksik'}</button>
          <button onClick={clearPrinted} disabled={clearBusy} className="!text-sm px-3 py-1.5 rounded-lg text-rose-400 hover:bg-rose-500/10 border border-rose-500/25 whitespace-nowrap">{clearBusy ? '…' : '🗑️ Basılanları Temizle'}</button>
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
        <select value={storeId} onChange={e => setStoreId(e.target.value)} className="input !text-sm !py-1.5 min-w-[170px]">
          <option value="">Tümü (Mağaza + Bayi)</option>
          <optgroup label="Mağazalar">
            {stores.filter(s => s.platform !== 'bayii').map(s => <option key={s.id} value={s.id}>🏪 {s.name}</option>)}
          </optgroup>
          <optgroup label="Bayiler">
            {stores.filter(s => s.platform === 'bayii').map(s => <option key={s.id} value={s.id}>🤝 {s.name.replace(/^Bayii:\s*/, '')}</option>)}
          </optgroup>
        </select>
        <div className="flex-1 min-w-[160px]">
          <input className="input w-full !py-1.5 text-sm" placeholder="Kalıp ara… (kod / kalıp kodları)"
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">{[0,1,2].map(i => <div key={i} className="card"><div className="skeleton h-5 w-44 mb-3 rounded" /><div className="skeleton h-3 w-full rounded" /></div>)}</div>
      ) : filtered.length === 0 ? (
        <div className="card !p-0">
          {molds.length === 0 ? (
            <EmptyState ikon="🖨️" baslik="Henüz kalıp yok"
              aciklama="Siparişler kalıba alındığında burada listelenir. Kalıp Oluşturucu'dan yeni kalıp üretebilirsin."
              aksiyon={<a href="/kalip-olustur" className="btn-primary !text-sm">🧩 Kalıp Oluşturucu</a>} />
          ) : (
            <EmptyState ikon="🔍" baslik="Bu filtrede kalıp yok"
              aciklama="Seçili durum ve aramayla eşleşen kalıp bulunamadı."
              aksiyon={<button onClick={() => { setFilter('all'); setSearch('') }}
                               className="btn-secondary !text-sm">Filtreyi temizle</button>} />
          )}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {filtered.map(m => (
            <MoldCard key={m.id} mold={m}
              analyzing={!!analyzing[m.id]} busyStatus={!!busyStatus[m.id]}
              onAnalyze={analyze} onSetStatus={requestStatus} onPreview={setPreview} onOpen={(id) => navigate(`/kalip/${id}`, { state: { from: '/baskici-paneli' } })} />
          ))}
        </div>
      )}

      {totalMissing && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 p-4" onMouseDown={e => e.target === e.currentTarget && setTotalMissing(null)}>
          <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 my-8 max-h-[85vh] overflow-y-auto animate-popin">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-100">📊 Toplam Stok Eksiği</h2>
              <button onClick={() => setTotalMissing(null)} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
            </div>
            {totalMissing.items.length === 0 ? (
              <EmptyState dar ikon="✅" baslik="Hiç stok eksiği yok"
                aciklama="Panelde duran basılmamış kalıplarda gereken her model rafta var." />
            ) : (
              <>
                <div className="text-xs text-gray-500 mb-3">
                  Panelde duran <b>{totalMissing.kalip_sayisi ?? '—'} basılmamış kalıpta</b> gereken
                  ama rafta olmayanlar · {totalMissing.total_models} satır ·
                  toplam <b>{totalMissing.total_missing} adet</b> alınmalı
                  {totalMissing.siparis_kalem_sayisi > 0 &&
                    ` · ${totalMissing.siparis_kalem_sayisi}'i aksesuar/işlemsiz ürün`}
                </div>
                {/* Kalıba hiç girmeyen ürünler (aksesuar) ayrı bir soru — isteyen açar */}
                <label className="flex items-center gap-2 mb-3 cursor-pointer select-none">
                  <input type="checkbox" className="accent-accent"
                    checked={!!totalMissing.siparisler_dahil} disabled={tmBusy}
                    onChange={e => loadTotalMissing(e.target.checked)} />
                  <span className="text-[11px] text-gray-400">
                    Açık siparişlerdeki aksesuar/işlemsiz ürünleri de göster (kalıba girmeyenler)
                  </span>
                </label>
                <div className="space-y-1.5">
                  {totalMissing.items.map((it, i) => (
                    <div key={i} className="flex items-center gap-2 bg-brand-input/40 rounded-lg px-3 py-2">
                      {/* "-12" stok eksiymiş gibi okunuyordu; eksik ADEDİ yazılı */}
                      <span className="text-red-400 font-bold tabular-nums text-sm w-12">{it.total_missing}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-200 truncate">{it.model}</div>
                        {/* Aksesuar/işleme girmeyen ürünler kalıptan değil, açık
                            siparişlerden geliyor — "kalıpta" yazmak yanıltıcı olur. */}
                        <div className="text-[10px] text-gray-500"
                             title={it.kaynak === 'siparis' && it.siparisler?.length
                               ? `Siparişler: ${it.siparisler.map(n => '#' + n).join(', ')}` : undefined}>
                          {it.kaynak === 'siparis'
                            ? `🎁 ${it.grup} · ${it.siparis_sayisi} siparişte · ihtiyaç ${it.ihtiyac}, stok ${it.mevcut}`
                            : `${it.variation} · ${it.mold_count} kalıpta · ihtiyaç ${it.ihtiyac ?? '—'}, stok ${it.mevcut ?? 0}`}
                        </div>
                      </div>
                      {it.not_in_system && (
                        <span className="text-[10px] text-red-400/80 whitespace-nowrap">📦 stokta yok</span>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {requiredModels && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 p-4" onMouseDown={e => e.target === e.currentTarget && setRequiredModels(null)}>
          <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 my-8 max-h-[85vh] overflow-y-auto animate-popin">
            <div className="flex items-center justify-between mb-3 gap-2">
              <h2 className="text-lg font-semibold text-gray-100">📋 Kalıplarda Gereken Modeller</h2>
              <div className="flex items-center gap-2">
                {requiredModels.items.length > 0 && (
                  <button onClick={copyRequiredModels} className="btn-secondary !text-xs whitespace-nowrap">📋 Kopyala</button>
                )}
                <button onClick={() => setRequiredModels(null)} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
              </div>
            </div>
            {requiredModels.items.length === 0 ? (
              <EmptyState dar ikon="📋" baslik="Hazırlanacak bir şey yok"
                aciklama="Panelde basılmamış kalıp ve açık siparişlerde stok eksiği bulunmuyor." />
            ) : (
              <>
                <div className="text-xs text-gray-500 mb-3">
                  {requiredModels.total_models} satır · toplam {requiredModels.total_count} adet · kalıplar için stok bakılmadı
                  {requiredModels.siparis_kalem_sayisi > 0 &&
                    ` · ${requiredModels.siparis_kalem_sayisi} kalem kalıba girmeyen ürün (magsafe, ekran koruyucu…)`}
                </div>
                <div className="space-y-1.5">
                  {requiredModels.items.map((it, i) => (
                    <div key={i} className="flex items-center gap-2 bg-brand-input/40 rounded-lg px-3 py-2">
                      <span className={`font-bold tabular-nums text-sm w-12 ${it.kaynak === 'siparis' ? 'text-red-400' : 'text-accent'}`}>{it.count}×</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-200 truncate">{it.model}</div>
                        <div className="text-[10px] text-gray-500"
                             title={it.kaynak === 'siparis' && it.siparisler?.length
                               ? `Siparişler: ${it.siparisler.map(n => '#' + n).join(', ')}` : undefined}>
                          {it.kaynak === 'siparis'
                            ? `🎁 ${it.grup} · ${it.siparis_sayisi} siparişte (kalıba girmez)`
                            : `${it.variation} · ${it.mold_count} kalıpta`}
                          {it.kaynak === 'siparis' && it.stok_takibi === false && (
                            <span className="ml-1.5 text-amber-400/90"
                                  title="Bu ürün bir stok grubuna bağlı değil — ihtiyaç listesinde görünür ama stok/eksik hesabına girmez. Stok sayfasından bağlayabilirsin.">
                              · stok takibi yok
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {confirmPrint && (
        <div className="fixed inset-0 z-[155] flex items-center justify-center bg-black/60 p-4" onMouseDown={e => e.target === e.currentTarget && setConfirmPrint(null)}>
          <div className="bg-brand-card border border-red-500/30 rounded-xl w-full max-w-sm p-5 animate-popin">
            <h3 className="text-base font-semibold text-gray-100 mb-2">⚠️ Stok Eksiği Var</h3>
            <p className="text-sm text-gray-400 mb-4"><span className="text-gray-200 font-medium">{confirmPrint.mold.kod}</span> kalıbında stok eksiği görünüyor. Stok tedariği sağlandıysa basıldı olarak işaretleyebilirsin.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmPrint(null)} className="btn-secondary !text-sm">Vazgeç</button>
              <button onClick={() => { setStatus(confirmPrint.mold, confirmPrint.status); setConfirmPrint(null) }}
                className="btn-primary !text-sm">📦 Stok sağlandı, basıldı</button>
            </div>
          </div>
        </div>
      )}

      {preview && (
        <div className="fixed inset-0 z-[160] flex items-center justify-center bg-black/80 p-4" onMouseDown={() => setPreview(null)}>
          <div className="mx-auto max-w-2xl max-h-[85vh] flex flex-col items-center" onMouseDown={e => e.stopPropagation()}>
            <img src={preview.url} alt={preview.title} className="max-w-full max-h-[75vh] object-contain rounded-lg" />
            <div className="mt-2 text-sm text-gray-300">{preview.title}</div>
            <button onClick={() => setPreview(null)} className="mt-2 btn-secondary !text-xs">Kapat</button>
          </div>
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

function MoldCard({ mold, analyzing, busyStatus, onAnalyze, onSetStatus, onPreview, onOpen }) {
  const st = STATUS_MAP[mold.print_status || 'bekliyor']
  const an = mold.print_analysis
  const [open, setOpen] = useState(false)
  const [showItems, setShowItems] = useState(false)
  const items = mold.items || []
  const [noteOpen, setNoteOpen] = useState(false)
  const [note, setNote] = useState(mold.print_note || '')
  const [noteBusy, setNoteBusy] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  const [pdfDurum, setPdfDurum] = useState('')   // 'hazırlanıyor… 42 sn'

  const saveNote = async () => {
    setNoteBusy(true)
    try {
      await api.patch(`/api/molds/${mold.id}/print-status`, { note })
      mold.print_note = note
      setNoteOpen(false)
    } catch { /* sessiz */ }
    finally { setNoteBusy(false) }
  }

  // PDF üretimi karmaşık vektör tasarımlarda dakikalar sürebiliyor ve vektör
  // KORUNUYOR (rasterleştirme kalite kaybı yapardı). Sunucu işi arka planda
  // yapıp 202 döndüğü için burada hazır olana kadar bekliyoruz.
  const downloadPdf = async () => {
    setPdfBusy(true)
    setPdfDurum('')
    const istek = () => fetchYetkili(mutlak(`/api/molds/${mold.id}/pdf`))
    const basla = Date.now()
    const AZAMI_MS = 15 * 60 * 1000
    try {
      while (true) {
        const res = await istek()

        // 409 = henüz hazır değil (bilerek 4xx: 2xx olsaydı gövde dosya sanılırdı)
        if (res.status === 409) {
          const gecen = Math.round((Date.now() - basla) / 1000)
          setPdfDurum(`hazırlanıyor… ${gecen} sn`)
          if (Date.now() - basla > AZAMI_MS) {
            alert('PDF hazırlanması beklenenden uzun sürdü. Sunucuda üretim sürüyor olabilir — birkaç dakika sonra tekrar dene.')
            return
          }
          await new Promise(r => setTimeout(r, 4000))
          continue
        }

        if (!res.ok) {
          let detay = ''
          try { detay = (await res.json())?.detail || '' } catch { /* json değilse geç */ }
          alert(detay || `PDF üretilemedi (HTTP ${res.status})`)
          return
        }

        // Gelenin gerçekten PDF olduğunu doğrula — aksi halde bozuk dosya iner
        const tip = res.headers.get('content-type') || ''
        const blob = await res.blob()
        if (!tip.includes('pdf') || blob.size < 5000) {
          alert(`Beklenen PDF gelmedi (tür: ${tip || 'bilinmiyor'}, boyut: ${blob.size} B). Sayfayı yenileyip tekrar dene.`)
          return
        }
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `kalip_${mold.kod || mold.id}.pdf`
        document.body.appendChild(a); a.click(); a.remove()
        URL.revokeObjectURL(url)
        return
      }
    } catch (e) { alert('PDF indirilemedi: ' + (e?.message || '')) }
    finally { setPdfBusy(false); setPdfDurum('') }
  }

  const removeSlot = async (it) => {
    if (!it.id) return
    if (!confirm(`Bu kılıfı kalıptan çıkar? (${it.model || ''} ${it.design_code || ''})\nSlot yeniden planlanacak.`)) return
    try {
      await api.post(`/api/molds/${mold.id}/items/${it.id}/remove`, { action: 'replan' })
      window.location.reload()
    } catch { /* sessiz */ }
  }

  return (
    <div className={`card !p-4 ${mold.print_status === 'eksik_var' ? 'ring-1 ring-red-500/30' : ''} ${mold.print_status === 'hatali_basildi' ? 'ring-1 ring-rose-500/40' : ''}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={() => onOpen?.(mold.id)} className="text-sm font-semibold text-gray-100 break-all hover:text-accent transition-colors text-left" title="Kalıp detayını aç">{mold.kod}</button>
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
        <div className="rounded-lg border border-brand-border bg-brand-input/30 p-2 my-2 overflow-x-auto">
          {items.length === 0 ? (
            <div className="text-xs text-gray-500 text-center py-2">Bu kalıpta slot bilgisi yok.</div>
          ) : (
<div className="space-y-1 min-w-[560px]">
              {[0, 1, 2].map(ri => (
                <div key={ri} className="grid grid-cols-9 gap-1">
              {Array.from({ length: 9 }).map((_, ci) => {
                const slotNo = 27 - (ri * 9 + ci)        // MoldDetailPage ile ayni: 27 sol-ust, 1 sag-alt
                const it = items.find(x => (x.slot_index + 1) === slotNo)
                const slot = slotNo - 1
                if (!it) {
                  return (
                    <div key={slot} className="rounded border border-dashed border-brand-border/40 bg-brand-input/10 overflow-hidden opacity-50">
                      <div className="relative aspect-square flex items-center justify-center">
                        <span className="absolute top-0 left-0 text-[6px] bg-black/30 text-gray-500 px-0.5 rounded-br leading-none">{slot + 1}</span>
                      </div>
                      <div className="px-0.5 py-0.5 h-6"></div>
                    </div>
                  )
                }
                return (
                  <div key={slot} className="group relative bg-brand-card rounded border border-brand-border/50 overflow-hidden">
                    <div className="relative aspect-square bg-brand-input/30 cursor-pointer hover:ring-1 hover:ring-accent"
                      onClick={() => it.thumbnail_url && onPreview?.({ url: it.thumbnail_url, title: `${it.model || ''} ${it.design_code || ''}`.trim() })}>
                      {it.thumbnail_url
                        ? <img src={it.thumbnail_url} alt="" className="w-full h-full object-contain" />
                        : <div className="w-full h-full flex items-center justify-center text-[7px] text-gray-600 text-center px-0.5 leading-tight">{it.model || ''}</div>}
                      <span className="absolute top-0 left-0 text-[6px] bg-black/55 text-gray-200 px-0.5 rounded-br leading-none">{slot + 1}</span>
                      {it.id && (
                        <button onClick={(e) => { e.stopPropagation(); removeSlot(it) }} title="Kılıfı çıkar"
                          className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 text-rose-300 hover:text-rose-200 text-[10px] leading-none px-1 py-0.5 rounded-bl">✕</button>
                      )}
                    </div>
                    <div className="px-0.5 py-0.5">
                      <div className="text-[8px] text-gray-200 font-medium truncate leading-tight" title={it.model || ''}>{it.model || '—'}</div>
                      <div className="text-[7px] text-gray-500 truncate leading-tight">{it.kilif_rengi || it.kalip_tipi || mold.variation || '—'}</div>
                    </div>
                  </div>
                )
              })}
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
        <button onClick={() => onOpen?.(mold.id)} className="btn-secondary !text-xs">📋 Detay</button>
        <button onClick={() => onAnalyze(mold, true)} disabled={analyzing}
          className="btn-secondary !text-xs">{analyzing ? 'Analiz…' : (an ? '↻ Yeniden Analiz' : '🔍 Analiz Et')}</button>
        <button onClick={downloadPdf} disabled={pdfBusy}
                title={pdfBusy ? 'Karmaşık tasarımlarda üretim birkaç dakika sürebilir' : 'Baskıya hazır PDF'}
                className="btn-secondary !text-xs whitespace-nowrap">
          {pdfBusy ? (pdfDurum || 'PDF…') : '⬇️ PDF'}
        </button>
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
