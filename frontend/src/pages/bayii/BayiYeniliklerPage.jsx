/**
 * Güncelleme notları — bayi paneline gelen yenilikler, sürüm sürüm.
 *
 * İçerik lib/bayiGuncellemeler.js'te. Tanıtımı olan bir güncellemenin turu
 * buradan tekrar izlenebilir (ilk girişte kapatılmış olsa bile).
 */
import { useOutletContext } from 'react-router-dom'
import { GUNCELLEMELER, TUR_ETIKET, goruldu as gorulduSiniri } from '../../lib/bayiGuncellemeler'

const tarihYaz = (t) => new Date(t).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })

export default function BayiYeniliklerPage() {
  const { goruldu, tanitimAc } = useOutletContext() || {}
  // Sayfa açıkken tur kapatılınca rozetler hemen kalkmasın diye ilk değer esas.
  const sinir = goruldu === undefined ? Infinity : gorulduSiniri(goruldu)
  const liste = [...GUNCELLEMELER].sort((a, b) => b.surum - a.surum)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight">Yenilikler</h1>
        <p className="text-[13px] text-gray-500 mt-1">
          Bayi paneline gelen güncellemeler. Tanıtımı olanları buradan tekrar izleyebilirsin.
        </p>
      </div>

      <div className="bayi-zaman space-y-4">
        {liste.map((g, i) => {
          const yeni = g.surum > sinir
          return (
            <article key={g.surum} className={`relative card bayi-sira ${yeni ? '!border-accent/40' : ''}`}
                     style={{ '--gecikme': `${i * 50}ms` }}>
              <span className="bayi-zaman-nokta" style={yeni ? { borderColor: 'rgb(var(--accent-rgb))',
                background: 'rgb(var(--accent-rgb))' } : undefined} />
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-mono text-gray-500 border border-white/10 rounded px-1.5 py-0.5">
                  v1.{g.surum}
                </span>
                <span className="text-[12px] text-gray-500">{tarihYaz(g.tarih)}</span>
                {yeni && (
                  <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full
                                   bg-accent/15 text-accent border border-accent/25">Yeni</span>
                )}
              </div>
              <h2 className="text-[16px] font-semibold text-white tracking-tight mt-2">{g.baslik}</h2>
              <p className="text-[13px] text-gray-400 mt-1">{g.ozet}</p>

              <ul className="mt-3 space-y-2">
                {g.degisiklikler.map((d, n) => {
                  const e = TUR_ETIKET[d.tur] || TUR_ETIKET.yeni
                  return (
                    <li key={n} className="flex items-start gap-2.5 text-[13px] text-gray-300 leading-relaxed">
                      <span className={`shrink-0 mt-[1px] text-[10px] px-1.5 py-0.5 rounded border ${e.sinif}`}>{e.ad}</span>
                      <span>{d.metin}</span>
                    </li>
                  )
                })}
              </ul>

              {g.tanitim?.length > 0 && tanitimAc && (
                <button onClick={() => tanitimAc([g])}
                        className="mt-4 inline-flex items-center gap-2 text-[13px] text-accent hover:brightness-125 transition">
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M8 5v14l11-7z" /></svg>
                  Tanıtımı izle · {g.tanitim.length} adım
                </button>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
