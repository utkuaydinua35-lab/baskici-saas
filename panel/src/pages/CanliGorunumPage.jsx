import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import Kure from '../components/Kure'

// Canlı Görünüm — mağazada ŞU AN ne olduğunu tek ekranda gösterir.
// Veri /api/orders/live-view'dan 10 sn'de bir gelir; sekme gizliyken durur
// (arka planda açık duran panel boşuna sorgu atmasın).
//
// Animasyonlar süs değil, DEĞİŞİMİ göstermek için: sayılar yeni değere
// sayarak gider, güncellenen kart kısa süre parlar, küredeki nokta nabız atar.

const TL = new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY',
  maximumFractionDigits: 0 })
const SAYI = new Intl.NumberFormat('tr-TR')

// ── Sayan sayı ────────────────────────────────────────────────
// Değer değişince eskiden yeniye yumuşakça geçer. Sayfa ilk açıldığında
// sıfırdan saymaz — o, gerçek veriyi bekliyormuş gibi görünürdü.
function useSayac(hedef) {
  const [deger, setDeger] = useState(hedef)
  const oncekiRef = useRef(hedef)
  const ilkRef = useRef(true)
  useEffect(() => {
    if (ilkRef.current) { ilkRef.current = false; oncekiRef.current = hedef; setDeger(hedef); return }
    const bas = oncekiRef.current
    if (bas === hedef) return
    oncekiRef.current = hedef
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches) { setDeger(hedef); return }
    const t0 = performance.now(), SURE = 700
    let raf
    const adim = t => {
      const o = Math.min(1, (t - t0) / SURE)
      const yumusak = 1 - Math.pow(1 - o, 3)          // ease-out cubic
      setDeger(bas + (hedef - bas) * yumusak)
      if (o < 1) raf = requestAnimationFrame(adim)
    }
    raf = requestAnimationFrame(adim)
    return () => cancelAnimationFrame(raf)
  }, [hedef])
  return deger
}

/** Değer her değiştiğinde kısa bir parlama sınıfı döndürür. */
function useParlama(deger) {
  const [anahtar, setAnahtar] = useState(0)
  const ilk = useRef(true)
  useEffect(() => {
    if (ilk.current) { ilk.current = false; return }
    setAnahtar(a => a + 1)
  }, [deger])
  return anahtar
}

function Etiket({ children, ipucu }) {
  return (
    <div className="text-[13px] font-medium text-panel-muted" title={ipucu}>{children}</div>
  )
}

function Degisim({ yuzde }) {
  if (yuzde == null) return null
  const arti = yuzde >= 0
  return (
    <span className={`text-xs font-bold ${arti ? 'text-panel-ok' : 'text-red-400'}`}>
      {arti ? '↗' : '↘'} %{SAYI.format(Math.abs(yuzde))}
    </span>
  )
}

