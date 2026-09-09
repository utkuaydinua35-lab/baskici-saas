import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { getToken } from '../lib/api'
import { mutlak } from '../lib/taban'

/**
 * Görseli AYNI SAYFADA büyütür — yeni sekme yok, indirme yok.
 *
 * Kalite: JPG/PNG'de /storage'daki dosyanın KENDİSİ gösterilir (küçük resim
 * zaten aynı dosyadır), yani kayıpsız. PDF'te kayıtlı küçük resim 100 dpi ve
 * büyütülünce bozuluyor; onun yerine /onizleme ucundan 200 dpi yeniden
 * çizdiriliyor.
 */
export default function GorselBuyutec({ acik, kapat, kaynak, tasarimId, format, baslik }) {
  const [pdfUrl, setPdfUrl] = useState(null)
  const [hata, setHata] = useState('')
  const [yakinlas, setYakinlas] = useState(false)

  const pdf = (format || '').toLowerCase() === 'pdf' && !!tasarimId
  const url = pdf ? pdfUrl : (kaynak || null)

  useEffect(() => {
    if (!acik || !pdf) return
    let iptal = false
    let olusan = null
    ;(async () => {
      try {
        const r = await fetch(mutlak(`/api/designs/${tasarimId}/onizleme?dpi=200`),
          { headers: { Authorization: `Bearer ${getToken()}` } })
        if (!r.ok) throw new Error()
        olusan = URL.createObjectURL(await r.blob())
        if (!iptal) setPdfUrl(olusan)
      } catch {
        // Yüksek çözünürlük alınamadıysa küçük resme düş ama SÖYLE —
        // sessizce bulanık görsel vermek kullanıcıyı yanıltır.
        if (!iptal) { setPdfUrl(kaynak || null); setHata('Yüksek çözünürlük alınamadı') }
      }
    })()
    return () => { iptal = true; if (olusan) URL.revokeObjectURL(olusan) }
  }, [acik, pdf, kaynak, tasarimId])

  useEffect(() => {
    if (!acik) return
    const esc = (e) => { if (e.key === 'Escape') kapat() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [acik, kapat])

  if (!acik) return null
  return createPortal((
    <div className="fixed inset-0 z-[200] flex flex-col animate-fadein"
         style={{ background: 'rgb(6 4 12 / 0.94)' }} onClick={kapat}>
      <div className="flex items-center justify-between px-4 py-3 shrink-0"
           onClick={(e) => e.stopPropagation()}>
        <div className="min-w-0">
          <div className="text-[13px] text-gray-200 truncate">{baslik || 'Tasarım'}</div>
          {hata && <div className="text-[11px] text-amber-400">{hata}</div>}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setYakinlas((y) => !y)}
                  className="text-[12px] px-3 py-1.5 rounded-lg border border-white/20
                             text-gray-200 hover:bg-white/10">
            {yakinlas ? 'Sığdır' : 'Yakınlaştır'}
          </button>
          <button onClick={kapat} aria-label="Kapat"
                  className="w-9 h-9 grid place-items-center rounded-lg border border-white/20
                             text-gray-200 hover:bg-white/10 text-xl leading-none">×</button>
        </div>
      </div>
      <div className={`flex-1 min-h-0 p-4 ${yakinlas
                        ? 'overflow-auto' : 'flex items-center justify-center overflow-hidden'}`}>
        {url
          ? <img src={url} alt={baslik || ''}
                 onClick={(e) => { e.stopPropagation(); setYakinlas((y) => !y) }}
                 className={yakinlas
                   ? 'max-w-none cursor-zoom-out'
                   : 'max-w-full max-h-full object-contain cursor-zoom-in'} />
          : <div className="text-[13px] text-gray-400">Yükleniyor…</div>}
      </div>
      <p className="text-center text-[11px] text-gray-600 pb-3 shrink-0">
        Kapatmak için Esc ya da boşluğa tıkla
      </p>
    </div>
  ), document.body)
}
