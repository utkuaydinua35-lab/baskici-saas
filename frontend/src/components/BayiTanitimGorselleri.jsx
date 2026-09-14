/**
 * Bayi tanıtımlarının GÖRSELLERİ — ekran görüntüsü değil, canlı mini arayüz.
 *
 * Neden çizim: ekran görüntüsü arayüz değişince bayatlar ve telefonda bulanık
 * görünür. Bunlar panelin kendi renkleri/sınıflarıyla çizilir; imleç ve vurgu
 * halkası "nereye dokunacağını" gösterir. prefers-reduced-motion'da hareket yok.
 *
 * Yeni görsel: aşağıya bir bileşen yaz, GORSELLER'e ekle, bayiGuncellemeler.js'te
 * adıyla kullan.
 */
import { useEffect, useState } from 'react'

const hareketAzalt = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Görsel sahnesi — sabit oranlı, koyu çerçeve. */
function Sahne({ children, className = '' }) {
  return (
    <div className={`tanitim-sahne relative w-full aspect-[16/10] rounded-2xl overflow-hidden
                     border border-white/10 p-4 sm:p-5 ${className}`}>
      {children}
    </div>
  )
}

/** Dokunma işareti: nabız atan halka. */
function Dokun({ className = '' }) {
  return (
    <span aria-hidden className={`pointer-events-none absolute ${className}`}>
      <span className="tanitim-nabiz absolute inset-0 rounded-full border-2" />
      <span className="absolute inset-[30%] rounded-full bg-white/90 shadow-[0_0_12px_rgba(255,255,255,.6)]" />
    </span>
  )
}

/** Harf harf yazılan metin (döngü). */
function Yazan({ metin, hiz = 90, bekle = 1800 }) {
  const [n, setN] = useState(() => (hareketAzalt() ? metin.length : 0))
  useEffect(() => {
    if (hareketAzalt()) return
    let i = 0
    let t
    const adim = () => {
      i += 1
      setN(Math.min(i, metin.length))
      t = setTimeout(() => {
        if (i >= metin.length) { i = 0; setN(0); t = setTimeout(adim, 400) } else adim()
      }, i >= metin.length ? bekle : hiz)
    }
    t = setTimeout(adim, 500)
    return () => clearTimeout(t)
  }, [metin, hiz, bekle])
  return (
    <>
      {metin.slice(0, n)}
      <span className="tanitim-kursor inline-block w-[2px] h-[1em] align-[-0.15em] bg-white/80 ml-px" />
    </>
  )
}

const Etiket = ({ children }) => (
  <div className="text-[9px] sm:text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">{children}</div>
)

// ─── Hepsiburada ────────────────────────────────────────────
function HbKanal() {
  const kanallar = [
    ['Trendyol', '#f27a1a'], ['Shopier', '#8b5cf6'], ['Instagram', '#e1306c'], ['Hepsiburada', '#ff6000'],
  ]
  return (
    <Sahne>
      <Etiket>Sipariş nereden geldi?</Etiket>
      <div className="grid grid-cols-2 gap-2 sm:gap-2.5">
        {kanallar.map(([ad, renk]) => {
          const secili = ad === 'Hepsiburada'
          return (
            <div key={ad} className={`relative rounded-xl border px-2 py-2.5 sm:py-3 text-center text-[11px] sm:text-[13px]
                  ${secili ? 'border-accent/60 bg-accent/15 text-white tanitim-sec' : 'border-white/10 text-gray-500'}`}>
              <span className="block w-2 h-2 rounded-full mx-auto mb-1.5" style={{ background: renk }} />
              {ad}
              {secili && <Dokun className="w-9 h-9 -right-2 -bottom-2" />}
            </div>
          )
        })}
      </div>
      <p className="text-[10px] sm:text-[11px] text-gray-500 mt-2.5">
        Adres Hepsiburada’dan gelir — alıcı adı ve kargo entegrasyon kodu gerekli
      </p>
    </Sahne>
  )
}

