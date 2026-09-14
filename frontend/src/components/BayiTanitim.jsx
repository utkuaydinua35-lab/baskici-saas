/**
 * Bayi tanıtım turu — yeni özellikleri adım adım, görselle anlatır.
 *
 * Birden fazla güncelleme bekliyorsa adımları ART ARDA gösterir (eskiden
 * yeniye). Kapatınca da bitirince de "görüldü" sayılır: tanıtım zorla izletilmez,
 * isteyen Yenilikler sayfasından tekrar açar.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import TanitimGorseli from './BayiTanitimGorselleri'

export default function BayiTanitim({ guncellemeler, onKapat, tekrar = false }) {
  // Tüm güncellemelerin adımları tek listede; her adım hangi güncellemeden geldiğini bilir.
  const adimlar = useMemo(() => guncellemeler.flatMap((g) =>
    g.tanitim.map((a, i) => ({ ...a, guncelleme: g, sira: i, toplam: g.tanitim.length }))),
  [guncellemeler])
  const [i, setI] = useState(0)
  const [yon, setYon] = useState(1)
  const kutu = useRef(null)
  const a = adimlar[i]
  const son = i === adimlar.length - 1

  const git = (n) => { setYon(n > i ? 1 : -1); setI(n) }
  const ileri = () => (son ? onKapat(true) : git(i + 1))
  const geri = () => i > 0 && git(i - 1)

  useEffect(() => {
    const tus = (e) => {
      if (e.key === 'Escape') onKapat(false)
      else if (e.key === 'ArrowRight') ileri()
      else if (e.key === 'ArrowLeft') geri()
    }
    document.addEventListener('keydown', tus)
    const eski = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    kutu.current?.focus()
    return () => { document.removeEventListener('keydown', tus); document.body.style.overflow = eski }
  })

  // Kaydırarak geçiş (telefon)
  const dokunX = useRef(null)
  const dokunBasla = (e) => { dokunX.current = e.touches[0].clientX }
  const dokunBit = (e) => {
    if (dokunX.current == null) return
    const fark = e.changedTouches[0].clientX - dokunX.current
    dokunX.current = null
    if (fark < -50) ileri()
    else if (fark > 50) geri()
  }

  if (!a) return null
  const tarih = new Date(a.guncelleme.tarih).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' })

  return createPortal(
    <div className="fixed inset-0 z-[150] flex items-end sm:items-center justify-center bg-black/70 sm:p-4 animate-fadein"
         role="dialog" aria-modal="true" aria-label="Yenilikler"
         onMouseDown={(e) => e.target === e.currentTarget && onKapat(false)}>
      <div ref={kutu} tabIndex={-1}
           onTouchStart={dokunBasla} onTouchEnd={dokunBit}
           className="tanitim-kutu w-full sm:max-w-lg bg-brand-card border border-brand-border
                      rounded-t-3xl sm:rounded-3xl shadow-2xl outline-none
                      pb-[calc(1rem_+_env(safe-area-inset-bottom))] sm:pb-5 max-h-[92dvh] overflow-y-auto">
        <div className="flex items-center gap-2 px-5 pt-4">
          <span className="shrink-0 whitespace-nowrap text-[10px] uppercase tracking-[0.14em] px-2 py-0.5 rounded-full
                           bg-accent/15 text-accent border border-accent/25">{tekrar ? 'Tanıtım' : '✨ Yeni'}</span>
          <span className="text-[11.5px] text-gray-500 truncate">{a.guncelleme.baslik} · {tarih}</span>
          <button onClick={() => onKapat(false)} aria-label="Kapat"
                  className="ml-auto -mr-2 w-10 h-10 grid place-items-center rounded-xl text-gray-500 hover:text-gray-200">✕</button>
        </div>

        <div key={i} className={`px-5 pt-2 ${yon > 0 ? 'tanitim-adim-ileri' : 'tanitim-adim-geri'}`}>
          <TanitimGorseli ad={a.gorsel} />
          <h2 className="text-[17px] font-semibold text-white tracking-tight mt-4">{a.baslik}</h2>
          <p className="text-[13.5px] text-gray-400 leading-relaxed mt-1.5">{a.metin}</p>
        </div>

        <div className="flex items-center gap-3 px-5 mt-5">
          <div className="flex items-center gap-1.5" aria-label={`Adım ${i + 1} / ${adimlar.length}`}>
            {adimlar.map((_, n) => (
              <button key={n} onClick={() => git(n)} aria-label={`${n + 1}. adım`}
                      className={`h-1.5 rounded-full transition-all duration-300 ${n === i ? 'w-6 bg-accent' : 'w-1.5 bg-white/15 hover:bg-white/30'}`} />
            ))}
          </div>
          <div className="ml-auto flex items-center gap-2">
            {i > 0 && (
              <button onClick={geri} className="btn-secondary !py-2 !px-4 !text-[13px]">Geri</button>
            )}
            <button onClick={ileri} className="btn-primary !py-2 !px-5 !text-[13px]">
              {son ? 'Anladım' : 'İleri'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
