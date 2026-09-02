import { useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'
import { useToast } from './Toast'

/**
 * "Ölçüsü tanımlı değil" hatasından DOĞRUDAN model ölçüsü tanımlar.
 *
 * Kullanıcıyı Telefon Modelleri ekranına yollamak, hatayı okuyup oraya gidip
 * kaydı aramasını ve geri dönmesini gerektiriyordu. Buradan girip PDF'i hemen
 * tekrar deniyor.
 *
 * Anahtar sunucuda PDF motorunun ARADIĞI fonksiyonla üretilir; kaydettikten
 * sonra sunucu gerçekten bulunabildiğini doğrular (`dogrulandi`).
 */
export default function OlcuTanimlaDialog({ hedef, kapat, onTamam }) {
  const toast = useToast()
  const [olcu, setOlcu] = useState(() =>
    Object.fromEntries(hedef.modeller.map((m) => [m, { w: '', h: '', r: '1' }])))
  const [bekle, setBekle] = useState(false)
  const [biten, setBiten] = useState({})

  const degis = (m, alan, v) =>
    setOlcu((o) => ({ ...o, [m]: { ...o[m], [alan]: v } }))

  const kaydet = async () => {
    setBekle(true)
    const yeniBiten = { ...biten }
    let hata = false
    for (const m of hedef.modeller) {
      if (biten[m]) continue
      const { w, h, r } = olcu[m]
      if (!Number(w) || !Number(h)) { hata = true; toast.error(`${m}: en ve boy gerekli`); continue }
      try {
        const res = await api.post('/api/phone-models/olcu-tanimla', {
          model: m, width_cm: Number(w), height_cm: Number(h),
          radius_cm: Number(r) || 0,
        })
        if (!res.dogrulandi) {
          hata = true
          toast.error(`${m}: kaydedildi ama PDF motoru hâlâ bulamıyor — model adını kontrol et`)
          continue
        }
        yeniBiten[m] = res.spec_key
      } catch (e) { hata = true; toast.error(`${m}: ${e.detail || 'kaydedilemedi'}`) }
    }
    setBiten(yeniBiten)
    setBekle(false)
    if (!hata && hedef.modeller.every((m) => yeniBiten[m])) {
      toast.success('Ölçüler tanımlandı — PDF tekrar deneniyor')
      onTamam()
    }
  }

  return createPortal((
    <div className="fixed inset-0 z-[130] grid place-items-center p-4"
         style={{ background: 'rgb(6 4 12 / 0.86)' }}
         onMouseDown={(e) => e.target === e.currentTarget && kapat()}>
      <div className="rounded-2xl w-full max-w-lg p-5 border border-white/10 max-h-[86vh] overflow-y-auto"
           style={{ background: 'rgb(23 16 43)' }}>
        <h3 className="text-[15px] font-semibold text-white mb-1">
          Ölçüsü tanımlı olmayan model
        </h3>
        <p className="text-[12px] text-gray-400 mb-4">
          Bu ölçüler girilmeden kalıp basılamaz — yanlış boyda basmamak için PDF
          hiç üretilmiyor. Kılıfın <b>gerçek</b> dış ölçüsünü santimetre gir.
        </p>

        <div className="space-y-3">
          {hedef.modeller.map((m) => (
            <div key={m} className={`rounded-xl border p-3 ${biten[m]
              ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-white/10 bg-white/[0.02]'}`}>
              <div className="text-[13px] text-gray-200 mb-2 flex items-center gap-2">
                {m}
                {biten[m] && <span className="text-[11px] text-emerald-400">✓ {biten[m]}</span>}
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[['w', 'En (cm)', '7.6'], ['h', 'Boy (cm)', '16.0'], ['r', 'Köşe (cm)', '1.0']]
                  .map(([alan, etiket, ornek]) => (
                    <label key={alan} className="block">
                      <span className="text-[11px] text-gray-500">{etiket}</span>
                      <input type="number" step="0.05" min="0" placeholder={ornek}
                             value={olcu[m][alan]} disabled={!!biten[m]}
                             onChange={(e) => degis(m, alan, e.target.value)}
                             className="input w-full mt-0.5 !text-[13px] disabled:opacity-50" />
                    </label>
                  ))}
              </div>
            </div>
          ))}
        </div>

        <p className="text-[10.5px] text-gray-600 mt-3">
          Kayıt varsa ölçüleri güncellenir, yoksa yeni model oluşturulur.
          Telefon Modelleri ekranından sonradan düzenleyebilirsin.
        </p>

        <div className="flex gap-2 mt-4">
          <button onClick={kapat}
                  className="flex-1 px-3 py-2 rounded-lg border border-white/15
                             text-[13px] text-gray-300 hover:bg-white/10">
            Vazgeç
          </button>
          <button onClick={kaydet} disabled={bekle}
                  className="flex-1 btn-primary !text-[13px] disabled:opacity-50">
            {bekle ? 'Kaydediliyor…' : 'Kaydet ve PDF’i tekrar dene'}
          </button>
        </div>
      </div>
    </div>
  ), document.body)
}