function HbKod() {
  return (
    <Sahne>
      <Etiket>Alıcı adı soyadı</Etiket>
      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[12px] sm:text-[13px] text-gray-200 mb-3">
        Ayşe Yılmaz
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-2 sm:gap-3 items-end">
        <div>
          <Etiket>Kargo entegrasyon kodu <span className="text-red-400">*</span></Etiket>
          <div className="relative rounded-xl border border-accent/60 bg-accent/10 px-3 py-2 font-mono text-[12px] sm:text-[14px] text-white tracking-wide tanitim-sec">
            <Yazan metin="4010 5913 4531 2288" />
          </div>
        </div>
        <div>
          <Etiket>Kargo firması</Etiket>
          <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[12px] sm:text-[13px] text-gray-200 whitespace-nowrap">
            Sürat Kargo <span className="text-gray-500">▾</span>
          </div>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2 text-[10px] sm:text-[11px]">
        <span className="rounded-full border border-emerald-500/30 bg-emerald-500/15 text-emerald-300 px-2 py-0.5">✓ Boşluklar otomatik silinir</span>
        <span className="rounded-full border border-sky-500/30 bg-sky-500/15 text-sky-300 px-2 py-0.5">Sürat otomatik seçili</span>
      </div>
    </Sahne>
  )
}

/** Barkod görünümü — yalnız görsel (gerçek barkod değil). */
function SahteBarkod({ kod }) {
  const cubuklar = []
  let x = 0
  for (let i = 0; i < 70; i++) {
    const ch = kod.charCodeAt(i % kod.length)
    const g = 1 + ((ch * (i + 3)) % 3)
    if (i % 2 === 0) cubuklar.push(<rect key={i} x={x} y="0" width={g} height="100" fill="#000" />)
    x += g
  }
  return (
    <svg viewBox={`0 0 ${x} 100`} preserveAspectRatio="none" className="w-full h-full">{cubuklar}</svg>
  )
}

function HbEtiket() {
  return (
    <Sahne className="flex items-center justify-center gap-4 sm:gap-6">
      <div className="tanitim-etiket h-full aspect-[2/3] bg-white rounded-md shadow-2xl flex flex-col items-center px-[6%] py-[5%] text-black">
        <div className="text-[6px] sm:text-[8px] text-gray-500 leading-none">ALICI</div>
        <div className="text-[9px] sm:text-[13px] font-bold leading-tight mt-0.5">AYŞ* YIL***</div>
        <div className="text-[8px] sm:text-[11px] font-bold leading-tight">SÜRAT KARGO</div>
        <div className="w-full border-t border-black/70 my-[5%]" />
        <div className="w-full flex-1 min-h-0"><SahteBarkod kod="4010591345312288" /></div>
        <div className="text-[8px] sm:text-[12px] font-bold mt-[4%] tracking-tight">4010591345312288</div>
      </div>
      <ul className="space-y-2 text-[10.5px] sm:text-[12.5px] text-gray-300 max-w-[48%]">
        <li className="tanitim-belir" style={{ '--gecikme': '0.1s' }}><b className="text-white">Maskeli ad</b> — ilk 3 harf açık</li>
        <li className="tanitim-belir" style={{ '--gecikme': '0.35s' }}><b className="text-white">Kargo firması</b> — seçtiğin firma</li>
        <li className="tanitim-belir" style={{ '--gecikme': '0.6s' }}><b className="text-white">Barkod</b> — etiketi kaplar, şube okutur</li>
        <li className="tanitim-belir" style={{ '--gecikme': '0.85s' }}><b className="text-white">Rakamlar</b> — kodun kendisi</li>
      </ul>
    </Sahne>
  )
}

// ─── Genel ──────────────────────────────────────────────────
function MobilMenu() {
  return (
    <Sahne className="flex items-center justify-center">
      <div className="h-full aspect-[9/16] rounded-[18px] border-2 border-white/15 bg-[#0a0613] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-2.5 py-2 border-b border-white/5">
          <span className="flex items-center gap-1.5 text-[8px] sm:text-[10px] text-white font-semibold">
            <span className="w-3 h-3 rounded bg-accent" />BERNZ
          </span>
          <span className="relative w-5 h-5 sm:w-6 sm:h-6 rounded-md border border-white/10 grid place-items-center text-[9px] text-gray-300">
            ✕<Dokun className="w-7 h-7 -right-1.5 -bottom-1.5" />
          </span>
        </div>
        <div className="p-1.5 space-y-1 text-[8px] sm:text-[10px] tanitim-belir">
          {['Panel', 'Siparişlerim', 'Yeni Sipariş', 'Cari Hesap', 'Yenilikler'].map((m, i) => (
            <div key={m} className={`rounded-md px-2 py-1.5 ${i === 0 ? 'bg-accent/20 text-white' : 'text-gray-400'}`}>{m}</div>
          ))}
          <div className="border-t border-white/5 pt-1 mt-1 rounded-md px-2 py-1.5 text-red-300 bg-red-500/10">Çıkış yap</div>
        </div>
      </div>
    </Sahne>
  )
}

