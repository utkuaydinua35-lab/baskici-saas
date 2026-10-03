/**
 * Bayinin kendi logosu — sohbette mesajlarının yanında görünür.
 * Yükle / değiştir / kaldır: yanlış dosya seçilirse geri dönülebilsin.
 */
import { useRef, useState } from 'react'
import { api, fetchYetkili } from '../lib/api'
import { mutlak } from '../lib/taban'
import { Avatar } from './SohbetParcalari'

export default function BayiLogo({ logoUrl, ad, onDegisti }) {
  const [busy, setBusy] = useState(false)
  const [hata, setHata] = useState('')
  const dosyaRef = useRef(null)

  const yukle = async (dosya) => {
    if (!dosya) return
    setBusy(true); setHata('')
    try {
      const fd = new FormData()
      fd.append('file', dosya)
      const r = await fetchYetkili(mutlak('/api/bayii/logo'), { method: 'POST', body: fd })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'Yüklenemedi')
      onDegisti?.(d.logo_url)
    } catch (e) { setHata(e.message || 'Yüklenemedi') }
    finally { setBusy(false); if (dosyaRef.current) dosyaRef.current.value = '' }
  }

  const kaldir = async () => {
    setBusy(true); setHata('')
    try { await api.del('/api/bayii/logo'); onDegisti?.(null) }
    catch (e) { setHata(e.detail || 'Kaldırılamadı') }
    finally { setBusy(false) }
  }

  return (
    <div className="card flex items-center gap-3">
      <Avatar url={logoUrl} ad={ad} boyut={44} />
      <div className="min-w-0 flex-1">
        <div className="text-sm text-gray-200">Logon</div>
        <div className="text-[11.5px] text-gray-500">
          Sohbette mesajlarının yanında görünür. PNG/JPG, en fazla 3 MB.
        </div>
        {hata && <div className="text-[11.5px] text-red-300 mt-1">{hata}</div>}
      </div>
      <input ref={dosyaRef} type="file" accept="image/png,image/jpeg,image/webp" id="bayi-logo"
             className="hidden" onChange={e => yukle(e.target.files?.[0])} />
      <div className="flex gap-2 shrink-0">
        <label htmlFor="bayi-logo"
               className={`btn-secondary !text-xs !py-1.5 cursor-pointer ${busy ? 'opacity-50 pointer-events-none' : ''}`}>
          {logoUrl ? 'Değiştir' : 'Logo yükle'}
        </label>
        {logoUrl && (
          <button onClick={kaldir} disabled={busy}
                  className="text-xs px-2 py-1.5 rounded-lg text-red-300/90 hover:bg-red-500/10 disabled:opacity-50">
            Kaldır
          </button>
        )}
      </div>
    </div>
  )
}
