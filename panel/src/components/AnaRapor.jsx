import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'

// Ana sayfa raporu — Shopify "Analytics" düzeni: tarih aralığı + karşılaştırma,
// KPI kartları (önceki döneme göre değişim), ciro/sipariş/oturum grafiği,
// son 8 hafta, şehirler, en çok satanlar, birlikte satılanlar, kaynak, huni.
// Veri: /api/analytics/rapor (backend services/rapor.py).

const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz',
  'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']

const iso = (d) => {
  const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), g = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${g}`
}
const gunEkle = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x }

// Hazır aralıklar — bugün tarayıcı saatine göre (Türkiye'de İstanbul günü)
function hazirAraliklar() {
  const bugun = new Date(); bugun.setHours(0, 0, 0, 0)
  const y = bugun.getFullYear(), m = bugun.getMonth()
  const liste = [
    { id: 'bugun', ad: 'Bugün', bas: bugun, bit: bugun },
    { id: 'dun', ad: 'Dün', bas: gunEkle(bugun, -1), bit: gunEkle(bugun, -1) },
    { id: '7', ad: 'Son 7 gün', bas: gunEkle(bugun, -6), bit: bugun },
    { id: '30', ad: 'Son 30 gün', bas: gunEkle(bugun, -29), bit: bugun },
    { id: '90', ad: 'Son 90 gün', bas: gunEkle(bugun, -89), bit: bugun },
    { id: '365', ad: 'Son 1 yıl', bas: gunEkle(bugun, -364), bit: bugun },
    { id: 'buay', ad: 'Bu ay', bas: new Date(y, m, 1), bit: bugun },
    { id: 'buyil', ad: 'Bu yıl', bas: new Date(y, 0, 1), bit: bugun },
  ]
  // Son 12 ay tek tek (Eylül, Ağustos…) ve son iki yıl
  const aylar = []
  for (let i = 1; i <= 12; i++) {
    const bas = new Date(y, m - i, 1), bit = new Date(y, m - i + 1, 0)
    aylar.push({ id: `ay-${iso(bas)}`, ad: `${AYLAR[bas.getMonth()]} ${bas.getFullYear()}`, bas, bit })
  }
  const yillar = [y - 1, y - 2].map(yy => ({ id: `yil-${yy}`, ad: String(yy), bas: new Date(yy, 0, 1), bit: new Date(yy, 11, 31) }))
  return { liste, aylar, yillar }
}

const fmtTl = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(n || 0)
const fmtSayi = (n) => new Intl.NumberFormat('tr-TR').format(n || 0)
const fmtYuzde = (n) => n == null ? '—' : `%${n.toLocaleString('tr-TR', { maximumFractionDigits: 2 })}`

function degisim(simdi, onceki) {
  if (onceki == null || simdi == null) return null
  if (onceki === 0) return simdi === 0 ? 0 : null
  return ((simdi - onceki) / Math.abs(onceki)) * 100
}

function oku(anahtar, varsayilan) {
  try { return localStorage.getItem(anahtar) || varsayilan } catch { return varsayilan }
}
function yaz(anahtar, deger) { try { localStorage.setItem(anahtar, deger) } catch { /* gizli pencere */ } }

export default function AnaRapor() {
  const { liste, aylar, yillar } = useMemo(hazirAraliklar, [])
  const tumu = useMemo(() => [...liste, ...aylar, ...yillar], [liste, aylar, yillar])
  const [secim, setSecim] = useState(() => oku('rapor_aralik', '30'))
  const [ozel, setOzel] = useState(() => ({ bas: iso(gunEkle(new Date(), -13)), bit: iso(new Date()) }))
  const [kars, setKars] = useState(() => oku('rapor_kars', 'onceki'))
  const [kanal, setKanal] = useState(() => oku('rapor_kanal', 'perakende'))
  const [veri, setVeri] = useState(null)
  const [hata, setHata] = useState('')
  const [yukleniyor, setYukleniyor] = useState(false)

  const aralik = secim === 'ozel'
    ? ozel
    : (() => { const a = tumu.find(x => x.id === secim) || liste[3]; return { bas: iso(a.bas), bit: iso(a.bit) } })()

  useEffect(() => {
    if (!aralik.bas || !aralik.bit || aralik.bit < aralik.bas) return
    let iptal = false
    setYukleniyor(true); setHata('')
    api.get(`/api/analytics/rapor?start=${aralik.bas}&end=${aralik.bit}&karsilastir=${kars}&kanal=${kanal}`)
      .then(d => { if (!iptal) setVeri(d) })
      .catch(e => { if (!iptal) setHata(typeof e?.detail === 'string' ? e.detail : 'Rapor yüklenemedi') })
      .finally(() => { if (!iptal) setYukleniyor(false) })
    return () => { iptal = true }
  }, [aralik.bas, aralik.bit, kars, kanal])

  const s = veri?.simdi, o = veri?.onceki
  const oturumYok = veri && !veri.oturum_baslangici

  return (
    <div className="space-y-3">
      {/* Filtreler — tek satır */}
      <div className="flex flex-wrap items-center gap-2">
        <select className="input !w-auto !py-1.5 text-sm" value={secim}
          onChange={e => { setSecim(e.target.value); yaz('rapor_aralik', e.target.value) }}>
          {liste.map(a => <option key={a.id} value={a.id}>{a.ad}</option>)}
          <optgroup label="Aylar">{aylar.map(a => <option key={a.id} value={a.id}>{a.ad}</option>)}</optgroup>
          <optgroup label="Yıllar">{yillar.map(a => <option key={a.id} value={a.id}>{a.ad}</option>)}</optgroup>
          <option value="ozel">Özel aralık…</option>
        </select>
        {secim === 'ozel' && (
          <span className="flex items-center gap-1.5 text-sm">
            <input type="date" className="input !w-auto !py-1.5" value={ozel.bas} max={ozel.bit}
              onChange={e => setOzel(x => ({ ...x, bas: e.target.value }))} />
            <span className="text-panel-muted">–</span>
            <input type="date" className="input !w-auto !py-1.5" value={ozel.bit} min={ozel.bas}
              onChange={e => setOzel(x => ({ ...x, bit: e.target.value }))} />
          </span>
        )}
        <select className="input !w-auto !py-1.5 text-sm" value={kars}
          onChange={e => { setKars(e.target.value); yaz('rapor_kars', e.target.value) }}>
          <option value="onceki">Önceki dönemle karşılaştır</option>
          <option value="gecen_yil">Geçen yılın aynı dönemiyle</option>
          <option value="yok">Karşılaştırma yok</option>
        </select>
        <select className="input !w-auto !py-1.5 text-sm" value={kanal}
          onChange={e => { setKanal(e.target.value); yaz('rapor_kanal', e.target.value) }}
          title="Perakende: vitrin + Shopify geçmişi (bayi hariç)">
          <option value="perakende">Perakende (vitrin + Shopify geçmişi)</option>
          <option value="vitrin">Yalnız vitrin</option>
          <option value="hepsi">Tüm kanallar (bayi dahil)</option>
        </select>
        {yukleniyor && <span className="text-xs text-panel-muted">yükleniyor…</span>}
      </div>
      {hata && <p className="text-sm text-red-300">{hata}</p>}

      {s && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <Kpi ad="Toplam satış" deger={fmtTl(s.ciro)} d={degisim(s.ciro, o?.ciro)}
              alt={s.ciro_usd > 0 ? `+ ${s.ciro_usd.toLocaleString('tr-TR')} $ bayi` : null} />
            <Kpi ad="Sipariş" deger={fmtSayi(s.siparis)} d={degisim(s.siparis, o?.siparis)} />
            <Kpi ad="Ortalama sepet" deger={fmtTl(s.ortalama_sepet)} d={degisim(s.ortalama_sepet, o?.ortalama_sepet)} />
            <Kpi ad="Oturum" deger={oturumYok ? '—' : fmtSayi(s.oturum)} d={oturumYok ? null : degisim(s.oturum, o?.oturum)}
              alt={oturumYok ? 'kayıt yeni başladı' : 'yalnız vitrin'} />
            <Kpi ad="Dönüşüm oranı" deger={fmtYuzde(s.donusum)}
              d={s.donusum != null && o?.donusum != null ? s.donusum - o.donusum : null} puan
              alt={s.donusum == null ? 'oturum verisi yok' : `${s.vitrin_siparis} sipariş / ${fmtSayi(s.oturum)} oturum`} />
          </div>
          <AnaGrafik s={s} o={o} />
          {veri.oturum_baslangici && new Date(veri.oturum_baslangici) > new Date(s.bas) && (
            <p className="text-[11px] text-panel-muted">
              Oturum kaydı {new Date(veri.oturum_baslangici).toLocaleDateString('tr-TR')} tarihinde başladı;
              öncesinde oturum ve dönüşüm görünmez (sipariş ve ciro tam).
            </p>
          )}
          <div className="grid lg:grid-cols-2 gap-3">
            <Haftalar h={veri.haftalar} />
            <Huni huni={veri.huni} />
            <Liste baslik="En çok satan ürünler" bos="Bu aralıkta satış yok"
              satirlar={veri.urunler.map(u => [u.urun, `${u.adet} adet`, fmtTl(u.ciro)])} />
            <Liste baslik="En çok sipariş gelen şehirler" bos="Şehir bilgisi yok"
              satirlar={veri.sehirler.map(c => [c.sehir, `${c.siparis} sipariş`, fmtTl(c.ciro)])} cubuk={veri.sehirler.map(c => c.siparis)} />
            <Liste baslik="Birlikte satılan ürünler" bos="Aynı siparişte birden çok ürün yok"
              satirlar={veri.birlikte.map(b => [`${b.a}  +  ${b.b}`, `${b.siparis} sipariş`])} />
            <Liste baslik="Trafik kaynakları" bos={oturumYok ? 'Oturum kaydı yeni başladı' : 'Oturum yok'}
              satirlar={veri.kaynaklar.map(k => [k.kaynak, `${fmtSayi(k.oturum)} oturum`])} cubuk={veri.kaynaklar.map(k => k.oturum)} />
            <Liste baslik="Giriş sayfaları" bos="Oturum yok"
              satirlar={veri.girisler.map(g => [g.yol, `${fmtSayi(g.oturum)} oturum`])} />
            <Musteri m={veri.musteri} cihaz={veri.cihazlar} />
          </div>
        </>
      )}
    </div>
  )
}

function Kpi({ ad, deger, d, alt, puan = false }) {
  return (
    <div className="card">
      <div className="text-[11px] text-panel-muted uppercase tracking-wide">{ad}</div>
      <div className="text-xl font-semibold mt-1 tabular-nums">{deger}</div>
      <div className="flex items-center gap-1.5 mt-0.5 min-h-[16px]">
        {d != null && (
          <span className={`text-[11px] font-medium tabular-nums whitespace-nowrap ${d > 0 ? 'text-emerald-300' : d < 0 ? 'text-red-300' : 'text-panel-muted'}`}>
            {d > 0 ? '↑' : d < 0 ? '↓' : '→'} {Math.abs(d).toLocaleString('tr-TR', { maximumFractionDigits: 1 })}{puan ? ' puan' : '%'}
          </span>
        )}
        {alt && <span className="text-[11px] text-panel-muted truncate">{alt}</span>}
      </div>
    </div>
  )
}

const OLCULER = [
  { id: 'ciro', ad: 'Satış', fmt: fmtTl },
  { id: 'siparis', ad: 'Sipariş', fmt: fmtSayi },
  { id: 'oturum', ad: 'Oturum', fmt: fmtSayi },
]

function etiket(k, birim) {
  if (birim === 'saat') return `${k}:00`
  if (birim === 'ay') { const [y, m] = k.split('-'); return `${AYLAR[+m - 1].slice(0, 3)} ${y}` }
  const [, m, g] = k.split('-'); return `${+g} ${AYLAR[+m - 1].slice(0, 3)}`
}

// Şimdiki dönem (yeşil, düz) ve karşılaştırma dönemi (gri, kesikli) — Shopify gibi
// sıra numarasıyla hizalanır; tek eksen, imleç çizgisi + ipucu.
function AnaGrafik({ s, o }) {
  const [olcu, setOlcu] = useState('ciro')
  const [imlec, setImlec] = useState(null)
  const kutu = useRef(null)
  const W = 720, H = 200, PL = 8, PR = 8, PT = 10, PB = 22
  const n = s.seri.length
  const a = s.seri.map(x => x[olcu] || 0)
  const b = o ? o.seri.slice(0, n).map(x => x[olcu] || 0) : []
  const max = Math.max(1, ...a, ...b)
  const x = (i) => n > 1 ? PL + (i / (n - 1)) * (W - PL - PR) : W / 2
  const y = (v) => PT + (1 - v / max) * (H - PT - PB)
  const yol = (arr) => arr.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const O = OLCULER.find(q => q.id === olcu)
  const etiketAdim = Math.max(1, Math.ceil(n / 8))

  const hareket = (e) => {
    const r = kutu.current?.getBoundingClientRect()
    if (!r || n === 0) return
    const px = ((e.clientX - r.left) / r.width) * W
    const i = n > 1 ? Math.round(((px - PL) / (W - PL - PR)) * (n - 1)) : 0
    setImlec(Math.max(0, Math.min(n - 1, i)))
  }

  return (
    <div className="card">
      <div className="flex items-center gap-2 flex-wrap mb-2">
        <div className="flex gap-1">
          {OLCULER.map(q => (
            <button key={q.id} onClick={() => setOlcu(q.id)}
              className={`px-2.5 py-1 rounded-lg text-xs ${olcu === q.id ? 'bg-panel-input text-panel-ink font-medium' : 'text-panel-muted hover:text-panel-ink'}`}>
              {q.ad}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3 text-[11px] text-panel-muted">
          <span className="flex items-center gap-1.5"><span className="w-4 h-0.5 bg-emerald-500 rounded" />{tarihAraligi(s)}</span>
          {o && <span className="flex items-center gap-1.5"><span className="w-4 border-t-2 border-dashed border-zinc-500" />{tarihAraligi(o)}</span>}
        </div>
      </div>
      <div className="relative" ref={kutu} onMouseMove={hareket} onMouseLeave={() => setImlec(null)}
        onTouchStart={e => hareket(e.touches[0])} onTouchMove={e => hareket(e.touches[0])}>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full block" style={{ height: 200 }} preserveAspectRatio="none" role="img"
          aria-label={`${O.ad} grafiği`}>
          {[0.25, 0.5, 0.75].map(t => (
            <line key={t} x1={PL} x2={W - PR} y1={PT + t * (H - PT - PB)} y2={PT + t * (H - PT - PB)}
              stroke="currentColor" className="text-panel-border" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          <line x1={PL} x2={W - PR} y1={H - PB} y2={H - PB} stroke="currentColor" className="text-panel-border" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          {o && <path d={yol(b)} fill="none" stroke="#71717a" strokeWidth="2" strokeDasharray="5 4" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />}
          <path d={`${yol(a)} L${x(n - 1)},${H - PB} L${x(0)},${H - PB} Z`} fill="rgb(16 185 129 / 0.10)" />
          <path d={yol(a)} fill="none" stroke="#10b981" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
          {imlec != null && (
            <line x1={x(imlec)} x2={x(imlec)} y1={PT} y2={H - PB} stroke="#a1a1aa" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          )}
        </svg>
        <div className="flex justify-between text-[10px] text-panel-muted -mt-4 px-1 pointer-events-none">
          {s.seri.map((p, i) => (i % etiketAdim === 0 || i === n - 1)
            ? <span key={p.k}>{etiket(p.k, s.birim)}</span> : null)}
        </div>
        {imlec != null && (
          <div className="absolute top-0 z-10 rounded-lg border border-panel-border bg-panel-card px-2.5 py-1.5 text-xs shadow-lg pointer-events-none whitespace-nowrap"
            style={{ left: `${(x(imlec) / W) * 100}%`, transform: `translateX(${imlec > n / 2 ? '-105%' : '5%'})` }}>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" />
              {etiket(s.seri[imlec].k, s.birim)}: <b className="tabular-nums">{O.fmt(a[imlec])}</b></div>
            {o && o.seri[imlec] && (
              <div className="flex items-center gap-1.5 text-panel-muted"><span className="w-2 h-2 rounded-full bg-zinc-500" />
                {etiket(o.seri[imlec].k, o.birim)}: <span className="tabular-nums">{O.fmt(b[imlec])}</span></div>
            )}
          </div>
        )}
      </div>
      <p className="mt-1 text-[11px] text-panel-muted">
        Toplam {O.ad.toLowerCase()}: <b className="text-panel-ink">{O.fmt(a.reduce((t, v) => t + v, 0))}</b>
        {o && <> · karşılaştırma: {O.fmt(b.reduce((t, v) => t + v, 0))}</>}
      </p>
    </div>
  )
}

function tarihAraligi(d) {
  const f = (t) => new Date(t + 'T00:00:00').toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' })
  return d.bas === d.bit ? f(d.bas) : `${f(d.bas)} – ${f(d.bit)}`
}

function Haftalar({ h }) {
  const max = Math.max(1, ...h.map(x => x.ciro))
  const son = h[h.length - 1], once = h[h.length - 2]
  const d = degisim(son?.ciro, once?.ciro)
  return (
    <div className="card">
      <div className="flex items-baseline gap-2 mb-3">
        <h3 className="text-sm font-semibold">Son 8 hafta</h3>
        {d != null && <span className={`text-[11px] ${d >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
          bu hafta, geçen haftaya göre {d >= 0 ? '↑' : '↓'} %{Math.abs(d).toFixed(0)}</span>}
      </div>
      <div className="flex items-end gap-[2px] h-32">
        {h.map((w, i) => (
          <div key={w.hafta} className="flex-1 flex flex-col items-center justify-end h-full group relative">
            <div className={`w-full max-w-[36px] rounded-t ${i === h.length - 1 ? 'bg-emerald-500' : 'bg-emerald-500/45'}`}
              style={{ height: `${Math.max(2, (w.ciro / max) * 100)}%` }} />
            <div className="absolute bottom-full mb-1 hidden group-hover:block rounded-lg border border-panel-border bg-panel-card px-2 py-1 text-[11px] whitespace-nowrap z-10">
              {new Date(w.hafta + 'T00:00:00').toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })} haftası:
              <b> {fmtTl(w.ciro)}</b> · {w.siparis} sipariş
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-[2px] mt-1 text-[10px] text-panel-muted">
        {h.map(w => <span key={w.hafta} className="flex-1 text-center">
          {new Date(w.hafta + 'T00:00:00').toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })}</span>)}
      </div>
    </div>
  )
}

