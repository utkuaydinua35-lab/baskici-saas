import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

/**
 * BERNZ Special (PARLAK) stok listesi.
 *
 * Buradaki işaretler DOĞRUDAN müşteriye yansıyor: eksik stok nedeniyle
 * gönderilen "telefon modelini değiştir" bağlantısı, PARLAK ürünlerde yalnız
 * bu listeyi gösterir. Stokta olmayan model listede GÖRÜNÜR ama seçilemez —
 * müşteri "bu model var ama şu an yok" ile "hiç yok" farkını görsün.
 */
export default function OzelSeriStokPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [yeni, setYeni] = useState('')
  const [ekleniyor, setEkleniyor] = useState(false)

  const yukle = async () => {
    try {
      const d = await api.get('/api/ozel-seri/stok')
      setItems(d.items || [])
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Liste alınamadı')
    } finally { setLoading(false) }
  }
  useEffect(() => { yukle() }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  const degistir = async (r) => {
    // İyimser güncelleme: tık anında görünsün, sunucu hata verirse geri alınsın.
    const eski = items
    setItems(items.map(x => x.id === r.id ? { ...x, stokta: !x.stokta } : x))
    try {
      await api.patch(`/api/ozel-seri/stok/${r.id}`, { stokta: !r.stokta })
    } catch (e) {
      setItems(eski)
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Güncellenemedi')
    }
  }

  const ekle = async (e) => {
    e.preventDefault()
    const ad = yeni.trim()
    if (!ad) return
    setEkleniyor(true)
    try {
      await api.post('/api/ozel-seri/stok', { model: ad })
      setYeni('')
      await yukle()
      toast.success('Model eklendi')
    } catch (e2) {
      toast.error(typeof e2?.detail === 'string' ? e2.detail : 'Eklenemedi')
    } finally { setEkleniyor(false) }
  }

  const sil = async (r) => {
    if (!window.confirm(`"${r.model}" listeden çıkarılsın mı?`)) return
    try {
      await api.del(`/api/ozel-seri/stok/${r.id}`)
      setItems(items.filter(x => x.id !== r.id))
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Silinemedi')
    }
  }

  const stoktaSayisi = items.filter(x => x.stokta).length

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold text-gray-100">BERNZ Special — Stok</h1>
      <p className="text-sm text-gray-500 mt-1 mb-5">
        Eksik stok nedeniyle müşteriye gönderilen <b>model değiştirme bağlantısında</b>,
        BERNZ Special ürünler için yalnız bu liste gösterilir. Stokta olmayan model
        listede görünür ama seçilemez.
      </p>

      <form onSubmit={ekle} className="flex gap-2 mb-4">
        <input value={yeni} onChange={e => setYeni(e.target.value)}
          placeholder="Model ekle — örn. iPhone 16 Plus"
          className="input flex-1" />
        <button type="submit" disabled={ekleniyor || !yeni.trim()}
          className="btn-primary whitespace-nowrap">
          {ekleniyor ? 'Ekleniyor…' : 'Ekle'}
        </button>
      </form>

      {loading ? (
        <div className="text-sm text-gray-500">Yükleniyor…</div>
      ) : (
        <>
          <div className="text-xs text-gray-500 mb-2">
            {items.length} model · <span className="text-emerald-400">{stoktaSayisi} stokta</span>
            {items.length - stoktaSayisi > 0 &&
              <span className="text-amber-400"> · {items.length - stoktaSayisi} stok bekliyor</span>}
          </div>
          <div className="rounded-xl border border-brand-border overflow-hidden">
            {items.map((r, i) => (
              <div key={r.id}
                className={`flex items-center gap-3 px-4 py-2.5 ${i ? 'border-t border-brand-border' : ''}
                  ${r.stokta ? '' : 'bg-amber-500/5'}`}>
                <span className="flex-1 text-sm text-gray-200">{r.model}</span>

                <button onClick={() => degistir(r)}
                  className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border transition-colors ${
                    r.stokta
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/25'
                      : 'bg-amber-500/15 text-amber-300 border-amber-500/40 hover:bg-amber-500/25'}`}>
                  {r.stokta ? '✓ Stokta' : '⏳ Stokta yok'}
                </button>

                <button onClick={() => sil(r)} title="Listeden çıkar"
                  className="text-gray-600 hover:text-red-400 px-1">✕</button>
              </div>
            ))}
            {!items.length && (
              <div className="px-4 py-6 text-sm text-gray-500 text-center">
                Liste boş. Yukarıdan model ekleyin.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
