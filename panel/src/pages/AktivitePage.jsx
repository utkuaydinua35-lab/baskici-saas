import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Aktivite günlüğü — "kim, ne zaman, neyi değiştirdi".
// Sipariş aşama geçmişi sipariş detayındaki zaman akışında kalır; burası
// katalog/ayar tarafı + para iadesi ve kargo gönderileri içindir.
const ICONS = {
  urun_ekle: '🛍️', urun_guncelle: '✏️', urun_sil: '🗑️', urun_toplu: '📋',
  urun_ice_aktar: '📥', koleksiyon_ekle: '🗂️', koleksiyon_guncelle: '🗂️',
  koleksiyon_sil: '🗑️', kupon_ekle: '🎟️', kupon_guncelle: '🎟️', kupon_sil: '🗑️',
  ayar_guncelle: '⚙️', tema_yayinla: '🎨', iade: '↩️',
  kargo_gonderi: '📦', kargo_geri: '↩️', siparis_duzenle: '✏️',
}
// Detay sözlüğündeki teknik alan adlarını okunur yap
const FIELD_LABELS = {
  title: 'Ad', status: 'Durum', base_price: 'Fiyat', compare_at_price: 'İndirim öncesi',
  cost_price: 'Maliyet', tags: 'Etiketler', slug: 'URL', value: 'Değer',
  is_active: 'Aktiflik', is_automatic: 'Otomatik', combinable: 'Birleşebilir',
  usage_limit: 'Kullanım limiti', min_subtotal: 'Min. sepet', ends_at: 'Bitiş',
  alanlar: 'Değişen ayarlar', tutar: 'Tutar', takip_no: 'Takip no', firma: 'Kargo',
  adet: 'Adet', akilli: 'Akıllı koleksiyon', sebep: 'Sebep', tam: 'Tam iade',
}
const RANGES = [{ d: 7, l: '7 gün' }, { d: 30, l: '30 gün' }, { d: 90, l: '90 gün' }]

export default function AktivitePage() {
  const { storeId } = useStore()
  const [items, setItems] = useState([])
  const [meta, setMeta] = useState({ actions: [], users: [] })
  const [days, setDays] = useState(30)
  const [action, setAction] = useState('')
  const [who, setWho] = useState('')
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!storeId) return
    api.get(`/api/store-activity/_meta?store_id=${storeId}`).then(setMeta).catch(() => {})
  }, [storeId])

  const load = useCallback(async () => {
    if (!storeId) return
    setLoading(true); setErr('')
    const q = new URLSearchParams({ store_id: storeId, days, page })
    if (action) q.set('action', action)
    if (who) q.set('user_email', who)
    try {
      const r = await api.get(`/api/store-activity?${q}`)
      setItems(r.items); setHasMore(r.has_more)
    } catch {
      setErr('Aktivite yüklenemedi')
    } finally { setLoading(false) }
  }, [storeId, days, page, action, who])
  useEffect(() => { load() }, [load])

  // Filtre değişince ilk sayfaya dön
  useEffect(() => { setPage(1) }, [days, action, who])

  const gruplar = groupByDay(items)

  return (
    <div className="space-y-4 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">Aktivite</h1>
        <p className="text-xs text-panel-muted mt-0.5">
          Mağazada yapılan değişikliklerin kaydı. Siparişlerin aşama geçmişi
          sipariş detayındaki zaman akışındadır.
        </p>
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        {RANGES.map(r => (
          <button key={r.d} onClick={() => setDays(r.d)}
            className={`px-3 py-1.5 rounded-xl text-xs border transition ${days === r.d
              ? 'border-panel-accent bg-emerald-500/10 text-emerald-300 font-medium'
              : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
            {r.l}
          </button>
        ))}
        <select className="input !py-1.5 !w-auto text-xs ml-auto" value={action}
          onChange={e => setAction(e.target.value)}>
          <option value="">Tüm işlemler</option>
          {meta.actions.map(a => <option key={a.key} value={a.key}>{a.label}</option>)}
        </select>
        {meta.users.length > 1 && (
          <select className="input !py-1.5 !w-auto text-xs" value={who}
            onChange={e => setWho(e.target.value)}>
            <option value="">Herkes</option>
            {meta.users.map(u => <option key={u} value={u}>{u}</option>)}
          </select>
        )}
      </div>

      {err && <p className="text-sm text-red-300">{err}</p>}

      <div className={`space-y-4 transition-opacity ${loading ? 'opacity-50' : ''}`}>
        {gruplar.map(([gun, satirlar]) => (
          <div key={gun}>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-panel-muted mb-1.5">
              {gun}
            </div>
            <div className="card !p-0 divide-y divide-panel-border overflow-hidden">
              {satirlar.map(it => <Satir key={it.id} it={it} />)}
            </div>
          </div>
        ))}
        {items.length === 0 && !loading && (
          <div className="card text-sm text-panel-muted text-center py-8">
            Bu aralıkta kayıt yok. (Günlük tutulmaya bu özelliğin yayına
            alındığı tarihte başlandı — daha eski değişiklikler görünmez.)
          </div>
        )}
      </div>

      {(page > 1 || hasMore) && (
        <div className="flex justify-between">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
            className="btn-ghost text-xs disabled:opacity-30">← Önceki</button>
          <span className="text-xs text-panel-muted self-center">Sayfa {page}</span>
          <button disabled={!hasMore} onClick={() => setPage(p => p + 1)}
            className="btn-ghost text-xs disabled:opacity-30">Sonraki →</button>
        </div>
      )}
    </div>
  )
}

function Satir({ it }) {
  const saat = it.created_at
    ? new Date(it.created_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
    : ''
  return (
    <div className="flex gap-2.5 px-4 py-2.5 text-sm">
      <span className="text-base leading-5">{ICONS[it.action] || '•'}</span>
      <div className="min-w-0 flex-1">
        <div>
          <span className="font-medium">{it.action_label}</span>
          {it.entity_label && <span className="text-panel-muted"> — {it.entity_label}</span>}
        </div>
        <Detay detail={it.detail} />
        <div className="text-[11px] text-panel-muted mt-0.5">
          {it.user_email || 'sistem'} · {saat}
        </div>
      </div>
    </div>
  )
}

function Detay({ detail }) {
  if (!detail || typeof detail !== 'object') return null
  const parcalar = Object.entries(detail)
    .filter(([, v]) => v !== null && v !== '' && !(Array.isArray(v) && v.length === 0))
    .map(([k, v]) => {
      const ad = FIELD_LABELS[k] || k
      // [eski, yeni] biçimi → "Fiyat: 349,90 → 299,90"
      if (Array.isArray(v) && v.length === 2 && !Array.isArray(v[0])) {
        return `${ad}: ${v[0] ?? '—'} → ${v[1] ?? '—'}`
      }
      if (Array.isArray(v)) return `${ad}: ${v.join(', ')}`
      if (typeof v === 'boolean') return `${ad}: ${v ? 'evet' : 'hayır'}`
      return `${ad}: ${v}`
    })
  if (parcalar.length === 0) return null
  return (
    <div className="text-xs text-panel-muted mt-0.5 break-words">
      {parcalar.join(' · ')}
    </div>
  )
}

function groupByDay(items) {
  const map = new Map()
  for (const it of items) {
    const d = it.created_at ? new Date(it.created_at) : new Date()
    const key = d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(it)
  }
  return [...map.entries()]
}
