import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

export default function BayiYonetim() {
  const toast = useToast()
  const [dealers, setDealers] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)

  const load = async () => {
    setLoading(true)
    try { const d = await api.get('/api/dealers'); setDealers(Array.isArray(d) ? d : []) }
    catch { toast.error('Bayiler yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const fmt = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0)

  const remove = async (d) => {
    if (!confirm(`"${d.name}" bayisini silmek istiyor musun? Cari hesabı ve siparişleri korunur ama listeden kaldırılır.`)) return
    try { await api.del(`/api/dealers/${d.id}`); toast.success('Bayii silindi'); load() }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Silinemedi') }
  }

  return (
    <div className="animate-fadein -mt-2">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">Bayi ekle, düzenle, fiyat ve kargo ayarla. Sipariş girişi Bayiler sayfasından yapılır.</p>
        <button onClick={() => setEditing({})} className="btn-primary !text-sm whitespace-nowrap">+ Bayii Ekle</button>
      </div>

      {loading ? (
        <div className="space-y-2">{[0,1,2].map(i => <div key={i} className="card !py-4"><div className="skeleton h-4 w-40 mb-2 rounded" /><div className="skeleton h-3 w-24 rounded" /></div>)}</div>
      ) : dealers.filter(d => d.is_active).length === 0 ? (
        <div className="card text-center py-10 text-gray-500"><div className="text-3xl mb-2">🤝</div>Henüz bayii yok.</div>
      ) : (
        <div className="space-y-2">
          {dealers.filter(d => d.is_active).map(d => (
            <div key={d.id} className="card !py-3.5 flex items-center gap-3 flex-wrap">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-gray-100">{d.name}</div>
                <div className="text-xs text-gray-500">{d.phone || '—'}{d.email ? ` · ${d.email}` : ''}</div>
              </div>
              <div className="text-right text-xs">
                <div className="text-gray-400">Birim: <span className="text-gray-200 font-medium">{fmt(d.unit_price)}</span></div>
                <div className="text-gray-500">Kargo: {d.shipping_fee > 0 ? fmt(d.shipping_fee) : 'Yok'}</div>
              </div>
              <div className="flex gap-1.5">
                <button onClick={() => setEditing(d)} className="btn-secondary !text-xs">Düzenle</button>
                <button onClick={() => remove(d)} className="!text-xs px-2 py-1 rounded-lg text-red-300 hover:bg-red-500/10 border border-red-500/20">Sil</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && <BayiDialog dealer={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
    </div>
  )
}

function BayiDialog({ dealer, onClose, onSaved }) {
  const toast = useToast()
  const isNew = !dealer.id
  const [f, setF] = useState({
    name: dealer.name || '', phone: dealer.phone || '', email: dealer.email || '',
    address: dealer.address || '', note: dealer.note || '',
    unit_price: dealer.unit_price ?? '', shipping_fee: dealer.shipping_fee ?? '',
  })
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF(s => ({ ...s, [k]: e.target.value }))

  const save = async () => {
    if (!f.name.trim()) { toast.error('İsim gerekli'); return }
    setBusy(true)
    try {
      const payload = {
        ...f,
        unit_price: f.unit_price === '' ? 0 : Number(f.unit_price),
        shipping_fee: f.shipping_fee === '' ? 0 : Number(f.shipping_fee),
      }
      if (isNew) await api.post('/api/dealers', payload)
      else await api.patch(`/api/dealers/${dealer.id}`, payload)
      toast.success(isNew ? 'Bayii eklendi' : 'Güncellendi')
      onSaved()
    } catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">{isNew ? 'Yeni Bayii' : 'Bayiyi Düzenle'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {[['name','İsim *'],['phone','Telefon'],['email','E-posta'],['address','Adres'],['note','Not']].map(([k,lbl]) => (
          <label key={k} className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{lbl}</span>
            {k === 'address' || k === 'note'
              ? <textarea className="input w-full" rows={2} value={f[k]} onChange={set(k)} />
              : <input className="input w-full" value={f[k]} onChange={set(k)} />}
          </label>
        ))}
        <div className="grid grid-cols-2 gap-3 mb-2">
          <label className="block"><span className="block text-xs text-gray-400 mb-1">Birim Fiyat ₺ *</span>
            <input className="input w-full" type="number" inputMode="decimal" min="0" step="0.01" value={f.unit_price} onChange={set('unit_price')} placeholder="örn. 120" />
          </label>
          <label className="block"><span className="block text-xs text-gray-400 mb-1">Kargo ₺ (0 = yok)</span>
            <input className="input w-full" type="number" inputMode="decimal" min="0" step="0.01" value={f.shipping_fee} onChange={set('shipping_fee')} placeholder="örn. 93" />
          </label>
        </div>
        <p className="text-[11px] text-gray-600 mb-3">Birim fiyat: ürün başına bayi fiyatı. Kargo sipariş başına eklenir (0 ise eklenmez).</p>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? '…' : 'Kaydet'}</button>
        </div>
      </div>
    </div>
  )
}
