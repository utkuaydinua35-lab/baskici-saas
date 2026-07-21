// Kalıp etiket ayarları — yazı boyutu + her bilginin rengi. Canlı önizlemeli modal.
import { useState } from 'react'
import { loadLabelSettings, saveLabelSettings, DEFAULT_LABEL } from '../lib/kalipLabel'
import KalipSlotLabels from './KalipSlotLabels'

const FIELDS = [
  { k: 'order', label: 'Sipariş No' },
  { k: 'code', label: 'Tasarım Kodu' },
  { k: 'model', label: 'Telefon Modeli' },
  { k: 'kilif', label: 'Kılıf Rengi' },
  { k: 'slot', label: 'Slot No' },
]

const SAMPLE = { order_number: '10495', design_code: 'B580', model: 'iPhone 16', kilif_rengi: 'siyah' }

export default function KalipAyarlari({ onClose, onChange }) {
  const [s, setS] = useState(loadLabelSettings())
  const apply = (n) => { setS(n); saveLabelSettings(n); onChange && onChange(n) }
  const setScale = (v) => apply({ ...s, scale: v })
  const setColor = (k, v) => apply({ ...s, colors: { ...s.colors, [k]: v } })
  const reset = () => apply({ scale: DEFAULT_LABEL.scale, colors: { ...DEFAULT_LABEL.colors } })

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-100">⚙️ Kalıp Etiket Ayarları</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>

        <div className="flex gap-4">
          {/* Ayarlar */}
          <div className="flex-1 space-y-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Yazı boyutu: <b className="text-gray-200">{Math.round((s.scale || 1) * 100)}%</b></label>
              <input type="range" min="0.7" max="2" step="0.05" value={s.scale || 1}
                onChange={e => setScale(Number(e.target.value))} className="w-full accent-accent" />
            </div>
            <div className="space-y-1.5">
              {FIELDS.map(f => (
                <div key={f.k} className="flex items-center justify-between gap-2">
                  <span className="text-xs text-gray-300">{f.label}</span>
                  <div className="flex items-center gap-2">
                    <input type="color" value={s.colors[f.k]} onChange={e => setColor(f.k, e.target.value)}
                      className="w-8 h-7 rounded cursor-pointer bg-transparent border border-brand-border" />
                    <span className="text-[10px] font-mono text-gray-500 w-16">{s.colors[f.k]}</span>
                  </div>
                </div>
              ))}
            </div>
            <button onClick={reset} className="text-xs text-gray-400 hover:text-accent">↺ Varsayılana dön</button>
          </div>

          {/* Canlı önizleme */}
          <div className="w-28 shrink-0">
            <div className="text-[10px] text-gray-500 mb-1 text-center">Önizleme</div>
            <div className="aspect-[9/16] rounded-lg border border-accent/40 overflow-hidden relative bg-gradient-to-br from-brand-input to-brand-card">
              <span className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/20" />
              <div className="absolute top-1 left-1 text-[9px] font-mono text-accent bg-black/40 rounded px-1">A1</div>
              <KalipSlotLabels item={SAMPLE} no={9} settings={s} />
            </div>
          </div>
        </div>

        <p className="text-[11px] text-gray-500 mt-3">Bu ayarlar bu tarayıcıda saklanır; kalıp önizleme ve kalıp detay ekranlarındaki tüm slotlara uygulanır.</p>
      </div>
    </div>
  )
}
