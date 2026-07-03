import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

// Vitrin indirim kuponları — liste + oluştur/düzenle.
export default function KuponlarPage() {
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [coupons, setCoupons] = useState([])
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)   // null | 'new' | kupon objesi

  useEffect(() => {
    api.get('/api/stores').then(list => {
      const sf = (Array.isArray(list) ? list : []).filter(s => s.platform === 'storefront')
      setStores(sf)
      if (sf.length > 0) setStoreId(sf[0].id)
    }).catch(e => setError(e.detail || 'Mağazalar yüklenemedi'))
  }, [])

  const load = useCallback(async (sid) => {
    if (!sid) { setCoupons([]); return }
    try { setCoupons(await api.get(`/api/discounts?store_id=${sid}`)) }
    catch (e) { setError(typeof e?.detail === 'string' ? e.detail : 'Kuponlar yüklenemedi') }
  }, [])

  useEffect(() => { load(storeId) }, [storeId, load])

  const toggle = async (c) => {
    try { await api.patch(`/api/discounts/${c.id}`, { is_active: !c.is_active }); load(storeId) }
    catch { setError('Güncellenemedi') }
  }

  const remove = async (c) => {
    if (!window.confirm(`"${c.code}" kuponu silinecek. Emin misiniz?`)) return
    try { await api.del(`/api/discounts/${c.id}`); load(storeId) }
    catch { setError('Silinemedi') }
  }

  if (stores.length === 0) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold mb-3">Kuponlar</h1>
        <div className="bg-brand-card border border-brand-border rounded-xl p-6 text-sm text-gray-400">
          Kuponlar vitrin mağazaları içindir. Önce <b>Atölyeler</b>&apos;den bir
          &quot;Kendi Mağazam (Vitrin)&quot; mağazası ekleyin.
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Kuponlar</h1>
        <select value={storeId} onChange={e => setStoreId(e.target.value)}
          className="bg-brand-input border border-brand-border rounded-lg px-3 py-1.5 text-sm">
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button onClick={() => setEditing('new')}
          className="ml-auto px-3 py-1.5 rounded-lg text-sm font-medium text-black"
          style={{ background: 'rgb(var(--accent-rgb))' }}>
          + Yeni Kupon
        </button>
      </div>

      {error && <div className="text-sm text-red-400">{error}</div>}

      <div className="bg-brand-card border border-brand-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-gray-400 text-xs bg-brand-input">
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
              <tr key={c.id} className="border-t border-brand-border/50">
                <td className="px-4 py-2.5 font-mono font-semibold">{c.code}</td>
                <td className="px-4 py-2.5">{kindLabel(c)}</td>
                <td className="px-4 py-2.5 text-gray-400 text-xs">
                  {c.min_subtotal ? `min ${fmt(c.min_subtotal)}` : '—'}
                  {c.once_per_customer && ' · müşteri başına 1'}
                </td>
                <td className="px-4 py-2.5 tabular-nums">
                  {c.usage_count}{c.usage_limit ? ` / ${c.usage_limit}` : ''}
                </td>
                <td className="px-4 py-2.5 text-xs text-gray-400">{dateRange(c)}</td>
                <td className="px-4 py-2.5">
                  <button onClick={() => toggle(c)}
                    className={`text-xs px-2 py-0.5 rounded ${c.is_active
                      ? 'bg-emerald-600/30 text-emerald-300'
                      : 'bg-gray-600/40 text-gray-400'}`}>
                    {c.is_active ? 'Aktif' : 'Pasif'}
                  </button>
                </td>
                <td className="px-2 py-2.5 text-right whitespace-nowrap">
                  <button onClick={() => setEditing(c)} className="text-xs text-gray-400 hover:text-white px-1.5">Düzenle</button>
                  <button onClick={() => remove(c)} className="text-xs text-red-400/70 hover:text-red-400 px-1.5">Sil</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {coupons.length === 0 && (
          <div className="p-6 text-sm text-gray-400 text-center">Henüz kupon yok.</div>
        )}
      </div>

      {editing && (
        <CouponModal
          storeId={storeId}
          coupon={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(storeId) }}
        />
      )}
    </div>
  )
}

function fmt(v) {
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v))
}

function kindLabel(c) {
  if (c.kind === 'percent') return `%${Number(c.value)}`
  if (c.kind === 'amount') return fmt(c.value)
  return 'Ücretsiz kargo'
}

