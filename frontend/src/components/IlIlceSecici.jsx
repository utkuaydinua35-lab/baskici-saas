/**
 * Il / ilce secici — bagimli iki dropdown.
 *
 * Serbest metin girilen adreslerde yazim hatasi kargo etiketini bozuyor;
 * liste 81 ili ve ilcelerini sunucudan alir (statik, gunluk cache'li).
 */
import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'

export default function IlIlceSecici({ il, ilce, onDegis }) {
  const [veri, setVeri] = useState(null)

  useEffect(() => {
    api.get('/api/bayii/il-ilce').then((d) => setVeri(d.items || {})).catch(() => setVeri({}))
  }, [])

  const iller = useMemo(() => Object.keys(veri || {}).sort((a, b) => a.localeCompare(b, 'tr')), [veri])
  const ilceler = useMemo(() => (veri?.[il] || []), [veri, il])

  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">İl</label>
        <select value={il || ''} disabled={!veri}
                onChange={(e) => onDegis(e.target.value, '')}  // il degisti -> ilce sifirlanir
                className="input w-full appearance-none disabled:opacity-50">
          <option value="">{veri ? 'İl seç' : 'Yükleniyor…'}</option>
          {iller.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">İlçe</label>
        <select value={ilce || ''} disabled={!il}
                onChange={(e) => onDegis(il, e.target.value)}
                className="input w-full appearance-none disabled:opacity-50">
          <option value="">{il ? 'İlçe seç' : 'Önce il seç'}</option>
          {ilceler.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      </div>
    </div>
  )
}
