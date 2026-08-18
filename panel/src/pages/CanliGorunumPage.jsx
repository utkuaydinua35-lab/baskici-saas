import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import Kure from '../components/Kure'

// Canlı Görünüm — mağazada ŞU AN ne olduğunu tek ekranda gösterir.
// Veri /api/orders/live-view'dan 10 sn'de bir gelir; sekme gizliyken durur
// (arka planda açık duran panel boşuna sorgu atmasın).

const TL = new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY',
  maximumFractionDigits: 0 })
const SAYI = new Intl.NumberFormat('tr-TR')

// ── Küçük parçalar ────────────────────────────────────────────

// Etiketin altındaki noktalı çizgi Shopify'ın "üzerine gel, açıklama var"
// göstergesi; title ile aynı işi görüyor.
function Etiket({ children, ipucu }) {
  return (
    <div className="text-[13px] font-medium text-panel-ink inline-block
      border-b border-dotted border-panel-muted/50 pb-0.5" title={ipucu}>
      {children}
    </div>
  )
}

function Degisim({ yuzde }) {
  if (yuzde === null || yuzde === undefined) return null
  const arti = yuzde >= 0
  return (
    <span className={`text-xs font-medium ${arti ? 'text-emerald-600' : 'text-red-600'}`}>
      {arti ? '↗' : '↘'} %{SAYI.format(Math.abs(yuzde))}
    </span>
  )
}

