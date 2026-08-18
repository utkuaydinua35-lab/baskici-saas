// Kalıbın 9x3 slot doluluğu — kart üstünde tek bakışta.
//
// Kart daha önce yalnızca "27 kılıf" yazıyordu; kalıbın ne kadar dolduğu ancak
// içeriği açınca görülüyordu. Izgara aynı bilgiyi saymadan gösteriyor.
const SUTUN = 9
const SATIR = 3
export const SLOT_SAYISI = SUTUN * SATIR

export default function SlotHaritasi({ items = [], kilitli = false, onSlot }) {
  // slot_index 0..26. Aynı slotta birden fazla kayıt olursa ilki gösterilir.
  // typeof kontrolü şart: Number(null) === 0, yani slot_index'i null olan bir
  // kalem 1. slotu dolu gösterirdi.
  const dolu = new Map()
  for (const it of items) {
    const i = it?.slot_index
    if (typeof i !== 'number' || !Number.isInteger(i)) continue
    if (i >= 0 && i < SLOT_SAYISI && !dolu.has(i)) dolu.set(i, it)
  }
  const doluSayi = dolu.size

  return (
    <div className="my-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-gray-500">Slot doluluğu</span>
        <span className="text-[10px] text-gray-500 tabular-nums">
          {doluSayi}/{SLOT_SAYISI}
          {kilitli && <span className="ml-1 text-amber-400" title="Slot konumları kilitli">🔒</span>}
        </span>
      </div>
      <div className="grid gap-[3px]" style={{ gridTemplateColumns: `repeat(${SUTUN}, minmax(0, 1fr))` }}>
        {Array.from({ length: SLOT_SAYISI }, (_, i) => {
          const it = dolu.get(i)
          const ipucu = it
            ? `Slot ${i + 1} · ${it.model || '—'}${it.design_code ? ' · ' + it.design_code : ''}${it.order_number ? ' · #' + it.order_number : ''}`
            : `Slot ${i + 1} · boş`
          return (
            <div key={i} title={ipucu}
                 onClick={it && onSlot ? () => onSlot(it) : undefined}
                 className={`aspect-square rounded-[3px] transition-colors ${
                   it ? 'bg-accent/70 hover:bg-accent' : 'bg-brand-input border border-brand-border/60'
                 } ${it && onSlot ? 'cursor-pointer' : ''}`} />
          )
        })}
      </div>
    </div>
  )
}