function Onizleme() {
  return (
    <Sahne className="flex items-center gap-4 sm:gap-6">
      <div className="h-full aspect-[1/2] rounded-[22%/11%] border-2 border-white/20 bg-gradient-to-br from-fuchsia-500/40 via-accent/40 to-sky-400/30 relative shrink-0">
        <span className="absolute top-[4%] left-[8%] w-[34%] aspect-square rounded-[30%] bg-black/50 border border-white/15" />
      </div>
      <div className="flex-1 space-y-2">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[11px] sm:text-[13px] text-gray-300">📄 tasarim.jpg <span className="text-gray-500">· baskı dosyası</span></div>
        <div className="relative rounded-xl border border-dashed border-accent/60 bg-accent/10 px-3 py-2 text-[11px] sm:text-[13px] text-white tanitim-sec">
          + Önizleme görseli ekle <span className="text-gray-400">(isteğe bağlı)</span>
          <Dokun className="w-8 h-8 -right-2 -bottom-2" />
        </div>
        <p className="text-[10px] sm:text-[11px] text-gray-500">Önizleme baskıya girmez; kılıfın son halini bize gösterir.</p>
      </div>
    </Sahne>
  )
}

function CokluUrun() {
  return (
    <Sahne>
      <div className="space-y-2">
        {[['iPhone 15 Pro', '× 2'], ['Galaxy S24', '× 1']].map(([m, a], i) => (
          <div key={m} className="tanitim-belir flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.03] p-2"
               style={{ '--gecikme': `${i * 0.25}s` }}>
            <span className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-gradient-to-br from-accent/50 to-sky-400/40 shrink-0" />
            <span className="flex-1 text-[11px] sm:text-[13px] text-gray-200">{m}</span>
            <span className="text-[11px] sm:text-[12px] text-gray-500">{a}</span>
          </div>
        ))}
        <div className="relative rounded-xl border border-dashed border-accent/60 bg-accent/10 py-2 text-center text-[11px] sm:text-[13px] text-white tanitim-sec">
          + Ürün ekle
          <Dokun className="w-8 h-8 right-[38%] -bottom-3" />
        </div>
      </div>
    </Sahne>
  )
}

function Katalog() {
  const renkler = ['from-rose-400/60 to-orange-300/40', 'from-accent/60 to-sky-400/40',
    'from-emerald-400/50 to-teal-300/40', 'from-amber-300/60 to-pink-400/40']
  return (
    <Sahne>
      <div className="grid grid-cols-2 gap-2 mb-3 text-[11px] sm:text-[13px]">
        <div className="rounded-xl border border-white/10 py-2 text-center text-gray-500">Tasarım yükle</div>
        <div className="rounded-xl border border-accent/60 bg-accent/15 py-2 text-center text-white">Tasarımlarımdan seç</div>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {renkler.map((r, i) => (
          <div key={i} className={`relative aspect-[3/4] rounded-lg bg-gradient-to-br ${r}
                ${i === 1 ? 'ring-2 ring-accent tanitim-sec' : 'opacity-70'}`}>
            {i === 1 && (
              <>
                <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-accent text-[9px] text-white grid place-items-center">✓</span>
                <Dokun className="w-8 h-8 -right-2 -bottom-2" />
              </>
            )}
          </div>
        ))}
      </div>
    </Sahne>
  )
}

const GORSELLER = {
  hbKanal: HbKanal,
  hbKod: HbKod,
  hbEtiket: HbEtiket,
  mobilMenu: MobilMenu,
  onizleme: Onizleme,
  cokluUrun: CokluUrun,
  katalog: Katalog,
}

export default function TanitimGorseli({ ad }) {
  const G = GORSELLER[ad]
  return G ? <G /> : null
}
