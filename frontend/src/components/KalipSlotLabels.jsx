// Kalıp slot kartındaki bilgi etiketleri (Sipariş No / Tasarım / Model / Kılıf / Slot).
// Boyut + renkler kalipLabel ayarlarından gelir. MoldDetailPage + MoldGeneratorPage ortak kullanır.
import { DEFAULT_LABEL, shortModel, kilifText } from '../lib/kalipLabel'

export default function KalipSlotLabels({ item, no, settings }) {
  const sc = settings?.scale || 1
  const c = { ...DEFAULT_LABEL.colors, ...(settings?.colors || {}) }
  const px = (base) => ({ fontSize: `${(base * sc).toFixed(1)}px`, lineHeight: 1.15 })
  const kilif = kilifText(item)
  const model = shortModel(item.model)
  return (
    <div className="relative z-10 h-full flex flex-col justify-end p-1 text-center gap-0.5 drop-shadow">
      {item.order_number != null && item.order_number !== '' && (
        <div className="font-semibold truncate" style={{ ...px(7), color: c.order }}>Sipariş NO: {item.order_number}</div>
      )}
      <div className="font-semibold truncate" style={{ ...px(9), color: c.code }}>{item.design_code || ''}</div>
      {model && <div className="truncate" style={{ ...px(8), color: c.model }}>{model}</div>}
      {kilif && <div className="truncate" style={{ ...px(7), color: c.kilif }}>{kilif}</div>}
      <div style={{ ...px(7), color: c.slot }}>#{no}</div>
    </div>
  )
}
