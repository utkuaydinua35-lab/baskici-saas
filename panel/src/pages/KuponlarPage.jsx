import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { Modal } from './UrunlerPage'

// İndirim kuponları.
export default function KuponlarPage() {
  const { storeId } = useStore()
  const [coupons, setCoupons] = useState([])
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)   // null | 'new' | kupon

  const load = useCallback(async () => {
    if (!storeId) return
    try { setCoupons(await api.get(`/api/discounts?store_id=${storeId}`)) }
    catch (e) { setError(typeof e?.detail === 'string' ? e.detail : 'Kuponlar yüklenemedi') }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const toggle = async (c) => {
    try { await api.patch(`/api/discounts/${c.id}`, { is_active: !c.is_active }); load() }
    catch { setError('Güncellenemedi') }
  }
  const remove = async (c) => {
    if (!window.confirm(`"${c.code}" kuponu silinecek. Emin misiniz?`)) return
    try { await api.del(`/api/discounts/${c.id}`); load() }
    catch { setError('Silinemedi') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Kuponlar</h1>
        <button onClick={() => setEditing('new')} className="btn-primary ml-auto">+ Yeni Kupon</button>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-panel-muted text-xs bg-panel-input">
            <tr>
              <th className="text-left px-4 py-2.5">Kod</th>
              <th className="text-left px-4 py-2.5">İndirim</th>
              <th className="text-left px-4 py-2.5">Koşul</th>
              <th className="text-left px-4 py-2.5">Kullanım</th>
              <th className="text-left px-4 py-2.5">Geçerlilik</th>
              <th className="text-left px-4 py-2.5">Durum</th>
              <th className="px-2 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {coupons.map(c => (
              <tr key={c.id} className="border-t border-panel-border">
                <td className="px-4 py-2.5 font-mono font-semibold">
                  {c.code}
                  {c.is_automatic && (
                    <span className="ml-1.5 text-[10px] font-sans font-medium text-amber-300 bg-amber-500/10 px-1.5 py-0.5 rounded-full"
                      title="Kod gerekmez — koşulu sağlayan sepete otomatik uygulanır">⚡ otomatik</span>
                  )}
                </td>
                <td className="px-4 py-2.5">{kindLabel(c)}</td>
                <td className="px-4 py-2.5 text-panel-muted text-xs">
                  {[
                    c.min_subtotal && `min ${fmt(c.min_subtotal)}`,
                    c.min_quantity && `min ${c.min_quantity} adet`,
                    c.collection_id && 'koleksiyona özel',
                    c.once_per_customer && 'müşteri başına 1',
                  ].filter(Boolean).join(' · ') || '—'}
                </td>
                <td className="px-4 py-2.5 tabular-nums">
                  {c.usage_count}{c.usage_limit ? ` / ${c.usage_limit}` : ''}
                </td>
                <td className="px-4 py-2.5 text-xs text-panel-muted">{dateRange(c)}</td>
                <td className="px-4 py-2.5">
                  <button onClick={() => toggle(c)}
                    className={`text-xs px-2 py-0.5 rounded-full ${c.is_active
                      ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-500/15 text-slate-500'}`}>
                    {c.is_active ? 'Aktif' : 'Pasif'}
                  </button>
                </td>
                <td className="px-2 py-2.5 text-right whitespace-nowrap">
                  <button onClick={() => setEditing(c)} className="text-xs text-panel-muted hover:text-panel-ink px-1.5">Düzenle</button>
                  <button onClick={() => remove(c)} className="text-xs text-red-400 hover:text-red-400 px-1.5">Sil</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {coupons.length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">Henüz kupon yok.</div>
        )}
      </div>

      {editing && (
        <CouponModal storeId={storeId} coupon={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />
      )}
    </div>
  )
}

const fmt = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v))
const kindLabel = (c) => c.kind === 'percent' ? `%${Number(c.value)}`
  : c.kind === 'amount' ? fmt(c.value)
  : c.kind === 'bxgy' ? `${c.buy_x} Al ${c.pay_y} Öde`
  : 'Ücretsiz kargo'
function dateRange(c) {
  const f = (s) => s ? new Date(s).toLocaleDateString('tr-TR') : null
  const a = f(c.starts_at), b = f(c.ends_at)
  return (!a && !b) ? 'Süresiz' : `${a || '…'} → ${b || '…'}`
}

