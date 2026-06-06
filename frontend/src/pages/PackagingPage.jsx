import { useEffect, useState } from 'react'
import { api, getToken } from '../lib/api'

export default function PackagingPage() {
  const [ref, setRef] = useState('')
  const [data, setData] = useState(null)
  const [stock, setStock] = useState([])
  const [rows, setRows] = useState([])      // [{stock_item_id, quantity}]
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [result, setResult] = useState(null)

  const loadStock = async () => {
    try {
      const r = await api.get('/api/stock')
      setStock((r.items || []).filter(i => i.is_active))
    } catch { setStock([]) }
  }
  useEffect(() => { loadStock() }, [])

  const fetchOrder = async () => {
    if (!ref.trim()) return
    setLoading(true); setMsg(null); setResult(null); setData(null)
    try {
      const r = await api.get(`/api/packaging/order/${encodeURIComponent(ref.trim())}`)
      setData(r)
      // önerilerden başlangıç düşüm satırları (eşleşeni olanlar)
      const init = (r.suggestions || [])
        .filter(s => s.suggested_stock_item_id)
        .map(s => ({ stock_item_id: s.suggested_stock_item_id, quantity: s.quantity || 1 }))
      setRows(init)
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Sipariş bulunamadı' })
    } finally { setLoading(false) }
  }

  const addRow = () => setRows(r => [...r, { stock_item_id: '', quantity: 1 }])
  const setRow = (i, patch) => setRows(r => r.map((x, idx) => idx === i ? { ...x, ...patch } : x))
  const delRow = (i) => setRows(r => r.filter((_, idx) => idx !== i))

  const downloadLabel = async () => {
    const r = ref.trim()
    const res = await fetch(`/api/packaging/order/${encodeURIComponent(r)}/label`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) { setMsg({ ok: false, text: 'Etiket üretilemedi' }); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 30000)
  }

  const printAndComplete = async () => {
    setBusy(true); setMsg(null); setResult(null)
    try {
      const deductions = rows
        .filter(x => x.stock_item_id && x.quantity > 0)
        .map(x => ({ stock_item_id: x.stock_item_id, quantity: parseInt(x.quantity, 10) }))
      const r = await api.post(`/api/packaging/order/${encodeURIComponent(ref.trim())}/complete`, { deductions })
      setResult(r)
      await downloadLabel()
      // veriyi tazele
      const fresh = await api.get(`/api/packaging/order/${encodeURIComponent(ref.trim())}`)
      setData(fresh)
      loadStock()
      setMsg({
        ok: true,
        text: r.already
          ? 'Bu sipariş zaten paketlenmişti — etiket yeniden yazdırıldı (stok tekrar düşmedi).'
          : `Paketlendi · ${r.deducted} stok düşüldü${r.shortages?.length ? `, ${r.shortages.length} eksik` : ''}.`,
      })
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'İşlem başarısız' })
    } finally { setBusy(false) }
  }

  const stockName = id => {
    const s = stock.find(x => x.id === id)
    return s ? `${s.name} (${s.sku}) · ${s.quantity} adet` : ''
  }

  return (
    <div className="max-w-[1100px]">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">🏷️ Paketleme</h1>
        <p className="text-sm text-gray-500 mt-1">
          Sipariş no veya barkod oku → içindekileri ve aksesuarları onayla → kargo etiketi
          yazdır. Etiket yazdırınca sipariş "Paketlendi" olur, aksesuar stoğu düşer.
        </p>
      </div>

      <div className="card mb-4 flex flex-wrap gap-2 !p-3">
        <input
          type="text"
          placeholder="Sipariş no / barkod (ör: #1234)"
          value={ref}
          onChange={e => setRef(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && fetchOrder()}
          className="input !text-sm flex-1 min-w-[220px]"
          autoFocus
        />
        <button onClick={fetchOrder} disabled={loading} className="btn-secondary !text-sm disabled:opacity-50">
          {loading ? 'Getiriliyor...' : 'Getir'}
        </button>
      </div>

      {msg && (
        <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${
          msg.ok ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                 : 'bg-red-500/10 border-red-500/20 text-red-300'
        }`}>{msg.ok ? '✓ ' : '✗ '}{msg.text}</div>
      )}

      {result?.shortages?.length > 0 && (
        <div className="text-sm rounded-lg px-3 py-2 mb-3 border bg-amber-500/10 border-amber-500/30 text-amber-300">
          ⚠ Yetersiz/eksik stok (paketleme yine de tamamlandı):
          <ul className="mt-1 text-xs list-disc list-inside">
            {result.shortages.map((s, i) => (
              <li key={i}>{s.name || s.sku || s.stock_item_id} — gereken {s.need}{s.deducted != null ? `, düşülen ${s.deducted}` : ''} ({s.reason})</li>
            ))}
          </ul>
        </div>
      )}

      {data && (
        <>
          <div className="card mb-4 !p-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <div className="text-lg font-semibold text-gray-100">
                  {data.order.name || data.order.order_number}
                  {data.is_packaged && (
                    <span className="ml-2 text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                      Paketlendi
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-500">
                  {data.order.customer_name || '—'} · {data.order.store_name || ''}
                  {data.order.barkod_kodu ? ` · barkod: ${data.order.barkod_kodu}` : ''}
                </div>
              </div>
            </div>
          </div>

          <div className="card mb-4 !p-0 overflow-hidden">
            <div className="px-3 py-2 border-b border-brand-border text-xs text-gray-500 bg-brand-input">
              Sipariş İçeriği
            </div>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-brand-border/50">
                {(data.suggestions || []).map(s => (
                  <tr key={s.line_item_id}>
                    <td className="px-3 py-2 text-gray-200">
                      {s.title}
                      {s.variant_title && <span className="text-gray-500 text-xs"> · {s.variant_title}</span>}
                      {s.is_kaliba_eklendi && <span className="ml-2 text-[10px] text-gray-500">(kalıpta basıldı)</span>}
                    </td>
                    <td className="px-3 py-2 text-center text-gray-400 w-16">×{s.quantity}</td>
                    <td className="px-3 py-2 text-xs text-gray-500 w-48">
                      {s.suggested_stock_item_id
                        ? <span className="text-emerald-400">→ {s.suggested_name}</span>
                        : <span className="text-gray-600">stok eşleşmesi yok</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card mb-4 !p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-200">Düşülecek Stok (aksesuar/diğer)</h3>
              <button onClick={addRow} className="text-xs text-accent hover:underline">+ kalem ekle</button>
            </div>
            <p className="text-[11px] text-gray-500 mb-3">
              Boş kılıf kalıp basımında düştüğü için burada görünmez. Sadece ekran/lens koruyucu
              ve diğer aksesuarları düş.
            </p>
            {rows.length === 0 && <div className="text-xs text-gray-600 py-2">Düşülecek aksesuar yok.</div>}
            <div className="space-y-2">
              {rows.map((row, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <select
                    value={row.stock_item_id}
                    onChange={e => setRow(i, { stock_item_id: e.target.value })}
                    className="input !text-xs !py-1.5 flex-1"
                  >
                    <option value="">— stok kalemi seç —</option>
                    {stock.map(s => (
                      <option key={s.id} value={s.id}>{s.name} ({s.sku}) · {s.quantity} adet</option>
                    ))}
                  </select>
                  <input
                    type="number" min="1" value={row.quantity}
                    onChange={e => setRow(i, { quantity: e.target.value })}
                    className="input !text-xs !py-1.5 w-20"
                  />
                  <button onClick={() => delRow(i)} className="w-7 h-7 flex items-center justify-center text-red-400/70 hover:text-red-300 hover:bg-red-500/10 rounded">×</button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <button onClick={downloadLabel} className="btn-secondary !text-sm">Sadece Etiketi Yazdır</button>
            <button onClick={printAndComplete} disabled={busy} className="btn-primary !text-sm disabled:opacity-50">
              {busy ? 'İşleniyor...' : '🏷️ Kargo Etiketi Yazdır (Paketle)'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
