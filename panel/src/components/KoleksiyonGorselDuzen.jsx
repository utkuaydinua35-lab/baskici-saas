// Koleksiyon sayfası başlığı: düzen, görsel oranı ve kırpma.
// Görsel dosyası DEĞİŞMEZ — kırpma vitrinde CSS ile yapılır (odak noktası +
// yakınlaştırma). Önizleme vitrindeki storefront/components/KirpikGorsel.tsx
// ile AYNI CSS'i kullanır: burada gördüğünüz, sitede göreceğinizdir.
import { useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'

const ORANLAR = [
  ['dogal', 'Doğal'], ['1:1', 'Kare'], ['4:3', '4:3'], ['3:4', '3:4'], ['4:5', '4:5'],
  ['16:9', '16:9'], ['9:16', '9:16'], ['21:9', 'Geniş'],
]
const oranCss = (o) => (/^\d+:\d+$/.test(o || '') ? o.replace(':', ' / ') : undefined)

export default function KoleksiyonGorselDuzen({ storeId, collection, onClose, onSaved }) {
  const ilk = { oran: '4:3', x: 50, y: 50, zoom: 1, duzen: 'yan', taraf: 'sag', ...(collection.gorsel_kirp || {}) }
  const [k, setK] = useState(ilk)
  const [gorsel, setGorsel] = useState(collection.image_url || '')
  const [aciklama, setAciklama] = useState(collection.description || '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const kutu = useRef(null)
  const surukle = useRef(null)
  const yama = (p) => setK(o => ({ ...o, ...p }))

  const yukle = async (file) => {
    if (!file) return
    setBusy(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file); fd.append('kind', 'collection')
      const r = await api.postForm(`/api/store-settings/${storeId}/assets`, fd)
      setGorsel(r.url); yama({ x: 50, y: 50, zoom: 1 })
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Görsel yüklenemedi') }
    finally { setBusy(false) }
  }

  // Sürükle: görsel elin yönünde kayar → odak noktası ters yönde değişir
  const basla = (e) => {
    if (!oranCss(k.oran)) return
    e.preventDefault()
    const r = kutu.current.getBoundingClientRect()
    surukle.current = { px: e.clientX, py: e.clientY, x: k.x, y: k.y, w: r.width, h: r.height }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  const tasi = (e) => {
    const s = surukle.current
    if (!s) return
    const kat = 100 / Math.max(1, k.zoom)
    yama({
      x: Math.max(0, Math.min(100, s.x - ((e.clientX - s.px) / s.w) * kat * 1.6)),
      y: Math.max(0, Math.min(100, s.y - ((e.clientY - s.py) / s.h) * kat * 1.6)),
    })
  }
  const birak = () => { surukle.current = null }

  const kaydet = async () => {
    setBusy(true); setErr('')
    try {
      await api.patch(`/api/catalog/collections/${collection.id}`, {
        image_path: gorsel || '', description: aciklama.trim() || null,
        gorsel_kirp: { ...k, x: Math.round(k.x * 10) / 10, y: Math.round(k.y * 10) / 10 },
      })
      onSaved()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi') }
    finally { setBusy(false) }
  }

  const gorselKutusu = gorsel ? (
    oranCss(k.oran) ? (
      <div ref={kutu} onPointerDown={basla} onPointerMove={tasi} onPointerUp={birak} onPointerCancel={birak}
        onWheel={e => yama({ zoom: Math.max(1, Math.min(3, k.zoom - e.deltaY * 0.0015)) })}
        className="relative overflow-hidden rounded-xl cursor-grab active:cursor-grabbing touch-none select-none ring-1 ring-black/10"
        style={{ aspectRatio: oranCss(k.oran) }}>
        <img src={gorsel} alt="" draggable={false} className="absolute inset-0 h-full w-full object-cover pointer-events-none"
          style={{ objectPosition: `${k.x}% ${k.y}%`, transform: k.zoom > 1 ? `scale(${k.zoom})` : undefined,
            transformOrigin: `${k.x}% ${k.y}%` }} />
      </div>
    ) : <img src={gorsel} alt="" className="block w-full h-auto rounded-xl" />
  ) : (
    <label className="flex aspect-[4/3] items-center justify-center rounded-xl border-2 border-dashed border-zinc-300 text-sm text-zinc-500 cursor-pointer">
      📷 Görsel yükle
      <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={e => yukle(e.target.files?.[0])} />
    </label>
  )

  return createPortal(
    <div className="fixed inset-0 z-[80] bg-black/60 flex items-center justify-center p-3 sm:p-6" onClick={onClose}>
      <div className="card w-full max-w-4xl max-h-[92vh] overflow-y-auto !p-4 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold">“{collection.title}” sayfa görünümü</h2>
          <button onClick={onClose} className="ml-auto text-panel-muted hover:text-panel-ink text-xl leading-none">×</button>
        </div>

        {/* ÖNİZLEME — vitrindeki koleksiyon başlığıyla aynı düzen (açık zemin) */}
        <div className="rounded-2xl bg-[#f7f7f9] p-4 sm:p-6 text-zinc-900">
          {k.duzen === 'yan' ? (
            <div className={`grid items-center gap-5 sm:grid-cols-2 ${k.taraf === 'sol' ? 'sm:[&>*:first-child]:order-2' : ''}`}>
              <div className="text-center">
                <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">{collection.title}</div>
                {aciklama && <p className="mt-3 text-sm leading-relaxed text-zinc-700 whitespace-pre-line">{aciklama}</p>}
              </div>
              {gorselKutusu}
            </div>
          ) : (
            <div className="relative">
              {gorselKutusu}
              <div className="pointer-events-none absolute inset-x-0 bottom-0 rounded-b-xl bg-gradient-to-t from-black/60 to-transparent p-4 text-white">
                <div className="text-xl font-bold">{collection.title}</div>
                {aciklama && <p className="text-xs text-white/85 line-clamp-2">{aciklama}</p>}
              </div>
            </div>
          )}
          {gorsel && oranCss(k.oran) && (
            <p className="mt-2 text-center text-[11px] text-zinc-500">Görseli sürükleyerek kaydırın · tekerlek ya da aşağıdaki çubukla yakınlaştırın</p>
          )}
        </div>

        <div className="grid sm:grid-cols-2 gap-4 text-xs">
          <div className="space-y-3">
            <div>
              <div className="text-panel-muted mb-1">Düzen</div>
              <div className="flex gap-1.5 flex-wrap">
                {[['yan', 'Yazı + görsel yan yana'], ['kaplama', 'Görsel üstte, yazı üzerinde']].map(([v, ad]) => (
                  <button key={v} type="button" onClick={() => yama({ duzen: v })}
                    className={`px-2.5 py-1.5 rounded-lg border ${k.duzen === v ? 'border-panel-accent bg-emerald-500/10 text-emerald-300' : 'border-panel-border text-panel-muted'}`}>{ad}</button>
                ))}
              </div>
            </div>
            {k.duzen === 'yan' && (
              <div>
                <div className="text-panel-muted mb-1">Görsel hangi tarafta?</div>
                <div className="flex gap-1.5">
                  {[['sol', '← Solda'], ['sag', 'Sağda →']].map(([v, ad]) => (
                    <button key={v} type="button" onClick={() => yama({ taraf: v })}
                      className={`px-2.5 py-1.5 rounded-lg border ${k.taraf === v ? 'border-panel-accent bg-emerald-500/10 text-emerald-300' : 'border-panel-border text-panel-muted'}`}>{ad}</button>
                  ))}
                </div>
              </div>
            )}
            <div>
              <div className="text-panel-muted mb-1">Görsel oranı</div>
              <div className="flex gap-1.5 flex-wrap">
                {ORANLAR.map(([v, ad]) => (
                  <button key={v} type="button" onClick={() => yama({ oran: v })}
                    className={`px-2.5 py-1.5 rounded-lg border ${k.oran === v ? 'border-panel-accent bg-emerald-500/10 text-emerald-300' : 'border-panel-border text-panel-muted'}`}>{ad}</button>
                ))}
              </div>
            </div>
            {oranCss(k.oran) && gorsel && (
              <label className="block text-panel-muted">
                Yakınlaştırma: {k.zoom.toFixed(2)}×
                <input type="range" min={1} max={3} step={0.01} value={k.zoom}
                  onChange={e => yama({ zoom: Number(e.target.value) })} className="w-full mt-1" />
                <button type="button" onClick={() => yama({ x: 50, y: 50, zoom: 1 })} className="underline mt-1">Kırpmayı sıfırla</button>
              </label>
            )}
          </div>
          <div className="space-y-3">
            <label className="block text-panel-muted">
              Açıklama (başlığın altında)
              <textarea className="input mt-1" rows={5} maxLength={2000} value={aciklama}
                onChange={e => setAciklama(e.target.value)} placeholder="Koleksiyonu anlatan birkaç cümle…" />
            </label>
            <div className="flex gap-2 flex-wrap items-center">
              <label className="btn-ghost !py-1.5 text-xs cursor-pointer">
                {gorsel ? 'Görseli değiştir' : 'Görsel yükle'}
                <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={e => yukle(e.target.files?.[0])} />
              </label>
              {gorsel && <button type="button" onClick={() => setGorsel('')} className="text-red-300">Görseli kaldır</button>}
            </div>
          </div>
        </div>

        {err && <p className="text-sm text-red-300">{err}</p>}
        <div className="flex gap-2">
          <button onClick={onClose} className="btn-ghost !py-2 text-sm">Vazgeç</button>
          <button onClick={kaydet} disabled={busy} className="btn-primary !py-2 text-sm flex-1 disabled:opacity-40">
            {busy ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
