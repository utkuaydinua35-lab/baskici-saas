import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Mağaza dashboard'u — bugün/7 gün satış + hızlı bakış.
export default function DashboardPage() {
  const { storeId, store } = useStore()
  const [data, setData] = useState(null)
  const [live, setLive] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!storeId) return
    const end = new Date().toISOString().slice(0, 10)
    const start = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10)
    api.get(`/api/analytics/summary?start=${start}&end=${end}&store_id=${storeId}`)
      .then(setData)
      .catch(e => setError(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi'))
  }, [storeId])

  // Canlı veri — 30 sn'de bir; sekme gizliyken durur
  useEffect(() => {
    if (!storeId) return
    let timer
    const pull = () => {
      if (document.visibilityState !== 'visible') return
      api.get(`/api/analytics/live?store_id=${storeId}`).then(setLive).catch(() => {})
    }
    pull()
    timer = setInterval(pull, 30000)
    document.addEventListener('visibilitychange', pull)
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', pull) }
  }, [storeId])

  const today = data?.daily?.[data.daily.length - 1]

  return (
    <div className="space-y-4 max-w-5xl">
      <h1 className="text-xl font-semibold">Hoş geldin 👋</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi label="Bugünkü Satış" value={fmtTl(today?.tutar || 0)} hint={`${today?.adet || 0} sipariş`} />
        <Kpi label="Son 7 Gün" value={fmtTl(data?.revenue || 0)} hint={`${data?.orders_count || 0} sipariş`} />
        <Kpi label="Ortalama Sepet" value={fmtTl(data?.aov || 0)} />
        <Kpi label="Dönüşüm" value={data?.funnel?.created > 0 ? `%${data.funnel.conversion}` : '—'}
          hint={data?.funnel?.abandoned_count > 0
            ? `${data.funnel.abandoned_count} terk sepet` : 'checkout verisi yok'} />
      </div>

      {live && <LiveCard live={live} />}

      {data && <MiniChart daily={data.daily} />}

      <div className="grid sm:grid-cols-3 gap-3">
        <QuickCard to="/urunler" icon="🛍️" title="Ürün ekle"
          desc="Yeni tasarımını dakikalar içinde satışa çıkar" />
        <QuickCard to="/kuponlar" icon="🎟️" title="Kampanya başlat"
          desc="Kupon koduyla satışları hareketlendir" />
        <QuickCard to="/tema" icon="🎨" title="Vitrini kişiselleştir"
          desc="Renk, logo ve tema ayarları" />
      </div>

      {data?.top_products?.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold mb-3">Bu haftanın en çok satanları</h2>
          <ul className="space-y-1.5 text-sm">
            {data.top_products.slice(0, 5).map((p, i) => (
              <li key={i} className="flex justify-between">
                <span className="text-panel-ink truncate pr-3">{i + 1}. {p.title}</span>
                <span className="text-panel-muted whitespace-nowrap">{p.quantity} adet</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

const fmtTl = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(n || 0)

function Kpi({ label, value, hint }) {
  return (
    <div className="card">
      <div className="text-[11px] text-panel-muted uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1 tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-panel-muted mt-0.5">{hint}</div>}
    </div>
  )
}

function MiniChart({ daily }) {
  if (!daily?.length) return null
  const W = 700, H = 80, P = 4
  const vals = daily.map(d => d.tutar || 0)
  const max = Math.max(...vals, 1)
  const x = (i) => daily.length > 1 ? P + (i / (daily.length - 1)) * (W - 2 * P) : W / 2
  const y = (v) => H - P - (v / max) * (H - 2 * P)
  const pts = daily.map((d, i) => `${x(i)},${y(d.tutar || 0)}`).join(' ')
  return (
    <div className="card">
      <div className="text-[11px] text-panel-muted uppercase tracking-wide mb-2">Son 7 gün</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none" style={{ height: 80 }}>
        <polygon points={`${P},${H - P} ${pts} ${W - P},${H - P}`} fill="rgb(5 150 105 / 0.12)" />
        <polyline points={pts} fill="none" stroke="#059669" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    </div>
  )
}

function QuickCard({ to, icon, title, desc }) {
  return (
    <Link to={to} className="card hover:border-panel-accent/50 hover:shadow-sm transition block">
      <div className="text-2xl">{icon}</div>
      <div className="mt-2 font-medium text-sm">{title}</div>
      <div className="text-xs text-panel-muted mt-0.5">{desc}</div>
    </Link>
  )
}

// Canlı görünüm — 30 sn'de bir yenilenen aktivite akışı.
function LiveCard({ live }) {
  const ago = (iso) => {
    if (!iso) return ''
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
    if (s < 60) return 'az önce'
    if (s < 3600) return `${Math.floor(s / 60)} dk önce`
    if (s < 86400) return `${Math.floor(s / 3600)} sa önce`
    return `${Math.floor(s / 86400)} gün önce`
  }
  const ICON = {
    order: '🛍️', checkout_paid: '✅', checkout_pending: '🛒',
    checkout_failed: '✗', checkout_expired: '🕑',
  }
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-3">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
        </span>
        <span className="text-[11px] font-semibold tracking-wide text-emerald-700">CANLI</span>
        <span className="text-[11px] text-panel-muted ml-auto">
          Son 15 dk: {live.last_15m.orders} sipariş · {fmtTl(live.last_15m.revenue)}
          {live.active_checkouts > 0 && ` · ${live.active_checkouts} kişi ödeme sayfasında`}
        </span>
      </div>
      {live.activity.length === 0 ? (
        <p className="text-xs text-panel-muted">Henüz aktivite yok — ilk ziyaretçiler yolda.</p>
      ) : (
        <ul className="space-y-1.5 max-h-52 overflow-y-auto">
          {live.activity.map((a, i) => (
            <li key={i} className="flex items-center gap-2 text-xs">
              <span>{ICON[a.type] || '•'}</span>
              <span className="text-panel-ink"><b>{a.who}</b> {a.text}</span>
              {a.amount && <span className="text-panel-muted tabular-nums">{fmtTl(Number(a.amount))}</span>}
              <span className="ml-auto text-panel-muted whitespace-nowrap">{ago(a.at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
