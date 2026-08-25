/**
 * Toplu kalıp silme onayı.
 *
 * Silmenin sonucu kalıbın BASILMIŞ olup olmamasına göre DEĞİŞİR
 * (backend: molds._delete_mold_inner):
 *   • basılmamış → içindeki kalemler plana geri döner ("kalıp bekliyor")
 *   • basılmış   → kalemler ÜRETİLMİŞ sayılır, plana DÖNMEZ (çift baskı koruması)
 * Karışık seçimde ikisi de olabileceği için sayılar ayrı ayrı gösteriliyor —
 * yönetici neyi onayladığını görmeden silmesin.
 */
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const ONAY_SOZU = 'SİL'

export default function TopluKalipSilDialog({ open, kaliplar, onClose, onDeleted }) {
  const [onay, setOnay] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (open) { setOnay(''); setErr(''); setBusy(false) }
  }, [open])

  if (!open || !kaliplar?.length) return null

  const basilmis = kaliplar.filter((m) => m.basildi)
  const bekleyen = kaliplar.filter((m) => !m.basildi)
  const kilifToplam = kaliplar.reduce((t, m) => t + (m.kilif_sayisi || 0), 0)
  const olur = onay.trim().toLocaleUpperCase('tr') === ONAY_SOZU && !busy

  const sil = async () => {
    if (!olur) return
    setBusy(true); setErr('')
    try {
      const d = await api.post('/api/molds/print/bulk-delete',
                               { ids: kaliplar.map((m) => m.id) })
      onDeleted?.(d)
    } catch (e) {
      setErr(e?.detail || e?.message || 'Silme başarısız')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
         onClick={onClose}>
      <div className="card max-w-md w-full p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-100 mb-2">
          {kaliplar.length} kalıbı sil
        </h2>

        <div className="text-sm text-gray-300 space-y-2 mb-4">
          <p>
            Seçilen <span className="font-semibold text-gray-100">{kaliplar.length}</span> kalıp
            (<span className="tabular-nums">{kilifToplam}</span> kılıf) kalıcı olarak silinecek.
          </p>

          {bekleyen.length > 0 && (
            <p className="text-amber-300/90 bg-amber-500/10 border border-amber-500/30 rounded px-3 py-2">
              <span className="font-semibold">{bekleyen.length} basılmamış kalıp</span> —
              içindeki ürünler plana geri döner ve tekrar <span className="font-semibold">"kalıp bekliyor"</span> olur.
            </p>
          )}

          {basilmis.length > 0 && (
            <p className="text-emerald-300/90 bg-emerald-500/10 border border-emerald-500/30 rounded px-3 py-2">
              <span className="font-semibold">{basilmis.length} basılmış kalıp</span> —
              içindeki ürünler <span className="font-semibold">üretilmiş</span> sayılır, plana geri DÖNMEZ.
              (Çift baskı koruması.)
            </p>
          )}
        </div>

        <div className="max-h-32 overflow-y-auto mb-3 rounded-lg border border-brand-border
                        divide-y divide-white/5">
          {kaliplar.map((m) => (
            <div key={m.id} className="px-3 py-1.5 text-xs flex items-center gap-2">
              <span className="font-mono text-gray-200">{m.kod}</span>
              <span className="text-gray-500">{m.variation}</span>
              <span className="text-gray-600 ml-auto">{m.kilif_sayisi} kılıf</span>
              {m.basildi && <span className="text-emerald-400/80">basılmış</span>}
            </div>
          ))}
        </div>

        <label className="block text-sm text-gray-300 mb-1">
          Onaylamak için <span className="font-mono text-gray-100">{ONAY_SOZU}</span> yazın:
        </label>
        <input autoFocus value={onay} onChange={(e) => setOnay(e.target.value)}
               placeholder={ONAY_SOZU} disabled={busy}
               className="input w-full mb-3 font-mono"
               onKeyDown={(e) => { if (e.key === 'Enter' && olur) sil() }} />

        {err && (
          <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30
                          rounded px-3 py-2 mb-3">{err}</div>
        )}

        <div className="flex items-center justify-end gap-2">
          <button onClick={onClose} disabled={busy} className="btn-secondary">Vazgeç</button>
          <button onClick={sil} disabled={!olur}
                  className={`px-3 py-1.5 rounded text-sm font-medium ${
                    olur ? 'bg-red-600 hover:bg-red-500 text-white'
                         : 'bg-red-900/40 text-red-300/60 cursor-not-allowed'}`}>
            {busy ? 'Siliniyor…' : `${kaliplar.length} kalıbı sil`}
          </button>
        </div>
      </div>
    </div>
  )
}
