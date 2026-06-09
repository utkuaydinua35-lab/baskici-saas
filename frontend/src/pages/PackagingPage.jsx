import { useEffect, useState, useCallback } from 'react'
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
  const { clock, h, m, passed } = useCargoCountdown()

  const loadIndex = useCallback(async (idx) => {
    setLoading(true); setMsg(null)
    try {
      const r = await api.get(`/api/packaging/queue?index=${idx}`)
      setQueue(r)
      try { localStorage.setItem(LAST_INDEX_KEY, String(r.index)) } catch {}
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Kuyruk yüklenemedi' })
    } finally { setLoading(false) }
  }, [])

  // ilk acilis: localStorage'daki son index (yoksa 0 = en eski)
  useEffect(() => {
    let start = 0
    try { const v = parseInt(localStorage.getItem(LAST_INDEX_KEY) || '0', 10); if (!isNaN(v) && v >= 0) start = v } catch {}
    loadIndex(start)
  }, [loadIndex])

  const total = queue.total || 0
  const index = queue.index || 0
  const order = queue.order
  const go = (idx) => { if (total === 0) return; const c = Math.max(0, Math.min(idx, total - 1)); loadIndex(c) }

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

  // base64 PDF -> hem indir hem yeni sekmede ac
  const openBarkodPdf = (b64, takipNo) => {
    try {
      const bin = atob(b64)
      const bytes = new Uint8Array(bin.length)
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
      const blob = new Blob([bytes], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `surat_barkod_${takipNo || 'etiket'}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      try { window.open(url, '_blank') } catch { /* popup engellendi */ }
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch { /* yok say */ }
  }

  const suratGonder = async () => {
    if (!order || busy) return
    if (!confirm(`#${order.order_number} siparişi Sürat Kargo ile gönderilecek. Onaylıyor musun?`)) return
    setBusy(true); setMsg(null)
    try {
      const r = await api.post(`/api/packaging/order/${encodeURIComponent(order.id)}/surat-gonder`, {})
      const tn = r.takip_no || '—'
      const extra = r.shopify_ok ? '' : ' (Shopify\'a yazılamadı, takip no panelde)'
      setMsg({ ok: true, text: `✅ Sürat gönderi oluştu · Takip No: ${tn} · Barkod indirildi${extra}` })
      if (r.barkod_base64) openBarkodPdf(r.barkod_base64, tn)
      setTimeout(() => loadIndex(index), 2500)
    } catch (e) {
      const t = typeof e?.detail === 'string' ? e.detail : 'Sürat gönderimi başarısız'
      const friendly = t.includes('İlçe belirlenemedi')
        ? `⚠ ${t} (Adreste ilçe yok — Shopify'da ilçeyi düzeltip tekrar deneyin.)`
        : t
      setMsg({ ok: false, text: friendly })
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
    <div className="max-w-[1400px]">
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
          KALAN PAKETLENECEK SİPARİŞ: <b className="text-gray-100">{total} ADET</b>
        </div>
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
          Paketlenecek (gönderilmemiş) sipariş yok.
        </div>
      )}

      {order && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* SOL: urun gorselleri */}
          <div>
            <div className="grid grid-cols-2 gap-3">
              {order.items.map((it) => (
                <div key={it.line_item_id} className="card !p-0 overflow-hidden">
                  <div className="aspect-square bg-brand-input/40 flex items-center justify-center overflow-hidden">
                    {it.thumbnail_url
                      ? <img src={it.thumbnail_url} alt="" className="w-full h-full object-cover" />
                      : <div className="text-4xl opacity-30">📱</div>}
                  </div>
                  <div className="flex items-center justify-between px-2.5 py-2 gap-2">
                    <span className="text-xs font-medium text-gray-200 truncate">{it.model || (it.title || '').slice(0, 22)}</span>
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
              <button onClick={suratGonder} disabled={busy}
                className="w-full !text-sm flex items-center justify-center gap-2 rounded-lg py-2.5 font-medium bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50">
                {busy ? '⏳ GÖNDERİLİYOR…' : '🚚 SÜRAT KARGO İLE GÖNDER'}
              </button>
            </div>

            {/* Navigasyon */}
            <div className="grid grid-cols-4 gap-2 mt-auto pt-3 border-t border-brand-border">
              <button onClick={() => go(0)} disabled={index === 0} className="btn-secondary !text-xs disabled:opacity-30">« EN ESKİ</button>
              <button onClick={() => go(index - 1)} disabled={index === 0} className="btn-secondary !text-xs disabled:opacity-30">‹ ÖNCEKİ</button>
              <button onClick={() => go(index + 1)} disabled={index >= total - 1} className="btn-secondary !text-xs disabled:opacity-30">SONRAKİ ›</button>
              <button onClick={() => go(total - 1)} disabled={index >= total - 1} className="btn-secondary !text-xs disabled:opacity-30">EN YENİ »</button>
            </div>
            <div className="text-center text-xs text-gray-500 mt-2">{index + 1} / {total}</div>
          </div>
        </div>
      )}
    </div>
  )
}