function Huni({ huni }) {
  const ilk = huni[0]?.sayi || 0
  return (
    <div className="card">
      <h3 className="text-sm font-semibold mb-3">Dönüşüm hunisi <span className="text-[11px] font-normal text-panel-muted">(vitrin)</span></h3>
      {ilk === 0 ? <p className="text-xs text-panel-muted">Bu aralıkta oturum kaydı yok.</p> : (
        <ul className="space-y-2">
          {huni.map((a, i) => {
            const oran = ilk ? (a.sayi / ilk) * 100 : 0
            return (
              <li key={a.asama} className="text-xs">
                <div className="flex justify-between mb-0.5">
                  <span>{a.asama}</span>
                  <span className="tabular-nums text-panel-muted">{fmtSayi(a.sayi)}{i > 0 && ` · %${oran.toFixed(1)}`}</span>
                </div>
                <div className="h-2 rounded-full bg-panel-input overflow-hidden">
                  <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.max(1, oran)}%` }} />
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function Liste({ baslik, satirlar, bos, cubuk }) {
  const max = cubuk ? Math.max(1, ...cubuk) : 0
  return (
    <div className="card">
      <h3 className="text-sm font-semibold mb-2.5">{baslik}</h3>
      {satirlar.length === 0 ? <p className="text-xs text-panel-muted">{bos}</p> : (
        <ul className="space-y-1.5 text-sm">
          {satirlar.map((r, i) => (
            <li key={i} className="relative">
              {cubuk && <div className="absolute inset-y-0 left-0 rounded bg-emerald-500/10" style={{ width: `${(cubuk[i] / max) * 100}%` }} />}
              <div className="relative flex gap-3 px-1.5 py-0.5">
                <span className="truncate flex-1 min-w-0">{r[0]}</span>
                {r.slice(1).map((c, j) => <span key={j} className="text-panel-muted whitespace-nowrap tabular-nums text-xs">{c}</span>)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Musteri({ m, cihaz }) {
  const toplamC = Object.values(cihaz || {}).reduce((t, v) => t + v, 0)
  return (
    <div className="card space-y-3">
      <div>
        <h3 className="text-sm font-semibold mb-1.5">Müşteriler</h3>
        <div className="flex gap-4 text-sm">
          <span><b className="tabular-nums">{fmtSayi(m.yeni)}</b> <span className="text-panel-muted text-xs">yeni</span></span>
          <span><b className="tabular-nums">{fmtSayi(m.geri_donen)}</b> <span className="text-panel-muted text-xs">geri dönen</span></span>
          {m.toplam > 0 && <span className="text-xs text-panel-muted">tekrar alım %{((m.geri_donen / m.toplam) * 100).toFixed(1)}</span>}
        </div>
      </div>
      {toplamC > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-1.5">Cihaz</h3>
          <div className="flex gap-4 text-sm">
            {[['mobil', 'Mobil'], ['masaustu', 'Masaüstü']].map(([k, ad]) => (
              <span key={k}><b className="tabular-nums">%{(((cihaz[k] || 0) / toplamC) * 100).toFixed(0)}</b> <span className="text-panel-muted text-xs">{ad}</span></span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
