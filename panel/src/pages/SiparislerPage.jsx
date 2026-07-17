import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getToken } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import { Modal } from './UrunlerPage'

// Mağaza siparişleri — sade liste (üretim detayları Baskıcı'da kalır).
const STAGE_LABELS = {
  1: 'Yeni', 2: 'İşleniyor', 3: 'Barkod Oluştu', 4: 'Kalıba Alındı', 5: 'Baskıda',
  6: 'Baskı Tamam', 7: 'Paketlendi', 8: 'Kargoda', 9: 'Teslim',
}

export default function SiparislerPage() {
  const { storeId } = useStore()
  const [data, setData] = useState({ items: [], total: 0, page: 1, per_page: 50 })
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [draftOpen, setDraftOpen] = useState(false)
  const [selected, setSelected] = useState(new Set())  // toplu işlem seçimi
  const [showArchive, setShowArchive] = useState(false)
  const [bulkBusy, setBulkBusy] = useState(false)

  const load = useCallback(async () => {
    if (!storeId) return
    setLoading(true); setError('')
    try {
      const params = new URLSearchParams({ store_id: storeId, page: String(page) })
      if (search.trim()) params.set('search', search.trim())
      setData(await api.get(`/api/orders?${params}`))
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Siparişler yüklenemedi')
    } finally { setLoading(false) }
  }, [storeId, page, search])

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0)
    return () => clearTimeout(t)
  }, [load, search])

  const exportCsv = async () => {
    try {
      const res = await fetch(`/api/orders/export/orders.csv?store_id=${storeId}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) throw new Error()
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'siparisler.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch { setError('Dışa aktarma başarısız') }
  }

  const lastPage = Math.max(1, Math.ceil((data.total || 0) / (data.per_page || 50)))

  // Arşiv görünümü: internal_lists'te 'arsiv' olanlar; normal görünüm gizler
  const visible = (data.items || []).filter(o =>
    (o.internal_lists || []).includes('arsiv') === showArchive)
  const allChecked = visible.length > 0 && visible.every(o => selected.has(o.id))

  const toggleAll = () => {
    setSelected(allChecked ? new Set() : new Set(visible.map(o => o.id)))
  }
  const toggleOne = (id) => setSelected(s => {
    const n = new Set(s)
    if (n.has(id)) n.delete(id); else n.add(id)
    return n
  })

  // Toplu işlem — Baskıcı ile ortak /api/orders/_bulk ucu
  const bulk = async (action, value = null, confirmText = null) => {
    if (confirmText && !window.confirm(confirmText)) return
    setBulkBusy(true); setError('')
    try {
      await api.post('/api/orders/_bulk', { ids: [...selected], action, value })
      setSelected(new Set())
      await load()
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Toplu işlem başarısız')
    } finally { setBulkBusy(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Siparişler</h1>
        <span className="text-sm text-panel-muted">{data.total ?? 0} sipariş</span>
        <button onClick={() => { setShowArchive(a => !a); setSelected(new Set()) }}
          className={`px-2.5 py-1 rounded-full text-xs border transition ${showArchive
            ? 'border-panel-accent bg-emerald-500/10 text-emerald-300 font-medium'
            : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
          📦 Arşiv
        </button>
        <input value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
          placeholder="Sipariş no veya müşteri ara…" className="input !w-64 ml-auto" />
        <button onClick={exportCsv} className="btn-ghost text-xs">⬇ CSV</button>
        <button onClick={() => setDraftOpen(true)} className="btn-primary">＋ Sipariş Oluştur</button>
      </div>

      {draftOpen && <DraftOrderModal storeId={storeId} onClose={() => setDraftOpen(false)} />}

      {error && <p className="text-sm text-red-400">{error}</p>}

      {/* Toplu işlem çubuğu — seçim varken belirir (Shopify bulk bar) */}
      {selected.size > 0 && (
        <div className="card !py-2.5 flex items-center gap-2 flex-wrap toast-in">
          <span className="text-sm font-medium">{selected.size} sipariş seçili</span>
          {!showArchive ? (
            <button disabled={bulkBusy} onClick={() => bulk('list_add', 'arsiv')}
              className="btn-ghost !py-1.5 text-xs">📦 Arşivle</button>
          ) : (
            <button disabled={bulkBusy} onClick={() => bulk('list_remove', 'arsiv')}
              className="btn-ghost !py-1.5 text-xs">↩ Arşivden Çıkar</button>
          )}
          <button disabled={bulkBusy}
            onClick={() => bulk('delete', null,
              `${selected.size} sipariş çöp kutusuna taşınacak (geri alınabilir). Emin misiniz?`)}
            className="px-3 py-1.5 rounded-xl text-xs border border-red-500/30 text-red-300 bg-panel-card hover:bg-red-500/15 disabled:opacity-50">
            🗑 Sil
          </button>
          <button onClick={() => setSelected(new Set())}
            className="ml-auto text-xs text-panel-muted hover:text-panel-ink">Seçimi bırak</button>
        </div>
      )}

      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-panel-muted text-xs bg-panel-input">
            <tr>
              <th className="px-3 py-2.5 w-8">
                <input type="checkbox" checked={allChecked} onChange={toggleAll} />
              </th>
              <th className="text-left px-4 py-2.5">Sipariş</th>
              <th className="text-left px-4 py-2.5">Müşteri</th>
              <th className="text-right px-4 py-2.5">Tutar</th>
              <th className="text-left px-4 py-2.5">Tarih</th>
              <th className="text-left px-4 py-2.5">Ödeme</th>
              <th className="text-left px-4 py-2.5">Durum</th>
              <th className="px-2 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {visible.map(o => (
              <tr key={o.id} className={`border-t border-panel-border hover:bg-panel-input/50 ${
                selected.has(o.id) ? 'bg-emerald-500/10' : ''}`}>
                <td className="px-3 py-2.5">
                  <input type="checkbox" checked={selected.has(o.id)}
                    onChange={() => toggleOne(o.id)} />
                </td>
                <td className="px-4 py-2.5">
                  <Link to={`/siparisler/${o.id}`} className="font-mono font-medium hover:underline">
                    {o.name || `#${o.order_number}`}
                  </Link>
                </td>
                <td className="px-4 py-2.5">
                  <div>{o.customer_name || '—'}</div>
                  <div className="text-[11px] text-panel-muted">{o.item_count} kalem</div>
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                  {o.total_price ? new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(o.total_price)) : '—'}
                </td>
                <td className="px-4 py-2.5 text-xs text-panel-muted whitespace-nowrap">
                  {o.created_at_platform
                    ? new Date(o.created_at_platform).toLocaleString('tr-TR', {
                        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                </td>
                <td className="px-4 py-2.5"><FinancialBadge status={o.financial_status} /></td>
                <td className="px-4 py-2.5 text-xs">
                  {o.cancelled_at
                    ? <span className="text-red-400">İptal</span>
                    : <span>{STAGE_LABELS[o.current_stage] || '—'}</span>}
                </td>
                <td className="px-2 py-2.5 text-panel-muted">
                  <Link to={`/siparisler/${o.id}`}>›</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-4 text-sm text-panel-muted">Yükleniyor…</div>}
        {!loading && visible.length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">
            {showArchive ? 'Arşivde sipariş yok.'
              : search ? 'Sonuç bulunamadı.' : 'Henüz sipariş yok — ilk satışına az kaldı!'}
          </div>
        )}
      </div>

      {lastPage > 1 && (
        <div className="flex justify-center items-center gap-3 text-sm">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="btn-ghost !py-1">←</button>
          <span className="text-panel-muted">Sayfa {page} / {lastPage}</span>
          <button disabled={page >= lastPage} onClick={() => setPage(p => p + 1)} className="btn-ghost !py-1">→</button>
        </div>
      )}
    </div>
  )
}

export function FinancialBadge({ status }) {
  const map = {
    paid: ['Ödendi', 'bg-emerald-500/15 text-emerald-300'],
    refunded: ['İade Edildi', 'bg-red-500/15 text-red-300'],
    partially_refunded: ['Kısmi İade', 'bg-amber-500/15 text-amber-300'],
  }
  const [label, cls] = map[status] || [status || '—', 'bg-slate-500/15 text-slate-300']
  return <span className={`text-[11px] px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
}

// Taslak sipariş (Shopify draft order): sepeti panelden kur, müşteriye ödeme
// linki gönder — sipariş, müşteri linkten ödeyince normal akışla düşer.
function DraftOrderModal({ storeId, onClose }) {
  const toast = useToast()
  const [products, setProducts] = useState([])
  const [detail, setDetail] = useState(null)      // seçili ürünün varyantlı hali
  const [productId, setProductId] = useState('')
  const [variantId, setVariantId] = useState('')
  const [qty, setQty] = useState(1)
  const [lines, setLines] = useState([])          // {variant_id, label, unit_price, quantity}
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [sendEmail, setSendEmail] = useState(true)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)      // {payment_link, emailed, amount}

  useEffect(() => {
    api.get(`/api/catalog/products?store_id=${storeId}&status=active`)
      .then(setProducts).catch(() => toast.error('Ürünler yüklenemedi'))
  }, [storeId])

  useEffect(() => {
    setDetail(null); setVariantId('')
    if (!productId) return
    api.get(`/api/catalog/products/${productId}`)
      .then(d => { setDetail(d); setVariantId(d.variants?.find(v => v.is_active)?.id || '') })
      .catch(() => toast.error('Varyantlar yüklenemedi'))
  }, [productId])

  const addLine = () => {
    if (!detail || !variantId) return
    const v = detail.variants.find(x => x.id === variantId)
    const price = Number(v.price_override ?? detail.base_price)
    const label = `${detail.title} — ${v.model_display}${v.variation ? `, ${v.variation}` : ''}`
    setLines(ls => {
      const i = ls.findIndex(l => l.variant_id === variantId)
      if (i >= 0) return ls.map((l, j) => j === i ? { ...l, quantity: l.quantity + Number(qty) } : l)
      return [...ls, { variant_id: variantId, label, unit_price: price, quantity: Number(qty) }]
    })
    setQty(1)
  }

  const total = lines.reduce((t, l) => t + l.unit_price * l.quantity, 0)

  const submit = async (e) => {
    e.preventDefault()
    if (lines.length === 0) { toast.error('En az bir ürün ekleyin'); return }
    setBusy(true)
    try {
      const r = await api.post('/api/checkout-sessions/draft', {
        store_id: storeId,
        items: lines.map(l => ({ variant_id: l.variant_id, quantity: l.quantity })),
        customer_name: name.trim(),
        email: email.trim(),
        send_email: sendEmail,
      })
      setResult(r)
      toast.success(r.emailed ? 'Taslak oluşturuldu, ödeme linki e-postalandı'
        : 'Taslak oluşturuldu — linki kopyalayıp iletebilirsiniz')
    } catch (e2) {
      toast.error(typeof e2?.detail === 'string' ? e2.detail : 'Taslak oluşturulamadı')
    } finally { setBusy(false) }
  }

  const copy = async () => {
    try { await navigator.clipboard.writeText(result.payment_link); toast.success('Link kopyalandı') }
    catch { toast.error('Kopyalanamadı') }
  }

  if (result) {
    return (
      <Modal title="Taslak sipariş hazır 🧾" onClose={onClose}>
        <div className="space-y-3 text-sm">
          <p>Toplam <b>{fmtTL(result.amount)}</b> (kargo dahil).
            {result.emailed ? ' Ödeme linki müşteriye e-postalandı.' : ' Linki müşteriye iletin:'}</p>
          <div className="flex gap-2">
            <input readOnly value={result.payment_link} className="input font-mono text-xs flex-1"
              onFocus={e => e.target.select()} />
            <button onClick={copy} className="btn-ghost whitespace-nowrap">Kopyala</button>
          </div>
          <p className="text-xs text-panel-muted">
            Link 30 gün geçerli. Müşteri ödeyince sipariş normal akışla listeye düşer.
            Taslaklar Terk Sepetler → Taslaklar sekmesinde görünür.
          </p>
          <div className="flex justify-end"><button onClick={onClose} className="btn-primary">Tamam</button></div>
        </div>
      </Modal>
    )
  }

  return (
    <Modal title="Sipariş Oluştur" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-[1fr_1fr_64px_auto] gap-2 items-end">
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Ürün</span>
            <select className="input mt-1" value={productId} onChange={e => setProductId(e.target.value)}>
              <option value="">Seçin…</option>
              {products.map(pr => <option key={pr.id} value={pr.id}>{pr.title}</option>)}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Varyant</span>
            <select className="input mt-1" value={variantId} onChange={e => setVariantId(e.target.value)}
              disabled={!detail}>
              {(detail?.variants || []).filter(v => v.is_active).map(v => (
                <option key={v.id} value={v.id}>
                  {v.model_display}{v.variation ? ` · ${v.variation}` : ''} — {fmtTL(v.price_override ?? detail.base_price)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Adet</span>
            <input className="input mt-1" type="number" min="1" max="100" value={qty}
              onChange={e => setQty(e.target.value)} />
          </label>
          <button type="button" onClick={addLine} disabled={!variantId} className="btn-ghost">Ekle</button>
        </div>

        {lines.length > 0 && (
          <div className="border border-panel-border rounded-xl divide-y divide-panel-border">
            {lines.map((l, i) => (
              <div key={l.variant_id} className="flex items-center gap-2 px-3 py-2 text-sm">
                <span className="flex-1 min-w-0 truncate">{l.label}</span>
                <span className="tabular-nums text-panel-muted">×{l.quantity}</span>
                <span className="tabular-nums font-medium">{fmtTL(l.unit_price * l.quantity)}</span>
                <button type="button" onClick={() => setLines(ls => ls.filter((_, j) => j !== i))}
                  className="text-red-400 hover:text-red-400 px-1">×</button>
              </div>
            ))}
            <div className="flex justify-between px-3 py-2 text-sm font-semibold">
              <span>Ürün toplamı</span><span>{fmtTL(total)}</span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Müşteri adı</span>
            <input className="input mt-1" required minLength={2} value={name}
              onChange={e => setName(e.target.value)} placeholder="Ad Soyad" />
          </label>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">E-posta</span>
            <input className="input mt-1" type="email" required value={email}
              onChange={e => setEmail(e.target.value)} placeholder="musteri@ornek.com" />
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={sendEmail} onChange={e => setSendEmail(e.target.checked)} />
          Ödeme linkini müşteriye e-postala
        </label>
        <p className="text-xs text-panel-muted">
          Kargo, mağaza ayarlarındaki kurala göre eklenir; müşteri linkten güvenli ödeme sayfasında öder.
        </p>
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button disabled={busy || lines.length === 0} className="btn-primary">
            {busy ? 'Oluşturuluyor…' : 'Taslak Oluştur'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

const fmtTL = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v || 0))