function CouponModal({ storeId, coupon, onClose, onSaved }) {
  const isNew = !coupon
  const [collections, setCollections] = useState([])
  useEffect(() => {
    api.get(`/api/catalog/collections?store_id=${storeId}`)
      .then(c => setCollections(c.filter(x => x.is_active))).catch(() => {})
  }, [storeId])
  const [form, setForm] = useState(() => ({
    code: coupon?.code || '',
    kind: coupon?.kind || 'percent',
    value: coupon?.value || '',
    min_subtotal: coupon?.min_subtotal || '',
    min_quantity: coupon?.min_quantity || '',
    starts_at: coupon?.starts_at ? coupon.starts_at.slice(0, 10) : '',
    ends_at: coupon?.ends_at ? coupon.ends_at.slice(0, 10) : '',
    usage_limit: coupon?.usage_limit || '',
    once_per_customer: coupon?.once_per_customer || false,
    is_automatic: coupon?.is_automatic || false,
    collection_id: coupon?.collection_id || '',
    buy_x: coupon?.buy_x || '',
    pay_y: coupon?.pay_y || '',
  }))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm(f => ({ ...f, [k]: v }))
  }

  // "10,5" gibi virgüllü girişler Number()'da NaN olur → noktaya çevir
  const num = (v) => Number(String(v).replace(',', '.'))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    const payload = {
      value: (form.kind === 'free_shipping' || form.kind === 'bxgy') ? 0 : num(form.value),
      min_subtotal: form.min_subtotal ? num(form.min_subtotal) : null,
      min_quantity: form.min_quantity ? num(form.min_quantity) : null,
      starts_at: form.starts_at ? `${form.starts_at}T00:00:00+03:00` : null,
      ends_at: form.ends_at ? `${form.ends_at}T23:59:59+03:00` : null,
      usage_limit: form.usage_limit ? num(form.usage_limit) : null,
      once_per_customer: form.once_per_customer,
      is_automatic: form.is_automatic,
      collection_id: form.collection_id || null,
      buy_x: form.kind === 'bxgy' ? Number(form.buy_x) : null,
      pay_y: form.kind === 'bxgy' ? Number(form.pay_y) : null,
    }
    try {
      if (isNew) {
        await api.post('/api/discounts', {
          ...payload, store_id: storeId, code: form.code.trim().toUpperCase(), kind: form.kind,
        })
      } else {
        await api.patch(`/api/discounts/${coupon.id}`, payload)
      }
      onSaved()
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  return (
    <Modal title={isNew ? 'Yeni Kupon' : `Kupon: ${coupon.code}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {isNew && (
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Kupon kodu</span>
            <input className="input mt-1 font-mono uppercase" value={form.code}
              onChange={set('code')} required minLength={2} maxLength={40}
              placeholder="HOSGELDIN10" />
          </label>
        )}
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Tür</span>
            <select className="input mt-1" value={form.kind} onChange={set('kind')} disabled={!isNew}>
              <option value="percent">Yüzde (%)</option>
              <option value="amount">Tutar (₺)</option>
              <option value="free_shipping">Ücretsiz kargo</option>
              <option value="bxgy">X Al Y Öde (örn 3 al 2 öde)</option>
            </select>
          </label>
          {form.kind === 'bxgy' && (
            <div className="flex items-end gap-2">
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">Al (X)</span>
                <input className="input mt-1 !w-16" type="number" min="2" max="100" required
                  value={form.buy_x} onChange={set('buy_x')} placeholder="3" />
              </label>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">Öde (Y)</span>
                <input className="input mt-1 !w-16" type="number" min="1" max="99" required
                  value={form.pay_y} onChange={set('pay_y')} placeholder="2" />
              </label>
              <span className="text-[11px] text-panel-muted pb-2.5">en ucuz {form.buy_x && form.pay_y ? form.buy_x - form.pay_y : 'X−Y'} ürün bedava</span>
            </div>
          )}
          {form.kind !== 'free_shipping' && form.kind !== 'bxgy' && (
            <label className="block text-sm">
              <span className="text-panel-muted text-xs">
                {form.kind === 'percent' ? 'Yüzde (1-99)' : 'Tutar (₺)'}
              </span>
              <input className="input mt-1" type="number" step="0.01" min="0.01"
                max={form.kind === 'percent' ? 99 : undefined}
                value={form.value} onChange={set('value')} required />
            </label>
          )}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Min. sepet (₺, ops.)</span>
            <input className="input mt-1" type="number" step="0.01" min="0"
              value={form.min_subtotal} onChange={set('min_subtotal')} />
          </label>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Kullanım limiti (ops.)</span>
            <input className="input mt-1" type="number" min="1"
              value={form.usage_limit} onChange={set('usage_limit')} />
          </label>
        </div>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Min. ürün adedi (ops. — örn "3 al %20")</span>
          <input className="input mt-1 !w-32" type="number" min="2" max="100"
            value={form.min_quantity} onChange={set('min_quantity')} />
        </label>
        {collections.length > 0 && (
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Yalnızca şu koleksiyonda geçerli (ops.)</span>
            <select className="input mt-1" value={form.collection_id} onChange={set('collection_id')}>
              <option value="">Tüm ürünler</option>
              {collections.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
            <span className="block text-[11px] text-panel-muted mt-0.5">
              İndirim yalnızca bu koleksiyondaki sepet kalemlerine uygulanır.
            </span>
          </label>
        )}
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Başlangıç (ops.)</span>
            <input className="input mt-1" type="date" value={form.starts_at} onChange={set('starts_at')} />
          </label>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Bitiş (ops.)</span>
            <input className="input mt-1" type="date" value={form.ends_at} onChange={set('ends_at')} />
          </label>
        </div>
        <p className="text-[11px] text-panel-muted -mt-1.5">
          İki tarih de boş bırakılırsa indirim <b>süresiz</b> geçerli olur.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.once_per_customer} onChange={set('once_per_customer')} />
          Müşteri başına yalnızca 1 kez kullanılabilsin
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={form.is_automatic} onChange={set('is_automatic')} />
          <span>
            ⚡ Otomatik uygula (kod gerekmez)
            <span className="block text-xs text-panel-muted">
              Koşulu sağlayan sepete kendiliğinden uygulanır; müşteri kod girerse girilen kod geçerli olur.
            </span>
          </span>
        </label>
        {err && <p className="text-sm text-red-400">{err}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button disabled={busy} className="btn-primary">
            {busy ? 'Kaydediliyor…' : isNew ? 'Oluştur' : 'Kaydet'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