// Gradyan dolgulu alan grafiği: düz çizgi bugün, kesikli dün.
// İkisi AYNI ölçekte çizilir, yoksa "dünü geçtik mi" görselden okunamaz.
function Alan({ seri = [], onceki = [], saat = 23, id }) {
  const G = 200, Y = 46, pad = 3
  const enBuyuk = Math.max(1, ...seri, ...onceki)
  const xy = (v, i) => [
    pad + (i / 23) * (G - pad * 2),
    Y - pad - (v / enBuyuk) * (Y - pad * 2.5),
  ]
  const yol = (dizi, sinir) => dizi.slice(0, sinir + 1)
    .map((v, i) => xy(v, i).map(n => n.toFixed(1)).join(',')).join(' ')
  const bugun = yol(seri, saat)
  const sonX = xy(0, Math.min(saat, 23))[0]
  return (
    <svg viewBox={`0 0 ${G} ${Y}`} className="w-full h-[46px] mt-2 overflow-visible"
      preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={`dolgu-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#21d4fd" stopOpacity="0.42" />
          <stop offset="100%" stopColor="#0075ff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`cizgi-${id}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#0075ff" />
          <stop offset="100%" stopColor="#21d4fd" />
        </linearGradient>
      </defs>
      <polyline points={yol(onceki, 23)} fill="none" stroke="#a0aec0"
        strokeWidth="1.2" strokeDasharray="3 3" opacity="0.35" />
      <polygon points={`${pad},${Y - pad} ${bugun} ${sonX},${Y - pad}`}
        fill={`url(#dolgu-${id})`} />
      <polyline points={bugun} fill="none" stroke={`url(#cizgi-${id})`}
        strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

function Kart({ etiket, ipucu, deger, ham, degisim, seri, onceki, saat, ikon, id, bicim }) {
  const sayilan = useSayac(ham)
  const parlama = useParlama(ham)
  return (
    <div className="card card-parlak !p-4 flex flex-col overflow-hidden">
      <div className="flex items-start justify-between gap-2">
        <Etiket ipucu={ipucu}>{etiket}</Etiket>
        {ikon && (
          <span className="w-9 h-9 shrink-0 rounded-[12px] flex items-center justify-center text-base
            bg-gradient-to-br from-panel-accent to-panel-cyan shadow-lg shadow-panel-accent/40">
            {ikon}
          </span>
        )}
      </div>
      {/* Sayı ile grafik ALT ALTA: yan yanayken sabit genişlikli grafik
          "₺10.800" gibi uzun bir değeri sıfır piksele eziyordu. */}
      <div className="mt-1.5 flex items-baseline gap-2 flex-wrap">
        <span key={parlama}
          className="text-[26px] font-bold tabular-nums leading-none grad-metin parla">
          {bicim(sayilan)}
        </span>
        <Degisim yuzde={degisim} />
      </div>
      {seri && <div className="mt-auto"><Alan seri={seri} onceki={onceki} saat={saat} id={id} /></div>}
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

  if (hata) return <p className="text-sm text-red-400">{hata}</p>
  if (!d) return <Iskelet />

  const saat = d.su_anki_saat ?? 23
  const konumEnBuyuk = Math.max(1, ...d.konumlar.map(k => k.oturum))
  const { yeni, geri_donen } = d.musteriler
  const musteriToplam = yeni + geri_donen

  return (
    <div className="flex flex-col lg:flex-row gap-5 lg:h-[calc(100vh-7rem)] page-in">
      {/* ── Sol sütun: metrikler ── */}
      <div className="lg:w-[440px] shrink-0 space-y-3.5 lg:overflow-y-auto lg:pr-1.5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-extrabold flex items-center gap-2.5">
              <span className="w-9 h-9 rounded-[12px] flex items-center justify-center text-lg
                bg-gradient-to-br from-panel-accent2 to-panel-accent shadow-lg shadow-panel-accent2/40">
                🌐
              </span>
              Canlı Görünüm
            </h1>
            <TazeRozet an={tazelendi} />
          </div>
          {store && <p className="mt-1 text-xs text-panel-muted">{store.name}</p>}
        </div>

        <div className="grid grid-cols-2 gap-3.5">
          <Kart id="z" etiket="Şu anki ziyaretçiler" ikon="👥" ham={d.ziyaretci}
            bicim={v => SAYI.format(Math.round(v))}
            ipucu="Son 5 dakika içinde vitrinde hareket eden oturum sayısı" />
          <Kart id="s" etiket="Toplam satışlar" ikon="💳" ham={Number(d.satislar.bugun)}
            bicim={v => TL.format(v)}
            ipucu="Bugünün cirosu (iptal ve iade hariç) — kesikli çizgi dün"
            degisim={d.satislar.degisim} seri={d.satislar.seri}
            onceki={d.satislar.seri_onceki} saat={saat} />
          <Kart id="o" etiket="Oturumlar" ikon="📈" ham={d.oturumlar.bugun}
            bicim={v => SAYI.format(Math.round(v))}
            ipucu="Bugün vitrini ziyaret eden farklı oturum sayısı"
            degisim={d.oturumlar.degisim} seri={d.oturumlar.seri}
            onceki={d.oturumlar.seri_onceki} saat={saat} />
          <Kart id="p" etiket="Siparişler" ikon="🛍️" ham={d.siparisler.bugun}
            bicim={v => SAYI.format(Math.round(v))}
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
          <div className="mt-3 grid grid-cols-3 gap-2">
            <Huni etiket="Aktif sepetler" n={d.davranis.aktif_sepet} ikon="🛒" ton="from-panel-accent to-panel-cyan" />
            <Huni etiket="Ödeme yapıyor" n={d.davranis.odeme_yapiyor} ikon="💳" ton="from-panel-accent2 to-purple-400" />
            <Huni etiket="Satın aldı" n={d.davranis.satin_aldi} ikon="✅" ton="from-emerald-500 to-teal-300" />
          </div>
        </div>

        {/* Konuma göre oturumlar */}
        <div className="card !p-4">
          <Etiket ipucu="Bugünkü oturumların ülke dağılımı">Konuma göre oturumlar</Etiket>
          {d.konumlar.length === 0 ? (
            <p className="mt-3 text-xs text-panel-muted">Bugün henüz ziyaretçi yok.</p>
          ) : (
            <div className="mt-3 space-y-3">
              {d.konumlar.map((k, i) => (
                <div key={k.kod}>
                  <div className="flex justify-between text-xs">
                    <span className="text-panel-muted">{k.ad}</span>
                    <span className="tabular-nums font-semibold">{SAYI.format(k.oturum)}</span>
                  </div>
                  <div className="mt-1.5 h-1.5 rounded-full bg-white/[0.07] overflow-hidden">
                    <div className="h-full rounded-full bg-gradient-to-r from-panel-accent to-panel-cyan
                      transition-[width] duration-700 ease-out"
                      style={{ width: `${Math.max(3, (k.oturum / konumEnBuyuk) * 100)}%`,
                               boxShadow: '0 0 12px rgba(33,212,253,0.55)',
                               transitionDelay: `${i * 60}ms` }} />
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
              <div className="mt-3 h-2.5 rounded-full overflow-hidden flex bg-white/[0.07]">
                <div className="bg-gradient-to-r from-panel-accent to-panel-cyan transition-[width] duration-700"
                  style={{ width: `${(yeni / musteriToplam) * 100}%` }} />
                <div className="bg-gradient-to-r from-panel-accent2 to-purple-400 transition-[width] duration-700"
                  style={{ width: `${(geri_donen / musteriToplam) * 100}%` }} />
              </div>
              <div className="mt-3 flex gap-5 text-xs">
                <Nokta sinif="from-panel-accent to-panel-cyan" etiket="Yeni" n={yeni} />
                <Nokta sinif="from-panel-accent2 to-purple-400" etiket="Geri dönen" n={geri_donen} />
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
            <ul className="mt-3 space-y-1.5">
              {d.aktivite.map((a, i) => (
                <li key={`${a.zaman}-${i}`}
                  className="flex items-center gap-2.5 text-xs rounded-[12px] px-2 py-2
                    bg-white/[0.03] hover:bg-white/[0.07] transition-colors animate-slidein"
                  style={{ animationDelay: `${i * 45}ms` }}>
                  <span className="w-7 h-7 shrink-0 rounded-[10px] flex items-center justify-center
                    bg-white/[0.07] border border-panel-border">
                    {a.tur === 'siparis' ? '🛍️' : a.tur === 'odeme_paid' ? '✅'
                      : a.tur === 'odeme_failed' ? '⚠️' : '🕐'}
                  </span>
                  <span className="font-semibold text-white">{a.kim}</span>
                  <span className="text-panel-muted flex-1 truncate">{a.metin}</span>
                  {a.tutar && <span className="tabular-nums font-semibold text-panel-cyan">
                    {TL.format(Number(a.tutar))}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ── Sağ: küre ── */}
      <div className="relative flex-1 min-h-[420px] card !p-0 overflow-hidden">
        <Kure konumlar={d.konumlar} />
      </div>
    </div>
  )
}

function Huni({ etiket, n, ikon, ton }) {
  const sayilan = useSayac(n)
  return (
    <div className="rounded-[16px] p-3 bg-white/[0.035] border border-panel-border">
      <span className={`w-8 h-8 rounded-[11px] flex items-center justify-center text-sm
        bg-gradient-to-br ${ton} shadow-lg`}>{ikon}</span>
      <div className="mt-2 text-[11px] text-panel-muted leading-tight">{etiket}</div>
      <div className="text-2xl font-bold tabular-nums mt-0.5">{SAYI.format(Math.round(sayilan))}</div>
    </div>
  )
}

function Nokta({ sinif, etiket, n }) {
  return (
    <span className="flex items-center gap-2">
      <span className={`w-2.5 h-2.5 rounded-full bg-gradient-to-br ${sinif}`} />
      <span className="text-panel-muted">{etiket}</span>
      <span className="tabular-nums font-bold">{n}</span>
    </span>
  )
}

// "Az önce" rozeti — verinin canlı olduğunu gösterir. Sekme gizliyken
// güncelleme durduğu için geri dönüldüğünde yaşın görünmesi önemli.
function TazeRozet({ an }) {
  const [, tik] = useState(0)
  useEffect(() => { const t = setInterval(() => tik(v => v + 1), 5000); return () => clearInterval(t) }, [])
  if (!an) return null
  const sn = Math.floor((Date.now() - an) / 1000)
  const metin = sn < 15 ? 'Az önce' : sn < 60 ? `${sn} sn önce` : `${Math.floor(sn / 60)} dk önce`
  const taze = sn < 30
  return (
    <span className="flex items-center gap-2 text-xs text-panel-muted bg-white/[0.05]
      border border-panel-border rounded-full px-2.5 py-1">
      <span className="relative flex w-2 h-2">
        {taze && <span className="absolute inset-0 rounded-full bg-panel-accent nabiz-halka" />}
        <span className={`relative w-2 h-2 rounded-full ${taze ? 'bg-panel-accent' : 'bg-panel-muted/50'}`} />
      </span>
      {metin}
    </span>
  )
}

function Iskelet() {
  return (
    <div className="flex flex-col lg:flex-row gap-5 lg:h-[calc(100vh-7rem)]">
      <div className="lg:w-[440px] shrink-0 space-y-3.5">
        <div className="skeleton h-9 w-56" />
        <div className="grid grid-cols-2 gap-3.5">
          {[0, 1, 2, 3].map(i => <div key={i} className="skeleton h-[132px]" />)}
        </div>
        <div className="skeleton h-32" /><div className="skeleton h-44" />
      </div>
      <div className="flex-1 min-h-[420px] skeleton" />
    </div>
  )
}
