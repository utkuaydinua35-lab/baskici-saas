// Ürün görseli → varyant eşleştirme penceresi.
// Ürünün "varyant görseli" ayarı açıksa, müşteri vitrinde bu varyantlardan
// birini seçince görsel öne gelir. Bir görsel birden çok varyanta bağlanabilir
// (ör. tüm iPhone 15 serisi). Bağ model_key ile tutulur → model seti yeniden
// senkronlansa da kopmaz.
import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'

export default function VaryantGorselSecici({ gorsel, varyantlar, onKaydet, onKapat }) {
  // Aynı model_key birden çok varyasyonda olabilir — tekilleştir
  const secenekler = useMemo(() => {
    const m = new Map()
    for (const v of varyantlar || []) if (!m.has(v.model_key)) m.set(v.model_key, v.model_display || v.model_key)
    return [...m.entries()].map(([key, ad]) => ({ key, ad }))
  }, [varyantlar])
  const [secili, setSecili] = useState(() => new Set(gorsel.varyant_anahtarlari || []))
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const aranan = q.trim().toLocaleLowerCase('tr')
  const liste = secenekler.filter(s => !aranan || s.ad.toLocaleLowerCase('tr').includes(aranan))
  const degistir = (k) => setSecili(s => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n })
  const hepsi = (ac) => setSecili(s => {
    const n = new Set(s); liste.forEach(x => ac ? n.add(x.key) : n.delete(x.key)); return n
  })

  return createPortal(
    <div className="fixed inset-0 z-[80] bg-black/60 flex items-center justify-center p-4" onClick={onKapat}>
      <div className="card w-full max-w-md !p-4 space-y-3" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3">
          <img src={gorsel.url} alt="" className="w-14 h-14 rounded-lg object-cover border border-panel-border" />
          <div className="min-w-0">
            <div className="text-sm font-semibold">Bu görsel hangi varyantta gösterilsin?</div>
            <div className="text-[11px] text-panel-muted">
              Müşteri seçtiği an görsel öne gelir. Hiçbiri seçilmezse genel görseldir.
            </div>
          </div>
        </div>
        <input className="input" placeholder="Varyant ara…" value={q} onChange={e => setQ(e.target.value)} autoFocus />
        <div className="flex items-center gap-2 text-[11px]">
          <button type="button" onClick={() => hepsi(true)} className="underline">Listedekileri seç</button>
          <button type="button" onClick={() => hepsi(false)} className="underline">Listedekileri kaldır</button>
          <span className="ml-auto text-panel-muted">{secili.size} seçili</span>
        </div>
        <div className="max-h-72 overflow-y-auto overscroll-contain rounded-xl border border-panel-border divide-y divide-panel-border">
          {liste.map(s => (
            <label key={s.key} className="flex items-center gap-2 px-2.5 py-1.5 text-sm cursor-pointer hover:bg-panel-input">
              <input type="checkbox" checked={secili.has(s.key)} onChange={() => degistir(s.key)} />
              <span className="truncate">{s.ad}</span>
            </label>
          ))}
          {liste.length === 0 && <div className="px-2.5 py-3 text-xs text-panel-muted">Eşleşen varyant yok</div>}
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onKapat} className="btn-ghost !py-2 text-sm">Vazgeç</button>
          {(gorsel.varyant_anahtarlari || []).length > 0 && (
            <button type="button" disabled={busy}
              onClick={async () => { setBusy(true); await onKaydet([]); setBusy(false) }}
              className="btn-ghost !py-2 text-sm text-red-300">Bağı kaldır</button>
          )}
          <button type="button" disabled={busy}
            onClick={async () => { setBusy(true); await onKaydet([...secili]); setBusy(false) }}
            className="btn-primary !py-2 text-sm flex-1 disabled:opacity-40">
            {busy ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