function dateRange(c) {
  const f = (s) => s ? new Date(s).toLocaleDateString('tr-TR') : null
  const a = f(c.starts_at), b = f(c.ends_at)
  if (!a && !b) return 'Süresiz'
  return `${a || '…'} → ${b || '…'}`
}

const inputCls = 'mt-1 w-full bg-brand-input border border-brand-border rounded-lg px-3 py-2 text-sm'

function CouponModal({ storeId, coupon, onClose, onSaved }) {
  const isNew = !coupon
  const [form, setForm] = useState(() => ({
    code: coupon?.code || '',
    kind: coupon?.kind || 'percent',
    value: coupon?.value || '',
    min_subtotal: coupon?.min_subtotal || '',
    starts_at: coupon?.starts_at ? coupon.starts_at.slice(0, 10) : '',
    ends_at: coupon?.ends_at ? coupon.ends_at.slice(0, 10) : '',
    usage_limit: coupon?.usage_limit || '',
    once_per_customer: coupon?.once_per_customer || false,
  }))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm(f => ({ ...f, [k]: v }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    const payload = {
      value: form.kind === 'free_shipping' ? 0 : Number(form.value),
      min_subtotal: form.min_subtotal ? Number(form.min_subtotal) : null,
      starts_at: form.starts_at ? `${form.starts_at}T00:00:00+03:00` : null,
      ends_at: form.ends_at ? `${form.ends_at}T23:59:59+03:00` : null,
      usage_limit: form.usage_limit ? Number(form.usage_limit) : null,
      once_per_customer: form.once_per_customer,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div className="bg-brand-card border border-brand-border rounded-2xl p-5 w-full max-w-md max-h-[85vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">{isNew ? 'Yeni Kupon' : `Kupon: ${coupon.code}`}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-lg leading-none">×</button>
        </div>
        <form onSubmit={submit} className="space-y-3">
          {isNew && (
            <label className="block text-sm">
              <span className="text-gray-400 text-xs">Kupon kodu</span>
              <input className={inputCls + ' font-mono uppercase'} value={form.code}
                onChange={set('code')} required minLength={2} maxLength={40}
                placeholder="HOSGELDIN10" />
            </label>
          )}
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="text-gray-400 text-xs">Tür</span>
              <select className={inputCls} value={form.kind} onChange={set('kind')} disabled={!isNew}>
                <option value="percent">Yüzde (%)</option>
                <option value="amount">Tutar (₺)</option>
                <option value="free_shipping">Ücretsiz kargo</option>
              </select>
            </label>
            {form.kind !== 'free_shipping' && (
              <label className="block text-sm">
                <span className="text-gray-400 text-xs">
                  {form.kind === 'percent' ? 'Yüzde (1-99)' : 'Tutar (₺)'}
                </span>
                <input className={inputCls} type="number" step="0.01" min="0.01"
                  max={form.kind === 'percent' ? 99 : undefined}
                  value={form.value} onChange={set('value')} required />
              </label>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="text-gray-400 text-xs">Min. sepet tutarı (₺, opsiyonel)</span>
              <input className={inputCls} type="number" step="0.01" min="0"
                value={form.min_subtotal} onChange={set('min_subtotal')} />
            </label>
            <label className="block text-sm">
              <span className="text-gray-400 text-xs">Kullanım limiti (opsiyonel)</span>
              <input className={inputCls} type="number" min="1"
                value={form.usage_limit} onChange={set('usage_limit')} />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="text-gray-400 text-xs">Başlangıç (opsiyonel)</span>
              <input className={inputCls} type="date" value={form.starts_at} onChange={set('starts_at')} />
            </label>
            <label className="block text-sm">
              <span className="text-gray-400 text-xs">Bitiş (opsiyonel)</span>
              <input className={inputCls} type="date" value={form.ends_at} onChange={set('ends_at')} />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input type="checkbox" checked={form.once_per_customer} onChange={set('once_per_customer')} />
            Müşteri başına yalnızca 1 kez kullanılabilsin
          </label>
          {err && <div className="text-sm text-red-400">{err}</div>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-gray-400">Vazgeç</button>
            <button disabled={busy} className="px-4 py-1.5 rounded-lg text-sm font-medium text-black disabled:opacity-50"
              style={{ background: 'rgb(var(--accent-rgb))' }}>
              {busy ? 'Kaydediliyor…' : isNew ? 'Oluştur' : 'Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
