import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Müşterilerin vitrindeki hesaplarından yükledikleri tasarım talepleri —
// incele, durum güncelle, not yaz (not müşterinin hesabında görünür).
const STATUSES = [
  { key: 'acik', label: 'Açık', cls: 'bg-amber-50 text-amber-700' },
  { key: 'incelendi', label: 'İncelendi', cls: 'bg-sky-50 text-sky-700' },
  { key: 'teklif', label: 'Teklif Verildi', cls: 'bg-indigo-50 text-indigo-700' },
  { key: 'tamam', label: 'Tamamlandı', cls: 'bg-emerald-50 text-emerald-700' },
  { key: 'red', label: 'Reddedildi', cls: 'bg-red-50 text-red-600' },
]
const STATUS_MAP = Object.fromEntries(STATUSES.map(s => [s.key, s]))

export default function TasarimTalepleriPage() {
  const { storeId } = useStore()
  const [tab, setTab] = useState('')
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [notes, setNotes] = useState({})       // id → taslak not
  const [lightbox, setLightbox] = useState(null)

  const load = useCallback(async () => {
    if (!storeId) return
    setError('')
    try {
      const qs = tab ? `&status=${tab}` : ''
      const r = await api.get(`/api/design-requests?store_id=${storeId}${qs}`)
      setItems(r.requests || [])
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Talepler yüklenemedi')
    }
  }, [storeId, tab])
  useEffect(() => { load() }, [load])

  const update = async (id, patch) => {
    setBusyId(id)
    try {
      const r = await api.patch(`/api/design-requests/${id}`, patch)
      if (patch.notify_customer) {
        setError(r.notified ? '' : 'Kaydedildi ama e-posta gönderilemedi (SMTP ayarlarını kontrol edin)')
      }
      await load()
    }
    catch (e) { setError(typeof e?.detail === 'string' ? e.detail : 'Güncellenemedi') }
    finally { setBusyId(null) }
  }

  return (
    <div className="max-w-4xl space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <h1 className="text-xl font-semibold mr-2">🎨 Tasarım Talepleri</h1>
        <button onClick={() => setTab('')}
          className={`px-3 py-1.5 rounded-xl text-xs border transition ${tab === ''
            ? 'border-panel-accent bg-emerald-50 text-emerald-700 font-medium'
            : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
          Tümü
        </button>
        {STATUSES.map(s => (
          <button key={s.key} onClick={() => setTab(s.key)}
            className={`px-3 py-1.5 rounded-xl text-xs border transition ${tab === s.key
              ? 'border-panel-accent bg-emerald-50 text-emerald-700 font-medium'
              : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
            {s.label}
          </button>
        ))}
      </div>
      <p className="text-xs text-panel-muted">
        Müşteriler vitrindeki hesaplarından kendi tasarımlarını yükleyip talep açar.
        Yazdığınız not müşterinin hesabında görünür — teklif ve yanıtları buradan iletin.
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="space-y-3">
        {items.map(r => {
          const st = STATUS_MAP[r.status] || STATUSES[0]
          const draft = notes[r.id] ?? (r.admin_note || '')
          return (
            <div key={r.id} className="card">
              <div className="flex gap-3">
                <button onClick={() => setLightbox(r.image_url)}
                  className="w-24 h-24 shrink-0 rounded-xl overflow-hidden border border-panel-border bg-panel-input"
                  title="Büyüt">
                  <img src={r.image_url} alt="" className="w-full h-full object-cover" />
                </button>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap text-sm">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${st.cls}`}>
                      {st.label}
                    </span>
                    <span className="font-medium">{r.customer_name || r.customer_email}</span>
                    {r.customer_name && (
                      <a href={`mailto:${r.customer_email}`}
                        className="text-xs text-panel-muted hover:underline">{r.customer_email}</a>
                    )}
                    {r.phone_model && (
                      <span className="text-xs text-panel-muted">📱 {r.phone_model}</span>
                    )}
                    <span className="text-xs text-panel-muted ml-auto">
                      {r.created_at ? new Date(r.created_at).toLocaleString('tr-TR') : ''}
                    </span>
                  </div>
                  {r.message && <p className="text-sm mt-1.5 text-panel-ink">{r.message}</p>}

                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <select value={r.status} disabled={busyId === r.id}
                      onChange={e => update(r.id, { status: e.target.value })}
                      className="input !w-auto !py-1.5 text-xs">
                      {STATUSES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                    </select>
                    <input value={draft} placeholder="Müşteriye not / teklif (hesabında görünür)"
                      onChange={e => setNotes(n => ({ ...n, [r.id]: e.target.value }))}
                      maxLength={2000}
                      className="input flex-1 !py-1.5 text-xs min-w-48" />
                    <button disabled={busyId === r.id || draft === (r.admin_note || '')}
                      onClick={() => update(r.id, { admin_note: draft })}
                      className="px-3 py-1.5 rounded-lg text-xs bg-emerald-50 text-emerald-700 disabled:opacity-40">
                      Notu Kaydet
                    </button>
                    <button disabled={busyId === r.id || (draft === (r.admin_note || '') && !draft)}
                      onClick={() => update(r.id, { admin_note: draft, notify_customer: true })}
                      title="Notu kaydet ve müşteriye durum+not e-postası gönder"
                      className="px-3 py-1.5 rounded-lg text-xs bg-emerald-600 text-white disabled:opacity-40">
                      📧 Kaydet + Bildir
                    </button>
                    <a href={r.image_url} download target="_blank" rel="noopener noreferrer"
                      className="px-3 py-1.5 rounded-lg text-xs border border-panel-border text-panel-muted hover:text-panel-ink">
                      ⬇ Görseli İndir
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
        {items.length === 0 && !error && (
          <div className="card text-center !p-8 text-sm text-panel-muted">
            {tab ? 'Bu durumda talep yok.' : 'Henüz tasarım talebi yok. Müşteriler vitrindeki “Hesabım” sayfasından talep açabilir.'}
          </div>
        )}
      </div>

      {/* Görsel büyütme */}
      {lightbox && (
        <div onClick={() => setLightbox(null)}
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-8 cursor-zoom-out">
          <img src={lightbox} alt="" className="max-w-full max-h-full rounded-xl shadow-2xl" />
        </div>
      )}
    </div>
  )
}
