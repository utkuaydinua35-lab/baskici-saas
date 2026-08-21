import { useEffect, useState, useCallback, useRef } from 'react'
import { api, getToken } from '../lib/api'

const LAST_INDEX_KEY = 'packaging_last_index'
const CARGO_HOUR = 18   // kargo kesim saati

// stages.py ikon hint -> emoji
const STAGE_EMOJI = {
  inbox: '📥', loader: '🔄', barcode: '|||', layers: '🧩',
  printer: '🖨', 'printer-check': '🖨', package: '📦', truck: '🚚', 'check-circle': '✓',
}

function useCargoCountdown() {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(t)
  }, [])
  const d = new Date(now)
  const target = new Date(d); target.setHours(CARGO_HOUR, 0, 0, 0)
  let diffMs = target - d
  const passed = diffMs <= 0
  if (diffMs < 0) diffMs = 0
  const h = Math.floor(diffMs / 3600000)
  const m = Math.floor((diffMs % 3600000) / 60000)
  const clock = d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
  return { clock, h, m, passed }
}

export default function PackagingPage() {
  const [queue, setQueue] = useState({ total: 0, index: 0, order: null, stages: [] })
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [labelPending, setLabelPending] = useState(null)  // {id, order_number, takip_no} — barkod otomatik açılamadı, elle yazdır
  const [manualAddr, setManualAddr] = useState(false)   // ilçe çözülemedi → il/ilçe seçici
  const [ilIlce, setIlIlce] = useState(null)            // { il: [ilçe, ...] }
  const [selIl, setSelIl] = useState('')
  const [selIlce, setSelIlce] = useState('')
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('')   // '' | 'store:<id>' | 'dealer:<id>'
  const [readyOnly, setReadyOnly] = useState(false)
  // "Eksiği olanlar": en az bir ürünü hazır ama hepsi değil. Kargoya verilemez
  // ama hazırlanan kılıflar dükkanda ayrı duruyor — sistemde de görünsün.
  const [eksigiOlanlar, setEksigiOlanlar] = useState(false)
  const { clock, h, m, passed } = useCargoCountdown()

  // Filtreleri ref'te tut — loadIndex kimliği stabil kalsın
  const filtersRef = useRef({ search: '', source: '', readyOnly: false, eksigiOlanlar: false })
  filtersRef.current = { search, source, readyOnly, eksigiOlanlar }

  const loadIndex = useCallback(async (idx) => {
    setLoading(true); setMsg(null); setManualAddr(false); setLabelPending(null)
    try {
      const f = filtersRef.current
      const params = new URLSearchParams({ index: String(idx) })
      if (f.search.trim()) params.set('search', f.search.trim())
      if (f.source.startsWith('store:')) params.set('store_id', f.source.slice(6))
      else if (f.source.startsWith('dealer:')) params.set('dealer_id', f.source.slice(7))
      if (f.readyOnly) params.set('ready_only', 'true')
      if (f.eksigiOlanlar) params.set('eksigi_olanlar', 'true')
      const r = await api.get(`/api/packaging/queue?${params}`)
      setQueue(r)
      try { localStorage.setItem(LAST_INDEX_KEY, String(r.index)) } catch {}
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Kuyruk yüklenemedi' })
    } finally { setLoading(false) }
  }, [])

  // ilk acilis: localStorage'daki son index (yoksa 0 = en eski)
  const _first = useRef(true)
  useEffect(() => {
    let start = 0
    try { const v = parseInt(localStorage.getItem(LAST_INDEX_KEY) || '0', 10); if (!isNaN(v) && v >= 0) start = v } catch {}
    loadIndex(start)
  }, [loadIndex])

  // filtre değişince başa dön (debounced)
  useEffect(() => {
    if (_first.current) { _first.current = false; return }
    const t = setTimeout(() => loadIndex(0), 300)
    return () => clearTimeout(t)
  }, [search, source, readyOnly, eksigiOlanlar, loadIndex])

  const total = queue.total || 0
  const index = queue.index || 0
  const order = queue.order
  const go = (idx) => { if (total === 0) return; const c = Math.max(0, Math.min(idx, total - 1)); loadIndex(c) }

  // Kalemi "kenara ayrıldı" işaretle/kaldır. İyimser güncelleme: tık anında
  // görünsün, sunucu hata verirse geri alınsın.
  const ayrildiToggle = async (it) => {
    const yeni = !it.ayrildi
    setQueue(q => ({ ...q, order: { ...q.order,
      items: q.order.items.map(x => x.line_item_id === it.line_item_id ? { ...x, ayrildi: yeni } : x) } }))
    try {
      await api.patch(`/api/packaging/kalem/${it.line_item_id}/ayrildi`, { ayrildi: yeni })
    } catch (e) {
      setQueue(q => ({ ...q, order: { ...q.order,
        items: q.order.items.map(x => x.line_item_id === it.line_item_id ? { ...x, ayrildi: !yeni } : x) } }))
      setMsg({ ok: false, text: e?.detail || 'İşaretlenemedi' })
    }
  }

  const downloadLabel = async () => {
    if (!order) return
    const res = await fetch(`/api/packaging/order/${encodeURIComponent(order.id)}/label`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) { setMsg({ ok: false, text: 'Etiket üretilemedi' }); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 30000)
  }

  // Panelin kendi barkodlu adres etiketi (PDF) -> yeni sekmede aç + yazdır.
  // Kendi kargo anlaşmasında paketin üzerine yapıştırılan etiket budur.
  // Döner: pencere açıldı mı (false = popup engeli / hata -> İLERLEME).
  const printAdresEtiketi = async (orderId) => {
    try {
      const res = await fetch(`/api/packaging/order/${encodeURIComponent(orderId)}/label`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) return false
      const url = URL.createObjectURL(await res.blob())
      const wnd = window.open(url, '_blank')
      if (!wnd) { URL.revokeObjectURL(url); return false }
      try { wnd.addEventListener('load', () => { try { wnd.print() } catch { /* kullanıcı yazdırır */ } }) } catch { /* çapraz köken */ }
      setTimeout(() => URL.revokeObjectURL(url), 60000)
      return true
    } catch { return false }
  }

  // SVG kargo etiketi -> yeni sekmede ac + otomatik yazdir. Döner: pencere açıldı mı (false = popup engeli)
  const openLabelSvg = (svg, takipNo) => {
    try {
      const w = window.open('', '_blank')
      if (!w) return false
      w.document.write(
        `<!doctype html><html><head><title>Kargo Etiketi ${takipNo || ''}</title>` +
        `<style>@page{margin:0}body{margin:0;display:flex;justify-content:center;padding:8px}svg{max-width:100%;height:auto}</style>` +
        `</head><body>${svg}<scr` + `ipt>window.onload=function(){setTimeout(function(){window.print()},300)}</scr` + `ipt></body></html>`
      )
      w.document.close()
      return true
    } catch { return false }
  }

  // Basit Kargo etiket SVG'sini yeniden çek (kargo-gonder boş dönerse / re-print)
  const fetchKargoSvg = async (orderId) => {
    try {
      const res = await fetch(`/api/packaging/order/${encodeURIComponent(orderId)}/kargo-label`,
        { headers: { Authorization: `Bearer ${getToken()}` } })
      return res.ok ? await res.text() : null
    } catch { return null }
  }

  // Barkodu yazdır: svg verilmişse onu; yoksa kargo-label'dan kısa retry ile çek
  // (Basit Kargo etiket üretimi yavaş olabiliyor). Döner: yazdırma penceresi açıldı mı.
  const printKargoLabel = async (orderId, svg, takipNo) => {
    let s = svg
    for (let i = 0; !s && i < 3; i++) {
      await new Promise(r => setTimeout(r, 1200))
      s = await fetchKargoSvg(orderId)
    }
    return s ? openLabelSvg(s, takipNo) : false
  }

  const kargoGonder = async (opts = {}) => {
    if (!order || busy) return
    if (!opts.il && !confirm(`#${order.order_number} siparişi kargoya verilecek (mağaza kargo firması). Onaylıyor musun?`)) return
    setBusy(true); setMsg(null)
    try {
      const r = await api.post(`/api/packaging/order/${encodeURIComponent(order.id)}/kargo-gonder`,
        { il: opts.il || '', ilce: opts.ilce || '' })
      const tn = r.takip_no || '—'
      const firma = r.handler_name || 'Kargo'
      const extra = r.shopify_ok ? '' : ' (Shopify\'a yazılamadı, takip no panelde)'
      setManualAddr(false)
      // Barkodu yazdır (svg boşsa kargo-label'dan retry ile çek). Sadece yazdırınca ilerle.
      const printed = await printKargoLabel(order.id, r.label_svg, tn)
      if (printed) {
        setLabelPending(null)
        setMsg({ ok: true, text: `✅ ${firma} gönderi oluştu · Takip No: ${tn}${extra}` })
        setTimeout(() => loadIndex(index), 2500)
      } else {
        // Barkod açılamadı (boş etiket / popup engeli) — İLERLEME, elle yazdırılsın
        setLabelPending({ id: order.id, order_number: order.order_number, takip_no: tn })
        setMsg({ ok: false, text: `⚠ Gönderi oluştu (Takip: ${tn}) ama barkod otomatik açılamadı. Aşağıdaki "🖨 Barkodu Yazdır"a bas, sonra "Sonraki"ye geç.` })
      }
    } catch (e) {
      const t = typeof e?.detail === 'string' ? e.detail : 'Kargo gönderimi başarısız'
      if (t.includes('İlçe belirlenemedi')) {
        setMsg({ ok: false, text: '⚠ Adresten il/ilçe çözülemedi. Aşağıdan seçip gönderebilirsin.' })
        setManualAddr(true)
        if (!ilIlce) api.get('/api/packaging/il-ilce').then(setIlIlce).catch(() => {})
      } else {
        setMsg({ ok: false, text: t })
      }
    } finally {
      setBusy(false)
    }
  }

  const fmtDate = (iso) => {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleString('tr-TR', { day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch { return iso }
  }

  const stageEmoji = (icon) => STAGE_EMOJI[icon] || '•'

  return (
    <div className="mx-auto max-w-[1400px]">
      {/* Ust bar: kargo geri sayim + kalan */}
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <div className="text-sm text-gray-300">
          <span className="font-mono text-gray-100">{clock}</span>
          {' — '}
          {passed
            ? <span className="text-red-400 font-medium">KARGO SAATİ GEÇTİ</span>
            : <span className="text-gray-300">KARGO SAATİNE <b className="text-gray-100">{h} SAAT {m} DAKİKA</b> KALDI</span>}
        </div>
        <div className="text-sm text-gray-400">
          {eksigiOlanlar ? 'EKSİĞİ OLAN' : readyOnly ? 'PAKETLEMEYE UYGUN' : 'KALAN PAKETLENECEK'} SİPARİŞ: <b className="text-gray-100">{total} ADET</b>
        </div>
      </div>

      {/* Filtreler: arama + marka + paketleme uygunluğu */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">🔍</span>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Sipariş no / müşteri ara…" className="input w-full !pl-9 !text-sm" />
        </div>
        <select value={source} onChange={e => setSource(e.target.value)} className="input !text-sm !py-2 w-auto max-w-[200px]">
          <option value="">Tüm mağaza / bayi</option>
          {(queue.stores || []).length > 0 && (
            <optgroup label="Mağazalar">
              {queue.stores.map(s => <option key={s.id} value={`store:${s.id}`}>🏪 {s.name}</option>)}
            </optgroup>
          )}
          {(queue.dealers || []).length > 0 && (
            <optgroup label="Bayiler">
              {queue.dealers.map(d => <option key={d.id} value={`dealer:${d.id}`}>🤝 {d.name}</option>)}
            </optgroup>
          )}
        </select>
        <button onClick={() => { setReadyOnly(v => !v); if (!readyOnly) setEksigiOlanlar(false) }}
          title="Sadece tüm ürünleri basılı kalıpta / hazır olan siparişler"
          className={`!text-sm px-4 py-2 rounded-full border whitespace-nowrap transition-colors ${
            readyOnly ? 'bg-accent/15 text-accent border-accent/40' : 'bg-brand-input/60 text-gray-300 border-brand-border hover:text-gray-100'
          }`}>
          {readyOnly ? '✓ ' : ''}Paketlemeye uygun
        </button>
        <button onClick={() => { setEksigiOlanlar(v => !v); if (!eksigiOlanlar) setReadyOnly(false) }}
          title="En az bir ürünü hazır ama hepsi değil — kargoya verilemez, hazırlananlar kenara ayrılır"
          className={`!text-sm px-4 py-2 rounded-full border whitespace-nowrap transition-colors ${
            eksigiOlanlar ? 'bg-amber-500/15 text-amber-300 border-amber-500/40' : 'bg-brand-input/60 text-gray-300 border-brand-border hover:text-gray-100'
          }`}>
          {eksigiOlanlar ? '✓ ' : ''}Eksiği olanlar
        </button>
      </div>

      {msg && (
        <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${
          msg.ok ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                 : 'bg-red-500/10 border-red-500/20 text-red-300'
        }`}>{msg.ok ? '✓ ' : '✗ '}{msg.text}</div>
      )}

      {loading && !order && <div className="text-gray-500 text-sm text-center py-16">Yükleniyor...</div>}

      {!loading && total === 0 && (
        <div className="card text-center py-16 text-gray-500">
          <div className="text-3xl mb-2">📦</div>
          {search || source || readyOnly || eksigiOlanlar
            ? 'Filtreyle eşleşen sipariş yok.'
            : 'Paketlenecek (gönderilmemiş) sipariş yok.'}
        </div>
      )}

      {order && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* SOL: urun gorselleri */}
          <div>
            <div className="grid grid-cols-2 gap-3">
              {order.items.map((it) => (
                <div key={it.line_item_id} className="card !p-0 overflow-hidden">
                  {/* Görsele tıkla = "hazırlandı, kenara ayrıldı". Sipariş eksik olsa
                      da hazırlanan kılıflar dükkanda ayrı duruyor; işaret o ayrımı
                      sistemde de gösteriyor. */}
                  <button type="button" onClick={() => ayrildiToggle(it)}
                    title={it.ayrildi ? 'Kenara ayrıldı — kaldırmak için tıkla' : 'Hazırlandı, kenara ayrıldı olarak işaretle'}
                    className="relative w-full aspect-square bg-brand-input/40 flex items-center justify-center overflow-hidden group">
                    {it.thumbnail_url
                      ? <img src={it.thumbnail_url} alt="" className="w-full h-full object-cover" />
                      : <div className="text-4xl opacity-30">📱</div>}
                    {it.ayrildi && (
                      <>
                        <span className="absolute inset-0 bg-emerald-500/20" />
                        <svg viewBox="0 0 40 40" className="absolute top-1.5 left-1.5 w-8 h-8 drop-shadow">
                          <circle cx="20" cy="20" r="17" fill="rgb(16 185 129 / 0.92)" />
                          <path d="M12 20.5 l5.5 5.5 L28 14" fill="none" stroke="white" strokeWidth="3.4"
                                strokeLinecap="round" strokeLinejoin="round"
                                className="tik-ciz" pathLength="1" />
                        </svg>
                      </>
                    )}
                    {!it.ayrildi && (
                      <span className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                    )}
                  </button>
                  <div className="flex items-center justify-between px-2.5 py-2 gap-2">
                    {/* Couple: kutuya İKİ kılıf giriyor — iki modeli de göster */}
                    {it.is_couple ? (
                      <div className="min-w-0 leading-tight">
                        <div className="text-[9px] text-accent/80 font-semibold tracking-wide">ÇİFT KILIF</div>
                        <div className="text-xs font-medium text-gray-200 truncate">1· {it.model || '—'}</div>
                        <div className="text-xs font-medium text-gray-200 truncate">2· {it.model_2 || '—'}</div>
                      </div>
                    ) : (
                      <span className="text-xs font-medium text-gray-200 truncate">{it.model || (it.title || '').slice(0, 22)}</span>
                    )}
                    <span className="text-[10px] px-2 py-0.5 rounded bg-accent/15 text-accent shrink-0 font-mono">
                      {it.kalip_kodu || '—'}{it.quantity > 1 ? ` ×${it.quantity}` : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* SAG: siparis detayi */}
          <div className="card !p-5 flex flex-col">
            <div className="text-center pb-3 border-b border-brand-border">
              <div className="text-2xl font-bold text-gray-100">
                {order.order_number} <span className="text-gray-500 text-lg font-normal">— {order.total_units} ADET</span>
              </div>
            </div>

            <div className="text-center py-4 border-b border-brand-border">
              <div className="text-xl font-semibold text-gray-100">{order.customer_name || '—'}</div>
              {order.address && <div className="text-sm text-gray-400 mt-2 leading-relaxed">{order.address}</div>}
              <div className="flex items-center justify-center gap-2 mt-2 text-sm text-gray-300">
                📍 {[order.district, order.province].filter(Boolean).join(' / ') || '—'}
              </div>
              {order.phone && <div className="text-base font-mono text-gray-200 mt-2">{order.phone}</div>}
              <div className="text-xs text-gray-500 mt-2">📅 Sipariş Tarihi: {fmtDate(order.created_at_platform)}</div>
            </div>

            {order.note && (
              <div className="py-3 border-b border-brand-border text-sm text-gray-300">
                <b className="text-gray-200">Sipariş Notu:</b> {order.note}
              </div>
            )}

            <div className="py-3 border-b border-brand-border text-sm text-gray-300">
              <b className="text-gray-200">KARGO ŞİRKETİ:</b> {order.kargo_sirketi || '—'}
            </div>

            {/* Asama (eski mor TAKIP butonu yerine) */}
            <div className="py-4 border-b border-brand-border">
              <div className="flex items-center justify-center gap-2 text-base font-semibold text-gray-100">
                <span className="text-xl">{stageEmoji(order.stage?.icon)}</span>
                {order.stage?.label || '—'}
                <span className="text-xs text-gray-500 font-normal">({order.stage?.no}/{queue.stages.length})</span>
              </div>
              <div className="mt-2 h-1.5 bg-brand-input rounded-full overflow-hidden">
                <div className="h-full bg-accent transition-all" style={{ width: `${order.progress_percent || 0}%` }} />
              </div>
            </div>

            {/* Butonlar */}
            <div className="space-y-2 py-4">
              <button onClick={downloadLabel} className="w-full btn-secondary !text-sm flex items-center justify-center gap-2">
                🖨 KARGO ETİKETİ YAZDIR
              </button>
              <button onClick={() => kargoGonder()} disabled={busy}
                className="w-full !text-sm flex items-center justify-center gap-2 rounded-lg py-2.5 font-medium bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50">
                {busy ? '⏳ GÖNDERİLİYOR…' : '🚚 KARGOYA VER'}
              </button>

              {labelPending && (
                <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 space-y-2">
                  <div className="text-xs text-amber-200">
                    ⚠ #{labelPending.order_number} <b>gönderildi</b> (Takip: {labelPending.takip_no}) ama barkod otomatik açılmadı. Yazdır, sonra "Sonraki"ye geç.
                  </div>
                  <button onClick={async () => {
                    const ok = await printKargoLabel(labelPending.id, null, labelPending.takip_no)
                    if (ok) setLabelPending(null)
                    else setMsg({ ok: false, text: 'Barkod hâlâ açılamadı — tarayıcının popup iznini ver ya da "🖨 KARGO ETİKETİ YAZDIR"ı dene.' })
                  }} className="w-full !text-sm rounded-lg py-2 font-medium bg-amber-600 hover:bg-amber-500 text-white">
                    🖨 Barkodu Yazdır
                  </button>
                </div>
              )}

              {manualAddr && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 space-y-2">
                  <div className="text-xs text-amber-300">Adresten il/ilçe çözülemedi — elle seç:</div>
                  <div className="flex gap-2">
                    <select value={selIl} onChange={e => { setSelIl(e.target.value); setSelIlce('') }}
                      className="input !text-sm flex-1">
                      <option value="">İl seç…</option>
                      {ilIlce && Object.keys(ilIlce).map(il => <option key={il} value={il}>{il}</option>)}
                    </select>
                    <select value={selIlce} onChange={e => setSelIlce(e.target.value)} disabled={!selIl}
                      className="input !text-sm flex-1 disabled:opacity-50">
                      <option value="">İlçe seç…</option>
                      {selIl && (ilIlce?.[selIl] || []).map(ic => <option key={ic} value={ic}>{ic}</option>)}
                    </select>
                  </div>
                  <button onClick={() => kargoGonder({ il: selIl, ilce: selIlce })}
                    disabled={busy || !selIl || !selIlce}
                    className="w-full !text-sm rounded-lg py-2 font-medium bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50">
                    {busy ? '⏳ Gönderiliyor…' : 'Seçili il/ilçe ile gönder'}
                  </button>
                </div>
              )}
            </div>

            {/* Navigasyon */}
            <div className="grid grid-cols-4 gap-1.5 sm:gap-2 mt-auto pt-3 border-t border-brand-border">
              <button onClick={() => go(0)} disabled={index === 0} className="btn-secondary !text-[10px] sm:!text-xs !px-1 sm:!px-3 disabled:opacity-30"><span className="hidden sm:inline">« </span>EN ESKİ</button>
              <button onClick={() => go(index - 1)} disabled={index === 0} className="btn-secondary !text-[10px] sm:!text-xs !px-1 sm:!px-3 disabled:opacity-30">‹ ÖNCEKİ</button>
              <button onClick={() => go(index + 1)} disabled={index >= total - 1} className="btn-secondary !text-[10px] sm:!text-xs !px-1 sm:!px-3 disabled:opacity-30">SONRAKİ ›</button>
              <button onClick={() => go(total - 1)} disabled={index >= total - 1} className="btn-secondary !text-[10px] sm:!text-xs !px-1 sm:!px-3 disabled:opacity-30">EN YENİ<span className="hidden sm:inline"> »</span></button>
            </div>
            <div className="text-center text-xs text-gray-500 mt-2">{index + 1} / {total}</div>
          </div>
        </div>
      )}
    </div>
  )
}
