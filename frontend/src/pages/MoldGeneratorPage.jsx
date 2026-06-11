import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import MoldTabs from '../components/MoldTabs'
import DeleteMoldDialog from '../components/DeleteMoldDialog'
import SlotAssignDialog from '../components/SlotAssignDialog'

const VAR_COLORS = {
  'SİYAH': 'bg-gray-700 text-gray-100 border-gray-600',
  'BEYAZ': 'bg-gray-100 text-gray-800 border-gray-300',
  'ŞEFFAF': 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  'PARLAK': 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  'MAGSAFE': 'bg-purple-500/15 text-purple-300 border-purple-500/30',
}
const REASON_LABELS = {
  urun_tasarima_baglanmamis: 'Ürün tasarıma bağlanmamış',
  kisiye_ozel_tasarim_eksik: 'Kişiye özel tasarımı eksik',
  model_belirsiz: 'Telefon modeli belirsiz',
  model_taninmadi: 'Model tanınmadı',
}

export default function MoldGeneratorPage() {
  const navigate = useNavigate()
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [plan, setPlan] = useState(null)
  const [molds, setMolds] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [assignTarget, setAssignTarget] = useState(null)  // { mold, kalip_kodu }
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState(null)
  const [searchParams] = useSearchParams()
  const _urlTab = searchParams.get('tab') === 'existing' ? 'existing' : 'plan'
  const [tab, setTab] = useState(_urlTab)
  useEffect(() => { setTab(_urlTab) }, [_urlTab])
  const [skipMissing, setSkipMissing] = useState(false)

  useEffect(() => {
    api.get('/api/stores').then(s => {
      const list = Array.isArray(s) ? s : []
      setStores(list)
      // Varsayılan: 'Tüm Mağazalar' (storeId="") — multi-store birleşik plan
    }).catch(() => {})
  }, [])

  const loadPlan = async (sid = storeId) => {
    setLoading(true); setError(''); setMsg(null)
    try {
      const url = sid ? `/api/molds/plan?store_id=${sid}` : `/api/molds/plan`
      const r = await api.get(url)
      setPlan(r)
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Plan hesaplanamadı')
    } finally { setLoading(false) }
  }
  const loadExisting = async (sid = storeId) => {
    try {
      const url = sid ? `/api/molds?store_id=${sid}` : `/api/molds`
      const r = await api.get(url)
      setMolds(r.items || [])
    } catch { setMolds([]) }
  }
  useEffect(() => { loadPlan(storeId); loadExisting(storeId) }, [storeId])

  const [harfler, setHarfler] = useState('GHJ')
  const handleCreate = async () => {
    const canGo = plan?.can_create || (skipMissing && plan?.mold_count > 0)
    if (!canGo) return
    const cm = (skipMissing && plan.eksik_count > 0)
      ? `${plan.eksik_count} eksik kalem ATLANACAK. Sadece çözülen ${plan.mold_count} kalıp (${plan.total_units} kılıf) oluşturulacak. Onaylıyor musun?`
      : `${plan.mold_count} kalıp oluşturulacak (${plan.total_units} kılıf). Onaylıyor musun?`
    if (!confirm(cm)) return
    setCreating(true); setError(''); setMsg(null)
    try {
      const hq = `&harfler=${encodeURIComponent((harfler || 'GHJ').toUpperCase())}`
      const url = storeId
        ? `/api/molds/create?store_id=${storeId}&skip_missing=${skipMissing}${hq}`
        : `/api/molds/create?skip_missing=${skipMissing}${hq}`
      const r = await api.post(url, {})
      if (r.success) {
        setMsg({ ok: true, text: r.message })
        loadPlan(storeId); loadExisting(storeId)
        setTab('existing')
      } else {
        setMsg({ ok: false, text: r.message })
      }
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Oluşturma hatası')
    } finally { setCreating(false) }
  }

  // SlotAssignDialog için uygun mold objesi (id + kod + variation + kalip_kodlari)
  const assignMoldObj = assignTarget ? {
    id: assignTarget.mold.id,
    kod: assignTarget.mold.kod,
    variation: assignTarget.mold.variation,
    kalip_kodlari: assignTarget.mold.kalip_kodlari || [],
  } : null

  return (
    <div className="max-w-6xl">
      <MoldTabs />
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">{tab === 'existing' ? '📦 Oluşturulan Kalıplar' : '🎯 Kalıp Oluşturucu'}</h1>
          <p className="text-sm text-gray-500 mt-1">{tab === 'existing' ? 'Daha önce oluşturulan kalıplar' : 'Bekleyen siparişleri otomatik kalıplara böler'}</p>
        </div>
        <select value={storeId} onChange={e => setStoreId(e.target.value)} className="input !text-sm !py-1.5 min-w-[200px]">
          <option value="">Tüm Mağazalar</option>
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>

      {error && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">{error}</div>}
      {msg && <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${msg.ok ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' : 'bg-amber-500/10 border-amber-500/20 text-amber-300'}`}>{msg.ok ? '✓ ' : '⚠ '}{msg.text}</div>}

      {tab === 'plan' && (
        <>
          {loading && <div className="text-gray-500 text-sm text-center py-10">Plan hesaplanıyor...</div>}
          {!loading && plan && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <Kpi label="OLUŞACAK KALIP" value={plan.mold_count} color="accent" />
                <Kpi label="TOPLAM KILIF" value={plan.total_units} />
                <Kpi label="EKSİK KALEM" value={plan.eksik_count} color={plan.eksik_count ? 'red' : 'emerald'} />
                <div className="bg-brand-card border border-brand-border rounded-lg p-3 flex flex-col justify-center gap-2">
                  <label className="flex items-center gap-2 text-[11px] text-gray-400">
                    <span className="whitespace-nowrap">Kalıp harfleri:</span>
                    <input
                      type="text"
                      value={harfler}
                      onChange={e => setHarfler(e.target.value.replace(/[^a-zA-Z]/g, '').toUpperCase().slice(0, 3))}
                      maxLength={3}
                      placeholder="GHJ"
                      className="w-16 px-2 py-1 bg-brand-input border border-brand-border rounded text-center font-mono text-gray-100 uppercase"
                    />
                  </label>
                  <button onClick={handleCreate}
                    disabled={creating || !(plan.can_create || (skipMissing && plan.mold_count > 0)) || (harfler || '').length < 3}
                    className="btn-primary w-full disabled:opacity-40 disabled:cursor-not-allowed">
                    {creating ? 'Oluşturuluyor...' : '🎯 Kalıpları Oluştur'}
                  </button>
                  {plan.eksik_count > 0 && (
                    <label className="flex items-center gap-1.5 text-[11px] text-gray-400 cursor-pointer">
                      <input type="checkbox" checked={skipMissing} onChange={e => setSkipMissing(e.target.checked)} className="accent-accent" />
                      Eksikleri atla, çözülenleri oluştur
                    </label>
                  )}
                </div>
              </div>

              {plan.eksik_count > 0 && (
                <div className="card mb-4 border-amber-500/30 bg-amber-500/5">
                  <h2 className="text-sm font-medium text-amber-300 mb-2">
                    ⚠ {plan.eksik_count} kalem için tasarım eksik — kalıp oluşturmadan önce tamamlanmalı
                  </h2>
                  <div className="space-y-1 max-h-60 overflow-y-auto">
                    {plan.eksikler.slice(0, 50).map((e, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs bg-brand-input/40 rounded px-2 py-1.5">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 shrink-0">
                          {REASON_LABELS[e.reason] || e.reason}
                        </span>
                        <span className="text-gray-300 truncate flex-1">{e.title || '(başlıksız)'}</span>
                        {e.model && <span className="text-gray-500 shrink-0">{e.model}</span>}
                        <span className="text-gray-600 shrink-0">×{e.count}</span>
                      </div>
                    ))}
                    {plan.eksikler.length > 50 && <div className="text-[11px] text-gray-500 px-2">+{plan.eksikler.length - 50} daha...</div>}
                  </div>
                  <p className="text-[11px] text-gray-500 mt-2">
                    Tasarıma bağlanmamış ürünleri <a href="/designs" className="text-accent hover:underline">Tasarımlar</a> sayfasından,
                    kişiye özelleri <a href="/kisiye-ozel" className="text-accent hover:underline">Kişiye Özel</a> sayfasından tamamla.
                  </p>
                </div>
              )}

              {plan.molds.length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-sm font-medium text-gray-300">Kalıp Önizlemesi ({plan.mold_count})</h2>
                  {plan.molds.map(m => <MoldCard key={m.sira} mold={m} preview harfler={harfler} />)}
                </div>
              )}

              {plan.mold_count === 0 && plan.eksik_count === 0 && (
                <div className="card text-center py-12 text-gray-500">
                  <div className="text-3xl mb-2">✓</div>
                  Bekleyen kalıp yok — tüm siparişler kalıba eklenmiş.
                </div>
              )}
            </>
          )}
        </>
      )}

      {tab === 'existing' && (
        <div className="space-y-3">
          {molds.length === 0 ? (
            <div className="card text-center py-12 text-gray-500">
              <div className="text-3xl mb-2">🧩</div>
              Henüz kalıp oluşturulmamış.
            </div>
          ) : (
            <div className="card divide-y divide-brand-border/60 !p-0 overflow-hidden">
              {molds.map(m => (
                <MoldRow
                  key={m.id}
                  mold={m}
                  onClick={() => navigate(`/kalip/${m.id}`)}
                  onDelete={() => setDeleteTarget({ id: m.id, kod: m.kod })}
                />
              ))}
            </div>
          )}
        </div>
      )}

      <DeleteMoldDialog
        open={!!deleteTarget}
        mold={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={() => { setDeleteTarget(null); loadExisting(); loadPlan() }}
      />

      <SlotAssignDialog
        open={!!assignTarget}
        mold={assignMoldObj}
        kalipKodu={assignTarget?.kalip_kodu}
        onClose={() => setAssignTarget(null)}
        onAssigned={() => { setAssignTarget(null); loadExisting(); loadPlan() }}
      />
    </div>
  )
}

function MoldRow({ mold, onClick, onDelete }) {
  const vc = VAR_COLORS[mold.variation] || 'bg-gray-700 text-gray-200 border-gray-600'
  const statusColors = {
    olusturuldu: 'bg-blue-500/15 text-blue-300',
    basildi: 'bg-emerald-500/15 text-emerald-300',
    iptal: 'bg-red-500/15 text-red-300',
  }
  const sc = statusColors[mold.status] || 'bg-gray-600/30 text-gray-300'
  const tarih = mold.created_at ? new Date(mold.created_at).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric' }) : ''
  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 px-4 py-3 hover:bg-brand-input/40 cursor-pointer transition-colors">
      <span className="text-sm font-mono font-semibold text-gray-100 min-w-[90px]">{mold.kod}</span>
      <span className={`text-[10px] px-2 py-0.5 rounded-full border ${vc}`}>{mold.variation}</span>
      <span className="text-xs text-gray-400">{mold.kilif_sayisi}/27 kılıf · {mold.rows_used} satır</span>
      {mold.is_multi_store && <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300">🏪 Çoklu</span>}
      <span className={`text-[10px] px-2 py-0.5 rounded-full ${sc}`}>{mold.status}</span>
      <span className="text-xs text-gray-500 ml-auto">{tarih}</span>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete() }}
        className="text-xs text-red-400/70 hover:text-red-300 hover:bg-red-500/10 rounded px-2 py-1 border border-red-500/20"
        title="Kalıbı sil">🗑</button>
      <span className="text-gray-600 text-lg">›</span>
    </div>
  )
}