// 24 saatlik seri — düz çizgi bugün, kesikli çizgi dün. İkisi AYNI ölçekte
// çizilir, yoksa "dünü geçtik mi" sorusu görselden okunamaz.
function Sparkline({ seri = [], onceki = [], saat = 23, renk = '#2c6ecb' }) {
  const G = 120, Y = 30, pad = 2
  const enBuyuk = Math.max(1, ...seri, ...onceki)
  const nokta = (dizi, sinir) => dizi.slice(0, sinir + 1).map((v, i) => {
    const x = pad + (i / 23) * (G - pad * 2)
    const y = Y - pad - (v / enBuyuk) * (Y - pad * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return (
    <svg viewBox={`0 0 ${G} ${Y}`} className="w-full h-[30px] mt-2"
      preserveAspectRatio="none" aria-hidden="true">
      <polyline points={nokta(onceki, 23)} fill="none" stroke={renk}
        strokeWidth="1.2" strokeDasharray="3 2" opacity="0.35" />
      <polyline points={nokta(seri, saat)} fill="none" stroke={renk}
        strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

function Kart({ etiket, ipucu, deger, degisim, seri, onceki, saat }) {
  return (
    <div className="card !p-4 flex flex-col">
      <Etiket ipucu={ipucu}>{etiket}</Etiket>
      {/* Sayı ile grafik ALT ALTA: yan yanayken 120px'lik sabit grafik
          "₺10.800" gibi uzun değeri sıfır piksele eziyordu. */}
      <div className="mt-2 flex items-baseline gap-2 flex-wrap">
        <span className="text-2xl font-semibold tabular-nums leading-none">{deger}</span>
        <Degisim yuzde={degisim} />
      </div>
      {seri && <div className="mt-auto"><Sparkline seri={seri} onceki={onceki} saat={saat} /></div>}
    </div>
  )
}

// ── Sayfa ─────────────────────────────────────────────────────

export default function CanliGorunumPage() {
  const { storeId, store } = useStore()
  const [d, setD] = useState(null)
  const [hata, setHata] = useState('')
  const [tazelendi, setTazelendi] = useState(null)
  const ilk = useRef(true)

  useEffect(() => {
    if (!storeId) return
    let timer
    const cek = () => {
      if (document.visibilityState !== 'visible') return
      api.get(`/api/orders/live-view?store_id=${storeId}`)
        .then(v => { setD(v); setTazelendi(Date.now()); setHata('') })
        .catch(e => { if (ilk.current) setHata(e?.detail || 'Canlı veri alınamadı') })
        .finally(() => { ilk.current = false })
    }
    cek()
    timer = setInterval(cek, 10000)
    document.addEventListener('visibilitychange', cek)
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', cek) }
  }, [storeId])

  if (hata) return <p className="text-sm text-red-600">{hata}</p>
  if (!d) return <p className="text-sm text-panel-muted">Canlı veri yükleniyor…</p>

  const saat = d.su_anki_saat ?? 23
  const konumToplam = Math.max(1, ...d.konumlar.map(k => k.oturum))
  const { yeni, geri_donen } = d.musteriler
  const musteriToplam = yeni + geri_donen

  return (
    <div className="flex flex-col lg:flex-row gap-5 lg:h-[calc(100vh-7rem)]">
      {/* ── Sol sütun: metrikler ── */}
      <div className="lg:w-[420px] shrink-0 space-y-3 lg:overflow-y-auto lg:pr-1">
        <div className="flex items-center gap-2.5">
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <span aria-hidden="true">🌐</span> Canlı Görünüm
          </h1>
          <TazeRozet an={tazelendi} />
        </div>
        {store && <p className="text-xs text-panel-muted -mt-1.5">{store.name}</p>}

        <div className="grid grid-cols-2 gap-3">
          <Kart etiket="Şu anki ziyaretçiler" deger={SAYI.format(d.ziyaretci)}
            ipucu="Son 5 dakika içinde vitrinde hareket eden oturum sayısı" />
          <Kart etiket="Toplam satışlar" deger={TL.format(Number(d.satislar.bugun))}
            ipucu="Bugünün cirosu (iptal ve iade hariç) — kesikli çizgi dün"
            degisim={d.satislar.degisim} seri={d.satislar.seri}
            onceki={d.satislar.seri_onceki} saat={saat} />
          <Kart etiket="Oturumlar" deger={SAYI.format(d.oturumlar.bugun)}
            ipucu="Bugün vitrini ziyaret eden farklı oturum sayısı"
            degisim={d.oturumlar.degisim} seri={d.oturumlar.seri}
            onceki={d.oturumlar.seri_onceki} saat={saat} />
          <Kart etiket="Siparişler" deger={SAYI.format(d.siparisler.bugun)}
            ipucu="Bugün oluşan sipariş sayısı (iptal hariç)"
            degisim={d.siparisler.degisim} seri={d.siparisler.seri}
            onceki={d.siparisler.seri_onceki} saat={saat} />
        </div>

        {/* Müşteri davranışı — huni. Üç adım da AYNI zaman penceresini
            kullanır, yoksa sayılar karşılaştırılamaz. */}
        <div className="card !p-4">
          <Etiket ipucu={`Son ${d.davranis.pencere_dk} dakikadaki hareket`}>
            Müşteri davranışı
          </Etiket>
          <div className="mt-3 grid grid-cols-3 divide-x divide-panel-border">
            <Huni etiket="Aktif sepetler" n={d.davranis.aktif_sepet} />
            <Huni etiket="Ödeme yapıyor" n={d.davranis.odeme_yapiyor} ic />
            <Huni etiket="Satın aldı" n={d.davranis.satin_aldi} ic />
          </div>
        </div>

        {/* Konuma göre oturumlar */}
        <div className="card !p-4">
          <Etiket ipucu="Bugünkü oturumların ülke dağılımı">
            Konuma göre oturumlar
          </Etiket>
          {d.konumlar.length === 0 ? (
            <p className="mt-3 text-xs text-panel-muted">Bugün henüz ziyaretçi yok.</p>
          ) : (
            <div className="mt-3 space-y-2.5">
              {d.konumlar.map(k => (
                <div key={k.kod}>
                  <div className="text-xs text-panel-muted">{k.ad}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="h-2 rounded-full bg-[#2c6ecb] transition-all duration-700"
                      style={{ width: `${Math.max(4, (k.oturum / konumToplam) * 100)}%` }} />
                    <span className="text-xs tabular-nums text-panel-muted">{k.oturum}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Yeni ve geri dönen müşteriler */}
        <div className="card !p-4">
          <Etiket ipucu="Bugün sipariş verenler: ilk siparişi bugünse yeni">
            Yeni ve geri dönen müşteriler
          </Etiket>
          {musteriToplam === 0 ? (
            <p className="mt-3 text-xs text-panel-muted">Bugün henüz sipariş yok.</p>
          ) : (
            <>
              <div className="mt-3 h-2.5 rounded-full overflow-hidden flex bg-panel-input">
                <div className="bg-[#2c6ecb]" style={{ width: `${(yeni / musteriToplam) * 100}%` }} />
                <div className="bg-[#5c6ac4]" style={{ width: `${(geri_donen / musteriToplam) * 100}%` }} />
              </div>
              <div className="mt-2.5 flex gap-4 text-xs">
                <Nokta renk="#2c6ecb" etiket="Yeni" n={yeni} />
                <Nokta renk="#5c6ac4" etiket="Geri dönen" n={geri_donen} />
              </div>
            </>
          )}
        </div>

        {/* Son hareketler */}
        <div className="card !p-4">
          <Etiket>Son hareketler</Etiket>
          {d.aktivite.length === 0 ? (
            <p className="mt-3 text-xs text-panel-muted">Henüz hareket yok.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {d.aktivite.map((a, i) => (
                <li key={i} className="flex items-baseline gap-2 text-xs">
                  <span aria-hidden="true">{a.tur === 'siparis' ? '🛍️'
                    : a.tur === 'odeme_paid' ? '✅' : a.tur === 'odeme_failed' ? '⚠️' : '🕐'}</span>
                  <span className="font-medium text-panel-ink">{a.kim}</span>
                  <span className="text-panel-muted flex-1 truncate">{a.metin}</span>
                  {a.tutar && <span className="tabular-nums text-panel-muted">
                    {TL.format(Number(a.tutar))}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ── Sağ: küre ── */}
      <div className="flex-1 min-h-[380px] card !p-0 overflow-hidden relative">
        <Kure konumlar={d.konumlar} />
      </div>
    </div>
  )
}

function Huni({ etiket, n, ic }) {
  return (
    <div className={ic ? 'pl-4' : ''}>
      <div className="text-xs text-panel-muted">{etiket}</div>
      <div className="text-2xl font-semibold tabular-nums mt-1">{SAYI.format(n)}</div>
    </div>
  )
}

function Nokta({ renk, etiket, n }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="w-2 h-2 rounded-full" style={{ background: renk }} />
      <span className="text-panel-muted">{etiket}</span>
      <span className="tabular-nums font-medium">{n}</span>
    </span>
  )
}

// "Az önce" rozeti — verinin canlı olduğunu gösterir; sekme gizliyken
// güncelleme durduğu için geri dönüldüğünde yaşın görünmesi önemli.
function TazeRozet({ an }) {
  const [, tik] = useState(0)
  useEffect(() => { const t = setInterval(() => tik(v => v + 1), 5000); return () => clearInterval(t) }, [])
  if (!an) return null
  const sn = Math.floor((Date.now() - an) / 1000)
  const metin = sn < 15 ? 'Az önce' : sn < 60 ? `${sn} sn önce` : `${Math.floor(sn / 60)} dk önce`
  return (
    <span className="flex items-center gap-1.5 text-xs text-panel-muted">
      <span className={`w-2 h-2 rounded-full ${sn < 30 ? 'bg-[#2c6ecb] animate-pulse' : 'bg-panel-muted/40'}`} />
      {metin}
    </span>
  )
}
