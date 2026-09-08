import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Mağaza dashboard'u — bugün/7 gün satış + hızlı bakış.
export default function DashboardPage() {
  const { storeId, store } = useStore()
  const [data, setData] = useState(null)
  const [live, setLive] = useState(null)
  const [stok, setStok] = useState(null)   // {low_stock, out_of_stock}
  const [guide, setGuide] = useState(null) // kurulum rehberi adımları
  const [ready, setReady] = useState(null) // canlıya hazırlık kontrolü
  const [error, setError] = useState('')

  useEffect(() => {
    if (!storeId) return
    const end = new Date().toISOString().slice(0, 10)
    const start = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10)
    api.get(`/api/analytics/summary?start=${start}&end=${end}&store_id=${storeId}`)
      .then(setData)
      .catch(e => setError(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi'))
    api.get(`/api/catalog/inventory?store_id=${storeId}`)
      .then(d => setStok({ low_stock: d.low_stock, out_of_stock: d.out_of_stock }))
      .catch(() => {})
    // Canlıya hazırlık — satışı fiilen durduran eksikler en üstte gösterilir
    api.get(`/api/store-settings/${storeId}/readiness`).then(setReady).catch(() => {})
    // Kurulum rehberi (Shopify setup guide) — tamamlanınca kart kaybolur
    if (localStorage.getItem(`kurulum_gizle_${storeId}`)) { setGuide([]); return }
    Promise.all([
      api.get(`/api/catalog/products?store_id=${storeId}&slim=1`).catch(() => []),
      api.get(`/api/store-settings/${storeId}`).catch(() => null),
      api.get(`/api/store-settings/${storeId}/theme`).catch(() => null),
      api.get(`/api/orders?store_id=${storeId}&per_page=1`).catch(() => null),
    ]).then(([prods, settings, theme, orders]) => {
      const cfg = settings?.config || {}
      setGuide([
        { label: 'İlk ürününü ekle', done: (prods || []).length > 0, to: '/urunler' },
        { label: 'Logo ve tema renklerini ayarla', done: !!theme?.logo_url, to: '/tema' },
        { label: 'Kargo ücretini belirle', done: !!cfg.shipping_fee, to: '/ayarlar' },
        { label: 'Ödeme sağlayıcını bağla (iyzico/PayTR)',
          done: !!(cfg.iyzico_api_key || cfg.paytr_merchant_id), to: '/ayarlar' },
        { label: 'Alan adını bağla', done: !!(cfg.custom_domain || cfg.shop_domain), to: '/ayarlar' },
        { label: 'İlk siparişini al 🎉', done: (orders?.total || 0) > 0, to: '/siparisler' },
      ])
    })
  }, [storeId])

  // Canlı veri — 10 sn'de bir (Shopify live view); sekme gizliyken durur
  const [liveView, setLiveView] = useState(null)
  useEffect(() => {
    if (!storeId) return
    let timer
    const pull = () => {
      if (document.visibilityState !== 'visible') return
      api.get(`/api/analytics/live?store_id=${storeId}`).then(setLive).catch(() => {})
      api.get(`/api/orders/live-view?store_id=${storeId}`).then(setLiveView).catch(() => {})
    }
    pull()
    timer = setInterval(pull, 10000)
    document.addEventListener('visibilitychange', pull)
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', pull) }
  }, [storeId])

  const today = data?.daily?.[data.daily.length - 1]

  return (
    <div className="space-y-4 max-w-5xl">
      <h1 className="text-xl font-semibold">Hoş geldin 👋</h1>
      {error && <p className="text-sm text-red-300">{error}</p>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi label="Bugünkü Satış" value={fmtTl(today?.tutar || 0)} hint={`${today?.adet || 0} sipariş`} />
        <Kpi label="Son 7 Gün" value={fmtTl(data?.revenue || 0)} hint={`${data?.orders_count || 0} sipariş`} />
        <Kpi label="Ortalama Sepet" value={fmtTl(data?.aov || 0)} />
        <Kpi label="Dönüşüm" value={data?.funnel?.created > 0 ? `%${data.funnel.conversion}` : '—'}
          hint={data?.funnel?.abandoned_count > 0
            ? `${data.funnel.abandoned_count} terk sepet` : 'checkout verisi yok'} />
      </div>

      {/* Canlıya hazırlık — satışı durduran eksikler her şeyin üstünde */}
      {ready && !ready.ready && (
        <div className="card border-red-500/30 bg-red-500/10">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-red-300">
              🚨 Satışı engelleyen {ready.blocker_count} sorun var
            </h2>
          </div>
          <ul className="mt-2.5 space-y-2">
            {ready.checks.filter(c => c.blocker).map(c => (
              <li key={c.key} className="text-sm">
                <div className="flex items-start gap-2">
                  <span className="text-red-300 mt-0.5">●</span>
                  <div className="min-w-0">
                    <div className="font-medium">
                      {c.label.replace(/^Tüm/, 'Bazı')}
                      {c.count ? ` — ${c.count} ürün` : ''}
                    </div>
                    <div className="text-xs text-panel-muted mt-0.5">{c.hint}</div>
                  </div>
                  {c.to && (
                    <Link to={c.to}
                          className="ml-auto shrink-0 text-xs text-panel-accent hover:underline
                                     inline-flex items-center min-h-[34px] px-1">
                      Düzelt →
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {ready?.ready && ready.checks.some(c => !c.ok) && (
        <div className="card !py-2.5 flex items-center gap-2 text-sm">
          <span className="text-emerald-300">✓ Satışa hazır</span>
          <span className="text-xs text-panel-muted">
            — öneri: {ready.checks.filter(c => !c.ok).map(c => c.label).join(', ')}
          </span>
        </div>
      )}

      {guide && guide.length > 0 && guide.some(g => !g.done) && (
        <div className="card">
          <div className="flex items-center">
            <h2 className="text-sm font-semibold">🚀 Kurulum Rehberi</h2>
            <span className="ml-2 text-xs text-panel-muted">
              {guide.filter(g => g.done).length}/{guide.length} tamamlandı
            </span>
            <button onClick={() => { localStorage.setItem(`kurulum_gizle_${storeId}`, '1'); setGuide([]) }}
              className="ml-auto text-xs text-panel-muted hover:text-panel-ink py-1.5 px-1">Gizle</button>
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-panel-input overflow-hidden">
            <div className="h-full bg-emerald-600 transition-all"
              style={{ width: `${(guide.filter(g => g.done).length / guide.length) * 100}%` }} />
          </div>
          <ul className="mt-3 space-y-1.5">
            {guide.map(g => (
              <li key={g.label}>
                <Link to={g.to} className="flex items-center gap-2.5 text-sm group py-1.5">
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] shrink-0 ${
                    g.done ? 'bg-emerald-600 text-white' : 'border-2 border-panel-border'}`}>
                    {g.done ? '✓' : ''}
                  </span>
                  <span className={g.done ? 'text-panel-muted line-through' : 'group-hover:underline'}>
                    {g.label}
                  </span>
                  {!g.done && <span className="ml-auto text-xs text-panel-muted">→</span>}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {stok && (stok.low_stock > 0 || stok.out_of_stock > 0) && (
        <Link to="/envanter"
          className="block card !py-3 border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/10 transition">
          <div className="flex items-center gap-2 text-sm">
            <span>⚠️</span>
            <span className="font-medium text-amber-300">
              {stok.out_of_stock > 0 && `${stok.out_of_stock} varyant stoksuz`}
              {stok.out_of_stock > 0 && stok.low_stock > 0 && ' · '}
              {stok.low_stock > 0 && `${stok.low_stock} varyantta az stok`}
            </span>
            <span className="ml-auto text-xs text-amber-300">Envantere git →</span>
          </div>
        </Link>
      )}

      {live && <LiveCard live={live} lv={liveView} />}

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
function LiveCard({ live, lv }) {
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
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-600" />
        </span>
        <span className="text-[11px] font-semibold tracking-wide text-emerald-300">CANLI</span>
        <span className="text-[11px] text-panel-muted ml-auto">
          Son 15 dk: {live.last_15m.orders} sipariş · {fmtTl(live.last_15m.revenue)}
        </span>
      </div>
      {/* Shopify live view metrikleri — 10 sn'de bir tazelenir */}
      {lv && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mb-3">
          {[
            ['👁', 'Şu an sitede', lv.current_visitors],
            ['📅', 'Bugün oturum', lv.today_sessions],
            ['🛒', 'Aktif sepet', lv.active_carts],
            ['💳', 'Ödeme yapıyor', lv.checking_out],
            ['✅', 'Az önce aldı', lv.purchased_recent],
            ['🛍️', 'Bugün satış', `${lv.today_orders} · ${fmtTl(Number(lv.today_revenue || 0))}`],
          ].map(([icon, label, val]) => (
            <div key={label} className="rounded-xl bg-panel-input/70 px-2.5 py-2 text-center">
              <div className="text-base leading-none">{icon}</div>
              <div className="text-sm font-semibold tabular-nums mt-1">{val}</div>
              <div className="text-[10px] text-panel-muted leading-tight">{label}</div>
            </div>
          ))}
        </div>
      )}
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