function MoldCard({ mold, preview, status, kod, onClick, onDelete, onAssignSlot, harfler }) {
  const vc = VAR_COLORS[mold.variation] || 'bg-gray-700 text-gray-200 border-gray-600'
  return (
    <div className={`card ${onClick ? 'cursor-pointer hover:border-accent/40 transition-colors' : ''}`} onClick={onClick}>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-100">
            {kod ? kod : (mold.kodlar && mold.kodlar.length ? kisaKodlar(mold.kodlar, harfler).join('-') : `Kalıp ${mold.sira}`)}
          </span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${vc}`}>{mold.variation}</span>
          {mold.is_multi_store && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border bg-blue-500/15 text-blue-300 border-blue-500/30" title="Birden çok mağazadan kalemler">
              🏪 Çoklu Mağaza
            </span>
          )}
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="ml-auto text-xs text-red-400/80 hover:text-red-300 hover:bg-red-500/10 rounded px-2 py-1 border border-red-500/20 hover:border-red-500/40 flex items-center gap-1"
              title="Kalıbı sil"
              aria-label="Kalıbı sil">
              🗑 Kalıbı Sil
            </button>
          )}
          {status && <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">{status}</span>}
          {preview && <span className="text-[10px] text-gray-500">önizleme</span>}
        </div>
        <div className="text-xs text-gray-500">
          {mold.count}/27 kılıf · {mold.rows_used} satır · kodlar: {kisaKodlar(mold.kodlar, harfler).join(', ')}
        </div>
      </div>
      <MoldGrid items={mold.items} onAssignSlot={onAssignSlot} harfler={harfler} />
    </div>
  )
}

const _KISA_SLOT = {
  'IPHONE-11-GROUP|SIYAH': [0,1], 'IPHONE-11-GROUP|BEYAZ': [0,2],
  'IPHONE-13-GROUP|SIYAH': [0,3], 'IPHONE-13-GROUP|BEYAZ': [0,4],
  'IPHONE-15-GROUP|SIYAH': [0,5], 'IPHONE-15-GROUP|BEYAZ': [0,6],
  'IPHONE-13-PROMAX-GROUP|SIYAH': [0,7], 'IPHONE-13-PROMAX-GROUP|BEYAZ': [0,8],
  'IPHONE-14-PLUS-GROUP|SIYAH': [0,7], 'IPHONE-14-PLUS-GROUP|BEYAZ': [0,8],
  'IPHONE-16-PLUS-GROUP|SIYAH': [0,7], 'IPHONE-16-PLUS-GROUP|BEYAZ': [0,8],
  'IPHONE-15-PRO-GROUP|SIYAH': [0,9], 'IPHONE-15-PRO-GROUP|BEYAZ': [1,1],
  'IPHONE-16-PRO-GROUP|SIYAH': [0,9], 'IPHONE-16-PRO-GROUP|BEYAZ': [1,1],
  'IPHONE-17-PRO-GROUP|SIYAH': [0,9], 'IPHONE-17-PRO-GROUP|BEYAZ': [1,1],
  'IPHONE-15-PROMAX-GROUP|SIYAH': [1,2], 'IPHONE-15-PROMAX-GROUP|BEYAZ': [1,3],
  'IPHONE-16-PROMAX-GROUP|SIYAH': [1,2], 'IPHONE-16-PROMAX-GROUP|BEYAZ': [1,3],
  'IPHONE-17-PROMAX-GROUP|SIYAH': [1,2], 'IPHONE-17-PROMAX-GROUP|BEYAZ': [1,3],
  'SEFFAF': [1,4], 'PARLAK': [1,5], 'MAGSAFE': [2,3],
  'REDMI-GROUP|SIYAH': [1,6], 'XIAOMI-GROUP|SIYAH': [1,7],
  'SAMSUNG-A-GROUP|SIYAH': [1,8], 'SAMSUNG-M-GROUP|SIYAH': [1,8],
  'SAMSUNG-S-GROUP|SIYAH': [1,9], 'SAMSUNG-ULTRA-GROUP|SIYAH': [2,1],
  'POCO-GROUP|SIYAH': [2,2], 'OPPO-GROUP|SIYAH': [2,2], 'VIVO-GROUP|SIYAH': [2,2],
  'REALME-GROUP|SIYAH': [2,2], 'TECNO-GROUP|SIYAH': [2,2], 'HUAWEI-GROUP|SIYAH': [2,2],
  'OMIX-GROUP|SIYAH': [2,2], 'SAMSUNG-OTHER-GROUP|SIYAH': [2,2],
}
function kisaKod(grupKodu, harfler) {
  if (!grupKodu) return '?'
  let h = (harfler || 'GHJ').toUpperCase()
  if (h.length < 3) h = (h + 'GHJ').slice(0, 3)
  h = h.slice(0, 3)
  let slot = _KISA_SLOT[grupKodu]
  if (!slot && grupKodu.indexOf('|BEYAZ') >= 0) slot = _KISA_SLOT[grupKodu.replace('|BEYAZ', '|SIYAH')]
  if (!slot) return grupKodu.split('|')[0].replace('-GROUP', '').slice(0, 4)
  return `${h[slot[0]]}${slot[1]}`
}
function kisaKodlar(grupKodlari, harfler) {
  const seen = []
  for (const gk of (grupKodlari || [])) {
    const kk = kisaKod(gk, harfler)
    if (seen.indexOf(kk) < 0) seen.push(kk)
  }
  return seen
}

function shortModel(m) {
  if (!m) return ''
  return m.replace(/i\s*phone/i, '').replace(/apple/i, '').replace(/galaxy/i, '').replace(/samsung/i, '').trim().toUpperCase()
}
function kilifLabel(it) {
  // Kalibin GERCEK rengi (android beyaz->siyah sonrasi)
  if (it.kilif_rengi) return `Kılıf: ${String(it.kilif_rengi).toUpperCase()}`
  if (it.variation) return `Kılıf: ${String(it.variation).toUpperCase()}`
  return ''
}

// Grup baski-sirasi onceligi (backend GROUP_PRIORITY ile ayni — dusuk=alt satir)
const _GROUP_PRIORITY = {
  'IPHONE-11-GROUP': 1, 'IPHONE-13-GROUP': 2, 'IPHONE-15-GROUP': 3,
  'IPHONE-13-PROMAX-GROUP': 4, 'IPHONE-14-PLUS-GROUP': 5, 'IPHONE-16-PLUS-GROUP': 6,
  'IPHONE-15-PRO-GROUP': 7, 'IPHONE-16-PRO-GROUP': 8, 'IPHONE-17-PRO-GROUP': 9,
  'IPHONE-15-PROMAX-GROUP': 10, 'IPHONE-16-PROMAX-GROUP': 11, 'IPHONE-17-PROMAX-GROUP': 12,
  'SAMSUNG-A-GROUP': 100, 'SAMSUNG-S-GROUP': 101, 'SAMSUNG-ULTRA-GROUP': 102,
  'SAMSUNG-M-GROUP': 103, 'SAMSUNG-OTHER-GROUP': 104,
  'REDMI-GROUP': 110, 'XIAOMI-GROUP': 111, 'POCO-GROUP': 112, 'OPPO-GROUP': 113,
  'VIVO-GROUP': 114, 'REALME-GROUP': 115, 'TECNO-GROUP': 116,
  'HUAWEI-GROUP': 117, 'OMIX-GROUP': 118, 'SEFFAF': 200, 'PARLAK': 201, 'MAGSAFE': 202,
  'IPHONE-UNKNOWN': 50, 'UNKNOWN-GROUP': 999,
}
function _kodPriority(kod) {
  if (!kod) return 999
  const grp = (kod.indexOf('|') >= 0) ? kod.split('|')[0] : kod
  return _GROUP_PRIORITY[grp] != null ? _GROUP_PRIORITY[grp] : 999
}

function MoldGrid({ items, onAssignSlot, harfler }) {
  // slot_index varsa onu kullan (kaydedilmis kalip); yoksa (plan onizleme) priority'ye gore diz.
  const hasSlots = items.some(it => typeof it.slot_index === 'number')
  const bySlot = {}
  if (hasSlots) {
    for (const it of items) {
      const sn = (typeof it.slot_index === 'number') ? it.slot_index + 1 : null
      if (sn) bySlot[sn] = it
    }
  } else {
    // onizleme: kodlari priority'ye gore sirala, dusuk->alt satir (row 0 = slot 1-9)
    const byKod = {}
    const kods = []
    for (const it of items) {
      if (!byKod[it.kod]) { byKod[it.kod] = []; kods.push(it.kod) }
      byKod[it.kod].push(it)
    }
    kods.sort((a, b) => _kodPriority(a) - _kodPriority(b))
    let rowCursor = 0
    for (const kod of kods) {
      const g = byKod[kod]
      const rowsNeeded = Math.ceil(g.length / 9)
      for (let r = 0; r < rowsNeeded; r++) {
        if (rowCursor >= 3) break
        const chunk = g.slice(r * 9, r * 9 + 9)
        // row 0 -> slot 1-9, row 1 -> 10-18, row 2 -> 19-27
        for (let i = 0; i < chunk.length; i++) {
          bySlot[rowCursor * 9 + i + 1] = chunk[i]
        }
        rowCursor++
      }
    }
  }
  const rowKodOf = (ri) => {
    for (let ci = 0; ci < 9; ci++) {
      const sn = 27 - (ri * 9 + ci)
      if (bySlot[sn]) return bySlot[sn].kod
    }
    return null
  }
  return (
    <div className="space-y-1.5">
      {[0, 1, 2].map((ri) => {
        const rowKod = rowKodOf(ri)
        return (
          <div key={ri} className="grid grid-cols-9 gap-1.5">
            {Array.from({ length: 9 }).map((_, ci) => {
              const slotNo = 27 - (ri * 9 + ci)
              const cell = bySlot[slotNo] || null
              const canAssign = !cell && rowKod && onAssignSlot
              return <Slot
                key={ci}
                item={cell}
                no={slotNo}
                harfler={harfler}
                onAssign={canAssign ? (e) => { e.stopPropagation(); onAssignSlot(rowKod) } : null}
                assignKod={canAssign ? rowKod : null}
              />
            })}
          </div>
        )
      })}
    </div>
  )
}

function Slot({ item, no, onAssign, assignKod, harfler }) {
  if (!item) {
    if (onAssign) {
      return (
        <button
          onClick={onAssign}
          title={`${assignKod} satırına slot ata`}
          className="aspect-[9/16] rounded-lg border border-dashed border-accent/40 hover:border-accent hover:bg-accent/10 flex flex-col items-center justify-center text-gray-500 hover:text-accent transition-colors group">
          <span className="text-2xl leading-none group-hover:scale-110 transition-transform">+</span>
          <span className="text-[9px] mt-0.5 font-mono opacity-60">{kisaKod(assignKod, harfler)}</span>
          <span className="text-[8px] mt-0.5">#{no}</span>
        </button>
      )
    }
    return (
      <div className="aspect-[9/16] rounded-lg border border-dashed border-brand-border/40 flex flex-col items-center justify-center text-gray-700">
        <span className="text-xs font-medium">{no}</span>
        <span className="text-[8px]">Boş</span>
      </div>
    )
  }
  return (
    <div className="aspect-[9/16] rounded-lg border border-accent/40 overflow-hidden relative bg-brand-input"
      title={`${item.kod} · ${item.design_code || ''} · ${item.model || ''} · #${item.order_number}`}>
      {item.thumbnail_url && (
        <img src={item.thumbnail_url} alt="" className="absolute inset-0 w-full h-full object-cover opacity-55"
          onError={e => { e.target.style.display = 'none' }} />
      )}
      <span className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/30" />
      <div className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 flex items-center justify-center text-white text-[7px]">✓</div>
      <div className="absolute top-1 left-1 text-[9px] font-mono text-accent bg-black/40 rounded px-1">{kisaKod(item.kod, harfler)}</div>
      <div className="relative z-10 h-full flex flex-col justify-end p-1 text-center gap-0.5">
        <div className="text-[9px] font-semibold text-white leading-none truncate drop-shadow">{item.design_code || ''}</div>
        <div className="text-[8px] text-gray-200 leading-none drop-shadow">{shortModel(item.model)}</div>
        <div className="text-[7px] text-amber-200 leading-none drop-shadow truncate">{kilifLabel(item)}</div>
        <div className="text-[7px] text-gray-400 leading-none">#{no}</div>
      </div>
    </div>
  )
}

function Kpi({ label, value, color = 'gray' }) {
  const colors = { gray: 'text-gray-100', accent: 'text-accent', red: 'text-red-400', emerald: 'text-emerald-400' }
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-3">
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold ${colors[color]}`}>{value}</div>
    </div>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick}
      className={`px-3 py-1.5 rounded-md text-sm transition-colors ${active ? 'bg-accent/15 text-accent' : 'text-gray-400 hover:text-gray-200'}`}>
      {children}
    </button>
  )
}
