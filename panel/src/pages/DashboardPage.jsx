import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Mağaza dashboard'u — bugün/7 gün satış + hızlı bakış.
export default function DashboardPage() {
  const { storeId, store } = useStore()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!storeId) return
    const end = new Date().toISOString().slice(0, 10)
    const start = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10)
    api.get(`/api/analytics/summary?start=${start}&end=${end}&store_id=${storeId}`)
      .then(setData)
      .catch(e => setError(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi'))
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
