import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, getToken } from '../lib/api'
import { useToast } from '../components/Toast'
import { mutlak } from '../lib/taban'

const KALIP_TIPLERI = [
  { value: '', label: 'Belirtilmedi' },
  { value: 'siyah', label: 'Siyah' },
  { value: 'beyaz', label: 'Beyaz' },
  { value: 'parlak', label: 'Parlak' },
  { value: 'seffaf', label: 'Şeffaf' },
  { value: 'magsafe', label: 'MagSafe' },
]

const RENK_SECENEKLERI = [
  { name: 'Bordo', hex: '#800020' },
  { name: 'Fıstık Yeşil', hex: '#5C9F3F' },
  { name: 'Sarı', hex: '#F5E94E' },
  { name: 'Turuncu', hex: '#F58220' },
  { name: 'Siyah', hex: '#1A1A1A' },
  { name: 'Beyaz', hex: '#F5F5F5' },
  { name: 'Krem', hex: '#E8DBC0' },
  { name: 'Şeker Pembe', hex: '#E879BD' },
  { name: 'Toz Pembe', hex: '#F4BFD5' },
  { name: 'Haki', hex: '#4F7942' },
  { name: 'Mavi', hex: '#3DBDE0' },
  { name: 'Lacivert', hex: '#1F38C8' },
  { name: 'Lila', hex: '#B591D1' },
  { name: 'Kahverengi', hex: '#5C3317' },
  { name: 'Şeffaf', hex: 'transparent' },
  { name: 'Kırmızı', hex: '#E81515' },
  { name: 'Gri', hex: '#BCBCBC' },
]

const REASON_LABELS = {
  urun_tasarima_baglanmamis: 'Ürün tasarıma bağlanmamış',
  kisiye_ozel_tasarim_eksik: 'Kişiye özel tasarımı eksik',
  model_belirsiz: 'Telefon modeli belirsiz',
  model_taninmadi: 'Model tanınmadı',
}

