import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

export default function DealersPage() {
  const toast = useToast()
  const [dealers, setDealers] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)   // {} yeni, obj duzenle, null kapali
  const [detail, setDetail] = useState(null)      // cari detay acilan bayi

  const load = async () => {
    setLoading(true)
    try { const d = await api.get('/api/dealers'); setDealers(Array.isArray(d) ? d : []) }
    catch { toast.error('Bayiler yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const fmt = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0)

  return (
    <div className="max-w-5xl animate-fadein">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-5">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🤝 Bayiler</h1>
          <p className="text-sm text-gray-500 mt-1">B2B müşteriler ve cari hesaplar</p>
        </div>
        <button onClick={() => setEditing({})} className="btn-primary">+ Bayii Ekle</button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[0,1,2].map(i => <div key={i} className="card !py-4"><div className="skeleton h-4 w-40 mb-2 rounded" /><div className="skeleton h-3 w-24 rounded" /></div>)}
        </div>
      ) : dealers.length === 0 ? (
        <div className="card text-center py-12 text-gray-500"><div className="text-3xl mb-2">🤝</div>Henüz bayii yok.</div>
      ) : (
        <div className="space-y-2 stagger">
          {dealers.filter(d => d.is_active).map(d => (
            <div key={d.id} className="card !py-3.5 flex items-center gap-3 flex-wrap">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-gray-100">{d.name}</div>
                <div className="text-xs text-gray-500">{d.phone || '—'}{d.email ? ` · ${d.email}` : ''}</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-gray-500">BAKİYE</div>
                <div className={`text-sm font-bold tabular-nums ${d.balance > 0 ? 'text-red-300' : d.balance < 0 ? 'text-emerald-300' : 'text-gray-300'}`}>
                  {fmt(d.balance)}
                </div>
              </div>
              <div className="flex gap-1.5">
                <button onClick={() => setDetail(d)} className="btn-secondary !text-xs">Cari</button>
                <button onClick={() => setEditing(d)} className="btn-secondary !text-xs">Düzenle</button>
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="text-[11px] text-gray-600 mt-3">Bakiye: <span className="text-red-300">kırmızı</span> = bayi borçlu, <span className="text-emerald-300">yeşil</span> = alacaklı.</p>

      {editing && <DealerDialog dealer={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
      {detail && <CariDialog dealer={detail} onClose={() => setDetail(null)} onChanged={load} />}
    </div>
  )
}

function DealerDialog({ dealer, onClose, onSaved }) {
  const toast = useToast()
  const isNew = !dealer.id
  const [f, setF] = useState({
    name: dealer.name || '', phone: dealer.phone || '', email: dealer.email || '',
    address: dealer.address || '', note: dealer.note || '',
  })
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF(s => ({ ...s, [k]: e.target.value }))

  const save = async () => {
    if (!f.name.trim()) { toast.error('İsim gerekli'); return }
    setBusy(true)
    try {
      if (isNew) await api.post('/api/dealers', f)
      else await api.patch(`/api/dealers/${dealer.id}`, f)
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
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? '…' : 'Kaydet'}</button>
        </div>
      </div>
    </div>
  )
}

function CariDialog({ dealer, onClose, onChanged }) {
  const toast = useToast()
  const [txs, setTxs] = useState([])
  const [loading, setLoading] = useState(true)
  const [amount, setAmount] = useState('')
  const [desc, setDesc] = useState('')
  const [busy, setBusy] = useState(false)
  const [bal, setBal] = useState(dealer.balance)

  const fmt = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0)

  const load = async () => {
    setLoading(true)
    try { const t = await api.get(`/api/dealers/${dealer.id}/transactions`); setTxs(Array.isArray(t) ? t : []) }
    catch { toast.error('Hareketler yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const pay = async (direction) => {
    const amt = parseFloat(amount)
    if (!amt || amt <= 0) { toast.error('Geçerli tutar gir'); return }
    setBusy(true)
    try {
      const d = await api.post(`/api/dealers/${dealer.id}/payment`, {
        amount: amt, kind: direction === 'payment' ? 'odeme' : 'duzeltme',
        description: desc || (direction === 'payment' ? 'Ödeme alındı' : 'Borç eklendi'), direction,
      })
      setBal(d.balance); setAmount(''); setDesc(''); load(); onChanged?.()
      toast.success(direction === 'payment' ? 'Ödeme işlendi' : 'Borç eklendi')
    } catch (e) { toast.error('İşlenemedi') } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-100">{dealer.name} — Cari Hesap</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        <div className="mb-4">
          <span className="text-xs text-gray-500">Güncel bakiye: </span>
          <span className={`text-base font-bold tabular-nums ${bal > 0 ? 'text-red-300' : bal < 0 ? 'text-emerald-300' : 'text-gray-300'}`}>{fmt(bal)}</span>
          <span className="text-[11px] text-gray-600 ml-2">{bal > 0 ? '(bayi borçlu)' : bal < 0 ? '(alacaklı)' : ''}</span>
        </div>

        <div className="bg-brand-input/40 rounded-lg p-3 mb-4">
          <div className="flex gap-2 mb-2">
            <input className="input flex-1" type="number" inputMode="decimal" placeholder="Tutar ₺" value={amount} onChange={e => setAmount(e.target.value)} />
            <input className="input flex-1" placeholder="Açıklama (ops.)" value={desc} onChange={e => setDesc(e.target.value)} />
          </div>
          <div className="flex gap-2">
            <button onClick={() => pay('payment')} disabled={busy} className="flex-1 rounded-lg py-2 text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50">💰 Ödeme Al</button>
            <button onClick={() => pay('debt')} disabled={busy} className="flex-1 btn-secondary !text-sm">＋ Borç Ekle</button>
          </div>
        </div>

        <div className="text-xs text-gray-500 mb-2">Hareketler</div>
        {loading ? <div className="text-sm text-gray-500 py-4 text-center">Yükleniyor…</div>
          : txs.length === 0 ? <div className="text-sm text-gray-600 py-4 text-center">Hareket yok.</div>
          : (
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {txs.map(t => (
                <div key={t.id} className="flex items-center justify-between text-sm py-1.5 border-b border-brand-border/40">
                  <div className="min-w-0">
                    <div className="text-gray-300 truncate">{t.description || t.kind}</div>
                    <div className="text-[10px] text-gray-600">{t.created_at ? new Date(t.created_at).toLocaleString('tr-TR') : ''}</div>
                  </div>
                  <div className={`tabular-nums font-medium ${t.amount > 0 ? 'text-red-300' : 'text-emerald-300'}`}>
                    {t.amount > 0 ? '+' : ''}{fmt(t.amount)}
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  )
}