export default function DesignsPage() {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [storesLoading, setStoresLoading] = useState(true)
  const [selectedStore, setSelectedStore] = useState('')

  const [designs, setDesigns] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [search, setSearch] = useState('')
  const [unmatched, setUnmatched] = useState([])
  const [unmatchedOpen, setUnmatchedOpen] = useState(false)
  const [eksikler, setEksikler] = useState([])
  const [assignProduct, setAssignProduct] = useState(null)  // {product_id, sample_title}
  const [filters, setFilters] = useState({
    no_product: false,
    no_kalip_tipi: false,
    no_birincil: false,
    no_ikincil: false,
    no_ucuncu: false,
    cmyk_done: null,
    baski_dosyasi_yok: false,
  })

  const [activeTab, setActiveTab] = useState('all')
  const [showUpload, setShowUpload] = useState(false)
  const [editingDesign, setEditingDesign] = useState(null)

  // ─── Stores ────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false
    api.get('/api/stores?include_bayii=true')
      .then(s => {
        if (cancelled) return
        const list = Array.isArray(s) ? s : []
        setStores(list)
        if (list.length > 0) setSelectedStore(list[0].id)
      })
      .catch(e => !cancelled && setError(e.detail || 'Mağazalar yüklenemedi'))
      .finally(() => !cancelled && setStoresLoading(false))
    return () => { cancelled = true }
  }, [])

  // ─── Designs + stats ───────────────────────────────────────
  const loadUnmatched = async (sid) => {
    if (!sid) { setUnmatched([]); return }
    try {
      const r = await api.get(`/api/designs/_meta/unmatched-products?store_id=${sid}`)
      setUnmatched(r.items || [])
    } catch { setUnmatched([]) }
  }

  const loadEksikler = async (sid) => {
    try {
      const url = sid ? `/api/molds/plan?store_id=${sid}` : '/api/molds/plan'
      const r = await api.get(url)
      setEksikler(r.eksikler || [])
    } catch { setEksikler([]) }
  }

  const loadDesigns = async () => {
    if (!selectedStore) return
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({
        store_id: selectedStore,
        page: String(page),
        per_page: '60',
      })
      if (search) params.set('search', search)
      if (filters.no_product) params.set('no_product', 'true')
      if (filters.no_kalip_tipi) params.set('no_kalip_tipi', 'true')
      if (filters.no_birincil) params.set('no_birincil', 'true')
      if (filters.no_ikincil) params.set('no_ikincil', 'true')
      if (filters.no_ucuncu) params.set('no_ucuncu', 'true')
      if (filters.cmyk_done !== null) params.set('cmyk_done', String(filters.cmyk_done))
      if (filters.baski_dosyasi_yok) params.set('baski_dosyasi_yok', 'true')
      if (activeTab === 'kisiye') params.set('is_kisiye_ozel', 'true')
      else if (activeTab === 'all') params.set('is_kisiye_ozel', 'false')

      const [list, st] = await Promise.all([
        api.get(`/api/designs?${params}`),
        api.get(`/api/designs/_stats?store_id=${selectedStore}`),
      ])
      setDesigns(list.items || [])
      setTotal(list.total || 0)
      setStats(st)
    } catch (e) {
      setError(e.detail || 'Yükleme başarısız')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (selectedStore) setPage(1)
  }, [selectedStore, activeTab, filters])

  useEffect(() => { loadDesigns() }, [selectedStore, page, activeTab, filters])
  useEffect(() => { loadUnmatched(selectedStore) }, [selectedStore])
  useEffect(() => { loadEksikler(selectedStore) }, [selectedStore])
  useEffect(() => {
    const h = () => loadUnmatched(selectedStore)
    window.addEventListener('notifications:refresh', h)
    return () => window.removeEventListener('notifications:refresh', h)
  }, [selectedStore])

  useEffect(() => {
    if (!selectedStore) return
    const t = setTimeout(() => { setPage(1); loadDesigns() }, 350)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  const toggleFilter = (key) => setFilters(f => ({ ...f, [key]: !f[key] }))

  const handleDeleteDesign = async (design) => {
    if (!confirm(`"${design.code}" tasarımını silmek istediğinden emin misin?`)) return
    try {
      await api.del(`/api/designs/${design.id}`)
      loadDesigns()
    } catch (e) {
      toast.error(e.detail || 'Silinemedi')
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">Tasarımlar</h1>
          <p className="text-sm text-gray-500 mt-1">Kalıp tasarım dosyaları</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowUpload(true)} className="btn-primary" disabled={!selectedStore}>
            + Tasarım Yükle
          </button>
        </div>
      </div>

      {storesLoading && (
        <div className="card text-center py-8 text-gray-500">⏳ Yükleniyor...</div>
      )}

      {!storesLoading && stores.length === 0 && (
        <div className="card text-center py-8">
          <div className="text-3xl mb-2">🏪</div>
          <p className="text-gray-400">
            Henüz mağaza yok. Önce <a href="/stores" className="text-accent hover:underline">Mağazalar</a> sayfasına git.
          </p>
        </div>
      )}

      {!storesLoading && stores.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <select
              value={selectedStore}
              onChange={e => setSelectedStore(e.target.value)}
              className="input !text-sm !py-1.5 w-full sm:w-auto sm:min-w-[200px]"
            >
              {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>

            <div className="flex gap-1 bg-brand-card border border-brand-border rounded-lg p-1">
              <TabBtn active={activeTab === 'all'} onClick={() => setActiveTab('all')}>
                🎨 Tüm Tasarımlar
              </TabBtn>
              <TabBtn active={activeTab === 'kisiye'} onClick={() => setActiveTab('kisiye')}>
                ✨ Kişiye Özel
              </TabBtn>
            </div>
          </div>

          <div className="card mb-3">
            <input
              type="text"
              placeholder="🔍 Tasarım kodu, isim veya ürün adı ara..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="input w-full !text-sm"
            />

            <div className="flex flex-wrap gap-2 mt-3">
              <FilterChip active={filters.no_product} onClick={() => toggleFilter('no_product')}
                color="amber" label="Ürünü Seçilmemiş" />
              <FilterChip active={filters.no_kalip_tipi} onClick={() => toggleFilter('no_kalip_tipi')}
                color="amber" label="Kalıp Tipi Belirsiz" />
              <FilterChip active={filters.no_birincil} onClick={() => toggleFilter('no_birincil')}
                color="red" label="● Birincil Rengi Seçilmemiş" />
              <FilterChip active={filters.no_ikincil} onClick={() => toggleFilter('no_ikincil')}
                color="blue" label="● İkincil Rengi Seçilmemiş" />
              <FilterChip active={filters.no_ucuncu} onClick={() => toggleFilter('no_ucuncu')}
                color="green" label="● Üçüncü Rengi Seçilmemiş" />
              <FilterChip
                active={filters.cmyk_done === true}
                onClick={() => setFilters(f => ({ ...f, cmyk_done: f.cmyk_done === true ? null : true }))}
                color="emerald" label="◔ CMYK Yapılmış" />
              <FilterChip
                active={filters.cmyk_done === false}
                onClick={() => setFilters(f => ({ ...f, cmyk_done: f.cmyk_done === false ? null : false }))}
                color="gray" label="◔ CMYK Yapılmamış" />
              <FilterChip active={filters.baski_dosyasi_yok} onClick={() => toggleFilter('baski_dosyasi_yok')}
                color="red" label="🖨️ Baskı Dosyası Yok" />
            </div>
          </div>

          {eksikler.length > 0 && (
            <div className="card mb-3 border-amber-500/30 bg-amber-500/5">
              <h2 className="text-sm font-medium text-amber-300 mb-2">
                ⚠ {eksikler.reduce((a, e) => a + (e.count || 0), 0)} kalem için tasarım eksik — kalıp oluşturmadan önce tamamlanmalı
              </h2>
              <div className="space-y-1 max-h-72 overflow-y-auto">
                {eksikler.slice(0, 50).map((e, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs bg-brand-input/40 rounded px-2 py-1.5">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 shrink-0">
                      {REASON_LABELS[e.reason] || e.reason}
                    </span>
                    <span className="text-gray-300 truncate flex-1">{e.title || '(başlıksız)'}</span>
                    {e.model && <span className="text-gray-500 shrink-0">{e.model}</span>}
                    <span className="text-gray-600 shrink-0">×{e.count}</span>
                    {e.product_id && e.reason !== 'kisiye_ozel_tasarim_eksik' && (
                      <button
                        onClick={() => setAssignProduct({ id: e.product_id, title: e.title || '' })}
                        className="btn-primary !text-[10px] !py-0.5 !px-2 shrink-0">
                        Tasarım Ekle
                      </button>
                    )}
                  </div>
                ))}
                {eksikler.length > 50 && <div className="text-[11px] text-gray-500 px-2">+{eksikler.length - 50} daha...</div>}
              </div>
              <p className="text-[11px] text-gray-500 mt-2">
                Tasarıma bağlanmamış ürünleri aşağıdan, kişiye özelleri <a href="/kisiye-ozel" className="text-accent hover:underline">Kişiye Özel</a> sayfasından tamamla.
              </p>
            </div>
          )}

          {unmatched.length > 0 && (
            <div className="card mb-3 border-amber-500/30 bg-amber-500/5">
              <button onClick={() => setUnmatchedOpen(o => !o)}
                className="w-full flex items-center justify-between text-left">
                <span className="text-sm text-amber-300 flex items-center gap-2">
                  ⚠ Eşleşmemiş Ürünler
                  <span className="text-[11px] bg-amber-500/20 px-2 py-0.5 rounded-full">{unmatched.length}</span>
                </span>
                <span className="text-amber-400 text-xs">{unmatchedOpen ? 'Gizle ▲' : 'Göster ▼'}</span>
              </button>
              <p className="text-[11px] text-gray-500 mt-1">
                Siparişlerde geçen ama henüz bir tasarıma bağlanmamış ürünler. Kalıp oluşturucu çalışması için bunlara tasarım+kalıp tipi atanmalı.
              </p>
              {unmatchedOpen && (
                <div className="mt-3 space-y-1.5 max-h-80 overflow-y-auto">
                  {unmatched.map(u => (
                    <div key={u.product_id}
                      className="flex items-center gap-2 bg-brand-input/50 border border-brand-border/60 rounded-lg px-3 py-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-200 truncate">{u.sample_title || '(başlıksız)'}</div>
                        <div className="text-[10px] text-gray-500 font-mono">
                          ID: {u.product_id} · {u.order_item_count} sipariş kalemi
                        </div>
                      </div>
                      <button
                        onClick={() => setAssignProduct({ id: u.product_id, title: u.sample_title || '' })}
                        className="btn-primary !text-[11px] !py-1 !px-2 shrink-0">
                        Tasarım Ata
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
              <StatCard label="Toplam Tasarım" value={stats.total} />
              <StatCard label="Standart" value={stats.standart} color="gray" />
              <StatCard label="Özel Tasarım" value={stats.ozel} color="pink" />
              <StatCard label="Shopify Ürünleri" value={stats.with_product} color="accent" />
              <StatCard label="Renk Atanmış"
                value={`${stats.renk_atanmis?.birincil || 0} · ${stats.renk_atanmis?.ikincil || 0} · ${stats.renk_atanmis?.ucuncu || 0}`}
                small hint="birincil · ikincil · üçüncü" />
            </div>
          )}

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
              {error}
            </div>
          )}

          <div className="card">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-sm font-medium text-gray-300">
                Tasarım Galerisi {total > 0 && <span className="text-gray-500">({total})</span>}
              </h2>
              <p className="text-xs text-gray-600">Tüm yüklenen tasarımlar</p>
            </div>

            {loading && <div className="text-gray-500 text-sm text-center py-12">Yükleniyor...</div>}

            {!loading && designs.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <div className="text-3xl mb-2">🎨</div>
                {search ? 'Arama sonucu yok.' : 'Hiç tasarım yok. + Tasarım Yükle ile başla.'}
              </div>
            )}

            {!loading && designs.length > 0 && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {designs.map(d => (
                    <DesignCard
                      key={d.id}
                      design={d}
                      onEdit={() => setEditingDesign(d)}
                      onDelete={() => handleDeleteDesign(d)}
                      onCmyk={() => toast.info('CMYK ayarı yakında')}
                    />
                  ))}
                </div>

                {total > 60 && (
                  <div className="flex justify-between items-center mt-4 text-xs text-gray-500">
                    <span>Sayfa {page} / {Math.ceil(total / 60)}</span>
                    <div className="flex gap-1">
                      <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                        className="btn-secondary !text-xs disabled:opacity-30">← Önceki</button>
                      <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 60)}
                        className="btn-secondary !text-xs disabled:opacity-30">Sonraki →</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}

      {(showUpload || assignProduct) && (
        <DesignUploadDialog
          storeId={selectedStore}
          initialProduct={assignProduct}
          onClose={() => { setShowUpload(false); setAssignProduct(null) }}
          onSaved={() => { setShowUpload(false); setAssignProduct(null); loadDesigns(); loadUnmatched(selectedStore); loadEksikler(selectedStore) }}
        />
      )}

      {editingDesign && (
        <DesignEditDialog
          design={editingDesign}
          onClose={() => setEditingDesign(null)}
          onSaved={() => { setEditingDesign(null); loadDesigns() }}
          onDelete={() => { setEditingDesign(null); loadDesigns() }}
        />
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// DesignCard — galeri thumbnail, hover overlay 3 buton
// ═══════════════════════════════════════════════════════════

function DesignCard({ design, onEdit, onDelete, onCmyk }) {
  const ext = (design.file_format || '').toLowerCase()
  const hasThumbnail = !!design.thumbnail_url

  return (
    <div className="bg-brand-input border border-brand-border rounded-lg overflow-hidden hover:border-accent/40 transition-colors group relative">
      {/* Thumbnail / placeholder */}
      <div
        className="aspect-square bg-gradient-to-br from-brand-card to-brand-input flex items-center justify-center cursor-pointer relative overflow-hidden"
        onClick={onEdit}
      >
        {hasThumbnail ? (
          <img
            src={design.thumbnail_url}
            alt={design.code}
            className="w-full h-full object-contain p-2"
            onError={e => { e.target.style.display = 'none' }}
          />
        ) : (
          <div className="flex flex-col items-center text-gray-600 gap-1">
            <div className="text-4xl">📄</div>
            <div className="text-[10px] uppercase font-mono">{ext || '?'}</div>
          </div>
        )}

        {design.is_kisiye_ozel && (
          <div className="absolute top-1 left-1 bg-pink-500/80 text-white text-[9px] px-1.5 py-0.5 rounded font-medium z-10">
            ÖZEL
          </div>
        )}

        {design.baski_dosyasi_yok && (
          <div className="absolute top-1 right-1 bg-red-500/85 text-white text-[9px] px-1.5 py-0.5 rounded font-medium z-10" title="Temiz baskı dosyası yok — kayıttaki görsel mockup">
            BASKI YOK
          </div>
        )}

        {/* Hover overlay (hidden→flex pattern) */}
        <div className="absolute inset-0 bg-black/55 hidden group-hover:flex items-center justify-center gap-2 z-20">
          <button
            onClick={e => { e.stopPropagation(); onEdit() }}
            className="w-9 h-9 bg-brand-input border border-brand-border rounded-lg flex items-center justify-center hover:bg-brand-card text-gray-200 shadow-lg"
            title="Düzenle"
          >
            <span className="text-sm">✏️</span>
          </button>
          <button
            onClick={e => { e.stopPropagation(); onCmyk && onCmyk() }}
            className="w-9 h-9 bg-cyan-500/20 border border-cyan-500/40 rounded-lg flex items-center justify-center hover:bg-cyan-500/30 text-cyan-300 shadow-lg"
            title="CMYK Ayarı (yakında)"
          >
            <span className="text-sm">💧</span>
          </button>
          <button
            onClick={e => { e.stopPropagation(); onDelete && onDelete() }}
            className="w-9 h-9 bg-red-500/20 border border-red-500/40 rounded-lg flex items-center justify-center hover:bg-red-500/30 text-red-300 shadow-lg"
            title="Sil"
          >
            <span className="text-sm">🗑️</span>
          </button>
        </div>
      </div>

      {/* Alt bilgi */}
      <div className="p-2">
        <div className="flex items-center justify-between gap-1">
          <div className="font-mono text-xs text-accent truncate flex-1">{design.code}</div>
          <span className="text-[9px] uppercase text-gray-500 bg-gray-700/30 px-1 rounded shrink-0">
            {ext}
          </span>
        </div>
        {design.name && (
          <div className="text-[10px] text-gray-400 truncate mt-0.5">{design.name}</div>
        )}
        <div className="flex gap-0.5 mt-1 flex-wrap items-center">
          {design.birincil_renk && <ColorDot color="red" title={design.birincil_renk} />}
          {design.ikincil_renk && <ColorDot color="blue" title={design.ikincil_renk} />}
          {design.ucuncu_renk && <ColorDot color="green" title={design.ucuncu_renk} />}
          {design.cmyk_hazirlanmis && <span className="text-[9px] text-emerald-400">◔</span>}
          {design.kalip_tipi && (
            <span className="text-[9px] text-gray-500 bg-gray-700/30 px-1 rounded">
              {design.kalip_tipi}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function ColorDot({ color, title }) {
  const map = {
    red: 'bg-red-500',
    blue: 'bg-blue-500',
    green: 'bg-emerald-500',
  }
  return <span className={`w-2 h-2 rounded-full inline-block ${map[color]}`} title={title}></span>
}


// ═══════════════════════════════════════════════════════════
// Yardımcı bileşenler
// ═══════════════════════════════════════════════════════════

function StatCard({ label, value, color = 'gray', hint, small = false }) {
  const colors = {
    gray: 'text-gray-200',
    accent: 'text-accent',
    pink: 'text-pink-400',
    emerald: 'text-emerald-400',
  }
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-3">
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`${small ? 'text-sm font-mono' : 'text-xl font-semibold'} ${colors[color]}`}>
        {value}
      </div>
      {hint && <div className="text-[9px] text-gray-600 mt-0.5">{hint}</div>}
    </div>
  )
}

function FilterChip({ active, onClick, color = 'gray', label }) {
  const colors = {
    amber:   active ? 'bg-amber-500/20 border-amber-500/50 text-amber-300' : 'border-brand-border text-gray-400 hover:text-gray-200',
    red:     active ? 'bg-red-500/20 border-red-500/50 text-red-300'       : 'border-brand-border text-gray-400 hover:text-gray-200',
    blue:    active ? 'bg-blue-500/20 border-blue-500/50 text-blue-300'    : 'border-brand-border text-gray-400 hover:text-gray-200',
    green:   active ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300' : 'border-brand-border text-gray-400 hover:text-gray-200',
    emerald: active ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300' : 'border-brand-border text-gray-400 hover:text-gray-200',
    gray:    active ? 'bg-gray-500/20 border-gray-500/50 text-gray-200'    : 'border-brand-border text-gray-400 hover:text-gray-200',
  }
  return (
    <button
      onClick={onClick}
      className={`text-[11px] px-3 py-1 rounded-full border transition-colors ${colors[color]}`}
    >
      {label}
    </button>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-xs transition-colors ${
        active ? 'bg-accent/15 text-accent font-medium' : 'text-gray-400 hover:text-gray-200 hover:bg-brand-input/60'
      }`}
    >{children}</button>
  )
}


// ═══════════════════════════════════════════════════════════
// ColorSelect — Portal-based, dialog scroll/clip dert etmez
// ═══════════════════════════════════════════════════════════

function ColorSwatch({ hex }) {
  if (hex === 'transparent') {
    return (
      <span
        className="w-3.5 h-3.5 rounded-full border border-red-500 shrink-0"
        style={{ background: 'transparent' }}
      />
    )
  }
  return (
    <span
      className="w-3.5 h-3.5 rounded-full border border-white/20 shrink-0"
      style={{ background: hex }}
    />
  )
}

function ColorSelect({ label, value, onChange, dot }) {
  const dots = { red: '🔴', blue: '🔵', green: '🟢' }
  const btnRef = useRef(null)
  const [openRect, setOpenRect] = useState(null)
  const selected = RENK_SECENEKLERI.find(c => c.name === value)

  const handleToggle = () => {
    if (openRect) {
      setOpenRect(null)
      return
    }
    if (btnRef.current) {
      const r = btnRef.current.getBoundingClientRect()
      const dropdownHeight = 256
      const spaceBelow = window.innerHeight - r.bottom
      const openUp = spaceBelow < dropdownHeight + 16 && r.top > dropdownHeight
      setOpenRect({
        top: openUp ? r.top - dropdownHeight - 4 : r.bottom + 4,
        left: r.left,
        width: r.width,
      })
    }
  }

  // Scroll/resize'da kapat (basit ve güvenli)
  useEffect(() => {
    if (!openRect) return
    const onScroll = () => setOpenRect(null)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
  }, [openRect])

  return (
    <div>
      <label className="text-xs text-gray-400 block mb-1">
        {dots[dot]} {label}
      </label>
      <button
        ref={btnRef}
        type="button"
        onClick={handleToggle}
        className="input w-full !text-xs text-left flex items-center gap-2"
      >
        {selected ? (
          <>
            <ColorSwatch hex={selected.hex} />
            <span>{selected.name}</span>
          </>
        ) : (
          <span className="text-gray-500">Belirtilmedi</span>
        )}
        <span className="ml-auto text-gray-500">⌄</span>
      </button>
      {openRect && createPortal(
        <>
          <div className="fixed inset-0 z-[200]" onClick={() => setOpenRect(null)} />
          <div
            className="fixed z-[201] bg-brand-card border border-brand-border rounded-lg shadow-2xl max-h-64 overflow-y-auto"
            style={{ top: openRect.top, left: openRect.left, width: openRect.width }}
          >
            <button
              type="button"
              onClick={() => { onChange(''); setOpenRect(null) }}
              className={`w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 hover:bg-brand-input ${value === '' ? 'bg-accent/10 text-accent' : 'text-gray-300'}`}
            >
              <span className="w-3.5 h-3.5 shrink-0" />
              <span>Belirtilmedi</span>
              {value === '' && <span className="ml-auto">✓</span>}
            </button>
            {RENK_SECENEKLERI.map(c => (
              <button
                key={c.name}
                type="button"
                onClick={() => { onChange(c.name); setOpenRect(null) }}
                className={`w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 hover:bg-brand-input ${value === c.name ? 'bg-accent/10 text-accent' : 'text-gray-300'}`}
              >
                <ColorSwatch hex={c.hex} />
                <span>{c.name}</span>
                {value === c.name && <span className="ml-auto">✓</span>}
              </button>
            ))}
          </div>
        </>,
        document.body
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// Upload Dialog
// ═══════════════════════════════════════════════════════════

function DesignUploadDialog({ storeId, onClose, onSaved, initialProduct = null }) {
  const fileInputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [filePreview, setFilePreview] = useState(null)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [productPickerOpen, setProductPickerOpen] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState(
    initialProduct ? { id: initialProduct.id, title: initialProduct.title, image_url: null } : null
  )
  const [kalipTipi, setKalipTipi] = useState('')
  const [birincil, setBirincil] = useState('')
  const [ikincil, setIkincil] = useState('')
  const [ucuncu, setUcuncu] = useState('')
  const [isKisiyeOzel, setIsKisiyeOzel] = useState(false)
  const [saving, setSaving] = useState(false)
  const [progress, setProgress] = useState(0)   // 0-100 yukleme ilerlemesi
  const [error, setError] = useState('')

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    if (['image/svg+xml', 'image/png', 'image/jpeg'].includes(f.type)) {
      const reader = new FileReader()
      reader.onload = e => setFilePreview(e.target.result)
      reader.readAsDataURL(f)
    } else if (f.type === 'application/pdf' || /\.pdf$/i.test(f.name)) {
      setFilePreview(URL.createObjectURL(f))   // PDF: blob URL (arka planda <embed>)
    } else {
      setFilePreview(null)
    }
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!file) { setError('Dosya seçmek zorunlu'); return }
    if (!code.trim()) { setError('Tasarım kodu zorunlu'); return }

    setError('')
    setSaving(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('store_id', storeId)
      fd.append('code', code.trim())
      if (name) fd.append('name', name.trim())
      if (selectedProduct) {
        fd.append('product_id', selectedProduct.id)
        fd.append('product_title', selectedProduct.title)
        if (selectedProduct.image_url) fd.append('product_image_url', selectedProduct.image_url)
      }
      if (kalipTipi) fd.append('kalip_tipi', kalipTipi)
      if (birincil) fd.append('birincil_renk', birincil)
      if (ikincil) fd.append('ikincil_renk', ikincil)
      if (ucuncu) fd.append('ucuncu_renk', ucuncu)
      fd.append('is_kisiye_ozel', String(isKisiyeOzel))

      // XHR — gercek yukleme ilerlemesi (fetch progress vermez)
      setProgress(0)
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', '/api/designs')
        xhr.setRequestHeader('Authorization', `Bearer ${getToken()}`)
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100))
        }
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) resolve()
          else {
            let detail = `HTTP ${xhr.status}`
            try { detail = JSON.parse(xhr.responseText).detail || detail } catch { /* yok */ }
            reject(new Error(detail))
          }
        }
        xhr.onerror = () => reject(new Error('Ağ hatası — yükleme başarısız'))
        xhr.send(fd)
      })
      onSaved()
    } catch (err) {
      setError(err.message || 'Kaydedilemedi')
    } finally {
      setSaving(false)
      setProgress(0)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex justify-between items-start p-5 pb-3 shrink-0 border-b border-brand-border">
          <div>
            <h2 className="text-xl font-semibold text-gray-100">Yeni Tasarım Yükle</h2>
            <p className="text-xs text-gray-500 mt-1">SVG, PNG, JPG veya PDF formatında tasarım yükleyin</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl leading-none">×</button>
        </div>

        <div className="overflow-y-auto px-5 py-4 flex-1">
          <form onSubmit={onSubmit} className="space-y-3" id="upload-form">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Dosya</label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-brand-border rounded-lg p-6 text-center cursor-pointer hover:border-accent/50 transition-colors"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".svg,.png,.jpg,.jpeg,.pdf"
                  onChange={e => handleFile(e.target.files?.[0])}
                  className="hidden"
                />
                {file ? (
                  <div className="relative min-h-[220px] flex flex-col items-center justify-center">
                    {filePreview && (
                      <div className="absolute inset-0 overflow-hidden rounded pointer-events-none" style={{ opacity: 0.24 }}>
                        {(file.type === 'application/pdf' || /\.pdf$/i.test(file.name)) ? (
                          <embed src={`${filePreview}#toolbar=0&navpanes=0&scrollbar=0&view=Fit`} type="application/pdf" className="w-full h-full" />
                        ) : (
                          <img src={filePreview} alt="" className="w-full h-full object-contain" />
                        )}
                      </div>
                    )}
                    <div className="relative space-y-2">
                      <div className="text-sm text-gray-300 break-all px-2">{file.name}</div>
                      <div className="text-[10px] text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="text-2xl mb-1">📤</div>
                    <div className="text-sm text-gray-300">Dosya seçmek için tıklayın</div>
                    <div className="text-[10px] text-gray-500 mt-1">SVG, PNG, JPG veya PDF · max 75 MB</div>
                  </>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Tasarım Kodu *</label>
                <input
                  type="text" required value={code}
                  onChange={e => setCode(e.target.value)}
                  className="input w-full font-mono" placeholder="Örn: 911"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">İsim (Opsiyonel)</label>
                <input
                  type="text" value={name}
                  onChange={e => setName(e.target.value)}
                  className="input w-full" placeholder="Örn: Çiçek Deseni"
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">Ürün Seçimi</label>
              {selectedProduct ? (
                <div className="bg-brand-input border border-brand-border rounded-lg p-2 flex items-center gap-2">
                  {selectedProduct.image_url && (
                    <img src={selectedProduct.image_url} alt="" className="w-10 h-10 rounded object-cover" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-gray-300 truncate">{selectedProduct.title}</div>
                    <div className="text-[10px] text-gray-500 font-mono">ID: {selectedProduct.id}</div>
                  </div>
                  <button type="button" onClick={() => setSelectedProduct(null)} className="text-xs text-red-400">×</button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setProductPickerOpen(true)}
                  className="input w-full text-left text-gray-400"
                >
                  Ürün seçin... <span className="float-right">⌄</span>
                </button>
              )}
              <p className="text-[10px] text-gray-600 mt-1">Tasarımı bir Shopify ürünü ile eşleştirin</p>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">Kalıp Tipi (Opsiyonel)</label>
              <select value={kalipTipi} onChange={e => setKalipTipi(e.target.value)} className="input w-full">
                {KALIP_TIPLERI.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <ColorSelect label="Birincil Renk" value={birincil} onChange={setBirincil} dot="red" />
              <ColorSelect label="İkincil Renk" value={ikincil} onChange={setIkincil} dot="blue" />
              <ColorSelect label="Üçüncü Renk" value={ucuncu} onChange={setUcuncu} dot="green" />
            </div>

            <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
              <input type="checkbox" checked={isKisiyeOzel} onChange={e => setIsKisiyeOzel(e.target.checked)} />
              Bu kişiye özel bir tasarım şablonu
            </label>

            {error && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}
          </form>
        </div>

        <div className="p-5 pt-3 border-t border-brand-border shrink-0">
          {saving && (
            <div className="mb-2">
              <div className="h-1.5 rounded-full bg-brand-input overflow-hidden">
                <div className="h-full bg-accent rounded-full transition-all duration-150" style={{ width: `${progress}%` }} />
              </div>
              <div className="text-[11px] text-gray-500 mt-1 text-right">
                {progress < 100 ? `Yükleniyor… %${progress}` : 'İşleniyor…'}
              </div>
            </div>
          )}
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="btn-secondary">İptal</button>
            <button type="submit" form="upload-form" disabled={saving || !file} className="btn-primary">
              {saving ? (progress < 100 ? `%${progress}` : 'İşleniyor…') : 'Yükle'}
            </button>
          </div>
        </div>
      </div>

      {productPickerOpen && (
        <ProductPicker
          storeId={storeId}
          onSelect={p => { setSelectedProduct(p); setProductPickerOpen(false) }}
          onClose={() => setProductPickerOpen(false)}
        />
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// Product Picker — tek useEffect, race-safe
// ═══════════════════════════════════════════════════════════

function ProductPicker({ storeId, onSelect, onClose }) {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const delay = search ? 400 : 0
    const t = setTimeout(async () => {
      if (cancelled) return
      setLoading(true)
      setError('')
      try {
        const params = new URLSearchParams({ store_id: storeId })
        if (search) params.set('search', search)
        const r = await api.get(`/api/designs/_meta/products?${params}`)
        if (cancelled) return
        setProducts(r.items || [])
      } catch (e) {
        if (cancelled) return
        setError(e.detail || 'Ürünler yüklenemedi')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, delay)
    return () => { cancelled = true; clearTimeout(t) }
    // eslint-disable-next-line
  }, [search])

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl p-4 w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-lg font-semibold text-gray-100">Ürün Seç</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>
        <input
          type="text" placeholder="Ürün ara..."
          value={search} onChange={e => setSearch(e.target.value)}
          className="input w-full !text-sm mb-3" autoFocus
        />
        {error && (
          <div className="text-xs text-red-400 bg-red-500/10 rounded p-2 mb-2">{error}</div>
        )}
        <div className="flex-1 overflow-y-auto space-y-1">
          {loading && <div className="text-center py-8 text-gray-500 text-sm">Yükleniyor...</div>}
          {!loading && products.length === 0 && (
            <div className="text-center py-8 text-gray-500 text-sm">Ürün bulunamadı</div>
          )}
          {products.map(p => (
            <button
              key={p.id}
              onClick={() => onSelect(p)}
              className="w-full flex items-center gap-2 p-2 bg-brand-input hover:bg-brand-input/70 border border-brand-border rounded-lg text-left transition-colors"
            >
              {p.image_url ? (
                <img src={p.image_url} alt="" className="w-10 h-10 rounded object-cover shrink-0" />
              ) : (
                <div className="w-10 h-10 rounded bg-brand-card flex items-center justify-center text-gray-600 shrink-0">📦</div>
              )}
              <div className="flex-1 min-w-0">
                <div className="text-xs text-gray-200 truncate">{p.title}</div>
                <div className="text-[10px] text-gray-500 font-mono">ID: {p.id}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// Edit Dialog — büyük görsel + tüm metadata + sil
// ═══════════════════════════════════════════════════════════

function DesignEditDialog({ design, onClose, onSaved, onDelete }) {
  const toast = useToast()
  const [uploadingPrint, setUploadingPrint] = useState(false)
  const [printDone, setPrintDone] = useState(false)   // baskı dosyası bu oturumda yüklendi
  const [yeniDosya, setYeniDosya] = useState(null)    // tasarım dosyasını değiştir (kaydedince gider)
  const [code, setCode] = useState(design.code || '')
  const [name, setName] = useState(design.name || '')
  const [kalipTipi, setKalipTipi] = useState(design.kalip_tipi || '')
  const [birincil, setBirincil] = useState(design.birincil_renk || '')
  const [ikincil, setIkincil] = useState(design.ikincil_renk || '')
  const [ucuncu, setUcuncu] = useState(design.ucuncu_renk || '')
  const [cmykDone, setCmykDone] = useState(design.cmyk_hazirlanmis || false)
  const [isKisiyeOzel, setIsKisiyeOzel] = useState(design.is_kisiye_ozel || false)
  const [notes, setNotes] = useState(design.notes || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const ext = (design.file_format || '').toLowerCase()
  const isPdf = ext === 'pdf'
  const isImage = ['svg', 'png', 'jpg', 'jpeg'].includes(ext)

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    // Baskı dosyası yeni yüklendiyse ya da tasarım eksik işaretliyse varyasyon ZORUNLU
    if ((printDone || design.baski_dosyasi_yok) && !kalipTipi) {
      setError('Varyasyon (Kalıp Tipi) seçilmeli — bu tasarım kalıba girebilmesi için varyasyon gerekiyor.')
      return
    }
    setSaving(true)
    try {
      const fd = new FormData()
      fd.append('code', code.trim())
      fd.append('name', name)
      fd.append('kalip_tipi', kalipTipi)
      fd.append('birincil_renk', birincil)
      fd.append('ikincil_renk', ikincil)
      fd.append('ucuncu_renk', ucuncu)
      fd.append('cmyk_hazirlanmis', String(cmykDone))
      fd.append('is_kisiye_ozel', String(isKisiyeOzel))
      fd.append('notes', notes)
      // Yeni dosya secildiyse tasarim dosyasini da degistir (or. yanlislikla
      // .jpg yuklenmis bir tasarimi .pdf ile duzeltmek).
      if (yeniDosya) fd.append('file', yeniDosya)

      const res = await fetch(mutlak(`/api/designs/${design.id}`), {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${getToken()}` },
        body: fd,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      onSaved()
    } catch (err) {
      setError(err.message || 'Kaydedilemedi')
    } finally {
      setSaving(false)
    }
  }

  // Dosya değişimi — kaydedilene kadar yalnızca seçili tutulur, yüklenmez.
  const dosyaSec = (f) => {
    if (!f) { setYeniDosya(null); return }
    const izin = ['svg', 'png', 'jpg', 'jpeg', 'pdf']
    const uz = (f.name || '').split('.').pop().toLowerCase()
    if (!izin.includes(uz)) { setError(`İzin verilen formatlar: ${izin.join(', ')}`); return }
    if (f.size > 75 * 1024 * 1024) { setError('Dosya çok büyük (max 75 MB)'); return }
    setError(''); setYeniDosya(f)
  }

  const uploadPrintFile = async (f) => {
    if (!f) return
    setUploadingPrint(true)
    try {
      const fd = new FormData(); fd.append('file', f)
      await api.postForm(`/api/designs/${design.id}/print-file`, fd)
      setPrintDone(true)   // modalı KAPATMA — varyasyon seçimi için açık kalsın
      toast.success('Baskı dosyası eklendi (CMYK). Şimdi varyasyonu seçip kaydet.')
    } catch (e) {
      toast.error(e.detail || 'Yüklenemedi')
    } finally {
      setUploadingPrint(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm(`"${design.code}" tasarımını silmek istediğinden emin misin?`)) return
    try {
      await api.del(`/api/designs/${design.id}`)
      onDelete()
    } catch (e) {
      toast.error(e.detail || 'Silinemedi')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex justify-between items-center p-5 pb-3 shrink-0 border-b border-brand-border">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Tasarımı Düzenle</h2>
            <p className="text-xs text-gray-500 mt-0.5">Kod: <span className="font-mono text-accent">{design.code}</span></p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>

        <div className="overflow-y-auto px-5 py-4 flex-1">
          {/* Tasarım dosyasını değiştir — yanlış formatta yüklenmiş bir tasarımı
              silip yeniden oluşturmadan düzeltmek için. */}
          <div className="mb-4 rounded-lg border border-brand-border bg-brand-input/40 p-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-200">📄 Tasarım dosyası</div>
                <div className="text-[11px] text-gray-500 mt-0.5">
                  Şu an: <span className="font-mono text-gray-400">.{design.file_format || '—'}</span>
                  {design.file_size_bytes ? ` · ${(design.file_size_bytes / 1024 / 1024).toFixed(1)} MB` : ''}
                </div>
              </div>
              <label className="btn-secondary !text-xs cursor-pointer inline-flex whitespace-nowrap">
                {yeniDosya ? 'Başka dosya seç' : '🔄 Dosyayı değiştir'}
                <input type="file" accept=".svg,.png,.jpg,.jpeg,.pdf" className="hidden"
                  onChange={e => { dosyaSec(e.target.files?.[0]); e.target.value = '' }} />
              </label>
            </div>
            {yeniDosya && (
              <div className="mt-2 flex items-center gap-2 text-[11px] text-accent">
                <span className="truncate">Yeni: {yeniDosya.name} · {(yeniDosya.size / 1024 / 1024).toFixed(1)} MB</span>
                <button type="button" onClick={() => setYeniDosya(null)}
                        className="text-gray-500 hover:text-gray-300 shrink-0">vazgeç</button>
                <span className="text-gray-500 shrink-0">— Kaydet'e basınca değişir</span>
              </div>
            )}
          </div>

          {/* Baskı dosyası yok — temiz baskı dosyası yükle (CMYK'ye çevrilir) */}
          {design.baski_dosyasi_yok && !printDone && (
            <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3">
              <div className="text-sm font-medium text-red-200 mb-1">🖨️ Baskı dosyası yok</div>
              <p className="text-[11px] text-gray-300 mb-2">
                Kayıttaki görsel kılıflı mockup — baskıya bu haliyle giremez ve kalıba alınmaz.
                <b> Temiz tasarımı</b> yükle; sistem CMYK PDF'e çevirir (beyaz koruma), mockup vitrin görseli olarak kalır.
              </p>
              <label className={`btn-primary !text-xs cursor-pointer inline-flex ${uploadingPrint ? 'opacity-50 pointer-events-none' : ''}`}>
                {uploadingPrint ? 'Yükleniyor…' : '⬆ Baskı dosyası yükle (PNG/JPG/PDF)'}
                <input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" className="hidden"
                  disabled={uploadingPrint} onChange={e => uploadPrintFile(e.target.files?.[0])} />
              </label>
            </div>
          )}
          {printDone && (
            <div className="mb-4 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3">
              <div className="text-sm font-medium text-emerald-200 mb-1">✓ Baskı dosyası yüklendi (CMYK)</div>
              <p className="text-[11px] text-gray-300">
                {kalipTipi
                  ? 'Kaydet ile tamamla.'
                  : '⚠ Şimdi aşağıdan Varyasyon (Kalıp Tipi) seçip Kaydet\'e bas — varyasyon olmadan kalıba giremez.'}
              </p>
            </div>
          )}

          {/* Tasarım önizlemesi */}
          {design.file_url && (
            <div className="bg-brand-input rounded-lg mb-4 overflow-hidden border border-brand-border">
              {isImage ? (
                <div className="flex items-center justify-center p-4" style={{ minHeight: '280px', maxHeight: '420px' }}>
                  <img src={design.file_url} alt={design.code}
                    className="max-w-full object-contain"
                    style={{ maxHeight: '380px' }} />
                </div>
              ) : isPdf ? (
                <iframe
                  src={design.file_url}
                  title={design.code}
                  className="w-full"
                  style={{ height: '420px', border: 'none', background: '#fff' }}
                />
              ) : (
                <div className="flex items-center justify-center py-16 text-gray-500">
                  <a href={design.file_url} target="_blank" rel="noreferrer"
                     className="text-accent hover:underline text-sm">
                    📄 {(ext || '?').toUpperCase()} dosyayı aç
                  </a>
                </div>
              )}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-3" id="edit-form">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Kod *</label>
                <input type="text" required value={code} onChange={e => setCode(e.target.value)} className="input w-full font-mono" />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">İsim</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} className="input w-full" />
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">
                Kalıp Tipi (Varyasyon){(printDone || design.baski_dosyasi_yok) && <span className="text-red-400"> *</span>}
              </label>
              <select value={kalipTipi} onChange={e => setKalipTipi(e.target.value)}
                className={`input w-full ${((printDone || design.baski_dosyasi_yok) && !kalipTipi) ? '!border-red-500/60' : ''}`}>
                {KALIP_TIPLERI.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <ColorSelect label="Birincil" value={birincil} onChange={setBirincil} dot="red" />
              <ColorSelect label="İkincil" value={ikincil} onChange={setIkincil} dot="blue" />
              <ColorSelect label="Üçüncü" value={ucuncu} onChange={setUcuncu} dot="green" />
            </div>

            <div className="flex gap-4 flex-wrap">
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input type="checkbox" checked={cmykDone} onChange={e => setCmykDone(e.target.checked)} />
                ◔ CMYK hazırlanmış
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input type="checkbox" checked={isKisiyeOzel} onChange={e => setIsKisiyeOzel(e.target.checked)} />
                ✨ Kişiye özel
              </label>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">Notlar</label>
              <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} className="input w-full !text-xs" />
            </div>

            {error && (
              <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">{error}</div>
            )}
          </form>
        </div>

        <div className="flex justify-between p-5 pt-3 border-t border-brand-border shrink-0">
          <button type="button" onClick={handleDelete} className="btn-secondary !text-red-400">
            🗑 Sil
          </button>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="btn-secondary">İptal</button>
            <button type="submit" form="edit-form" disabled={saving} className="btn-primary">
              {saving ? 'Kaydediliyor...' : 'Kaydet'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
