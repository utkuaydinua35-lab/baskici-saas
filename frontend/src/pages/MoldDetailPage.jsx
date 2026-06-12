import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import DeleteMoldDialog from '../components/DeleteMoldDialog'
import SlotAssignDialog from '../components/SlotAssignDialog'

const STAGE_ICONS = { edit: '✏️', check: '✓', send: '📤', printer: '🖨', 'check-circle': '✅', circle: '○' }
const VAR_COLORS = {
  'SİYAH': 'bg-gray-700 text-gray-100 border-gray-600',
  'BEYAZ': 'bg-gray-100 text-gray-800 border-gray-300',
  'ŞEFFAF': 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  'PARLAK': 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  'MAGSAFE': 'bg-purple-500/15 text-purple-300 border-purple-500/30',
}

export default function MoldDetailPage() {
  const { moldId } = useParams()
  const navigate = useNavigate()
  const [showDelete, setShowDelete] = useState(false)
  const [assignTarget, setAssignTarget] = useState(null)  // { kalip_kodu }
  const [mold, setMold] = useState(null)
  const [stages, setStages] = useState([])
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [printView, setPrintView] = useState(false)

  const load = async () => {
    try {
      const [d, st, h] = await Promise.all([
        api.get(`/api/molds/${moldId}/detail`),
        api.get('/api/molds/_meta/stages'),
        api.get(`/api/molds/${moldId}/history`),
      ])
      setMold(d); setStages(st.stages || []); setHistory(h.items || [])
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Kalıp yüklenemedi')
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [moldId])

  const patchStage = async (body) => {
    try {
      const d = await api.patch(`/api/molds/${moldId}/stage`, body)
      setMold(d)
      const h = await api.get(`/api/molds/${moldId}/history`)
      setHistory(h.items || [])
    } catch (e) { alert(typeof e?.detail === 'string' ? e.detail : 'Güncellenemedi') }
  }

  const [removeTarget, setRemoveTarget] = useState(null)
  const removeItem = async (itemId, action) => {
    try {
      const d = await api.post(`/api/molds/${moldId}/items/${itemId}/remove`, { action })
      setMold(d)
      const h = await api.get(`/api/molds/${moldId}/history`)
      setHistory(h.items || [])
      setRemoveTarget(null)
    } catch (e) { alert(typeof e?.detail === 'string' ? e.detail : 'Çıkarılamadı') }
  }

  const [pdfBusy, setPdfBusy] = useState(false)
  const downloadPdf = async () => {
    setPdfBusy(true)
    try {
      const res = await fetch(`/api/molds/${moldId}/pdf`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('baskici_token')}` },
      })
      if (!res.ok) throw new Error('PDF üretilemedi')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `kalip_${mold?.kod || moldId}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('PDF indirilemedi: ' + (e.message || ''))
    } finally { setPdfBusy(false) }
  }

  const toggleSlot = async (itemId, val) => {
    try {
      await api.patch(`/api/molds/${moldId}/items/${itemId}`, { is_hazir: val })
      setMold(m => ({ ...m, items: m.items.map(it => it.id === itemId ? { ...it, is_hazir: val } : it),
        hazir_count: m.items.filter(it => it.id === itemId ? val : it.is_hazir).length }))
    } catch (e) { alert('Slot güncellenemedi') }
  }

  if (loading) return <div className="text-gray-500 text-sm text-center py-16">Yükleniyor...</div>
  if (error) return (
    <div className="max-w-2xl">
      <button onClick={() => navigate('/kalip-olustur')} className="text-accent text-sm hover:underline mb-3">← Kalıplar</button>
      <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
    </div>
  )
  if (!mold) return null

  const vc = VAR_COLORS[mold.variation] || 'bg-gray-700 text-gray-200 border-gray-600'

  return (
    <div className="max-w-[1400px]">
      {/* Üst bar */}
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-start gap-3">
          <button onClick={() => navigate('/kalip-olustur')} className="text-gray-400 hover:text-gray-200 text-xl mt-0.5">←</button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-semibold text-gray-100 font-mono">{mold.kod}</h1>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border ${vc}`}>{mold.variation}</span>
              {mold.is_hatali && <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-300 border border-red-500/30">⚠ HATALI BASKI</span>}
            </div>
            <p className="text-xs text-gray-500 mt-1">{mold.kilif_sayisi}/27 slot dolu · {mold.rows_used} satır · {mold.hazir_count} hazır</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => setPrintView(v => !v)} className="btn-secondary !text-sm">
            {printView ? '↙ Normal Görünüm' : '↗ Baskı Görünümü'}
          </button>
          <StageDropdown stages={stages} current={mold.current_stage} onSelect={patchStage} />
          <button onClick={() => patchStage({ is_hatali: !mold.is_hatali })}
            className={`!text-sm px-3 py-1.5 rounded-lg border ${mold.is_hatali ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-red-500/10 text-red-300 border-red-500/30 hover:bg-red-500/20'}`}>
            ⚠ {mold.is_hatali ? 'Hatayı Geri Al' : 'Hatalı Baskı'}
          </button>
          <button
            onClick={() => setShowDelete(true)}
            className="!text-sm px-3 py-1.5 rounded-lg border bg-red-500/10 text-red-300 border-red-500/30 hover:bg-red-500/20"
            title="Kalıbı sil">
            🗑 Kalıbı Sil
          </button>
        </div>
      </div>

      <DeleteMoldDialog
        open={showDelete}
        mold={mold}
        onClose={() => setShowDelete(false)}
        onDeleted={() => { setShowDelete(false); navigate('/kalip-olustur') }}
      />

      <SlotAssignDialog
        open={!!assignTarget}
        mold={mold}
        kalipKodu={assignTarget?.kalip_kodu}
        onClose={() => setAssignTarget(null)}
        onAssigned={() => { setAssignTarget(null); load() }}
      />

      {/* Stage timeline */}
      <div className="card mb-5">
        <StageTimeline stages={stages} current={mold.current_stage} progress={mold.progress_percent} />
      </div>

      {printView ? (
        <div className="card">
          <h2 className="text-sm font-medium text-gray-300 mb-1">Baskı Görünümü</h2>
          <p className="text-xs text-gray-500 mb-3">9×3 grid · {mold.kilif_sayisi} slot dolu · boş slot ➜ + ile ata</p>
          <SlotGrid items={mold.items} onToggle={toggleSlot} onRemove={setRemoveTarget}
            onAssign={(kod) => setAssignTarget({ kalip_kodu: kod })} big />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="space-y-4">
            <div className="card">
              <h2 className="text-sm font-medium text-gray-200 mb-2">Kalıp Bilgileri</h2>
              <InfoRow label="Kod" value={mold.kod} mono />
              <InfoRow label="Varyasyon" value={mold.variation} />
              <InfoRow label="Kalıp kodları" value={(mold.kalip_kodlari || []).join(', ')} mono />
              <InfoRow label="Dolu slot" value={`${mold.kilif_sayisi} / 27`} />
              <InfoRow label="Hazır slot" value={`${mold.hazir_count} / ${mold.kilif_sayisi}`} />
              <InfoRow label="Oluşturulma" value={fmtDate(mold.created_at)} />
              {mold.updated_at && <InfoRow label="Son güncelleme" value={fmtDate(mold.updated_at)} />}
            </div>
            <div className="card">
              <h2 className="text-sm font-medium text-gray-200 mb-3">İşlemler</h2>
              <div className="space-y-2">
                <button onClick={downloadPdf} disabled={pdfBusy}
                  className="btn-primary w-full !text-sm disabled:opacity-50">
                  {pdfBusy ? '⏳ Hazırlanıyor...' : '⬇ PDF İndir'}
                </button>
                <button onClick={() => patchStage({ is_hatali: !mold.is_hatali })}
                  className="w-full !text-sm px-3 py-2 rounded-lg bg-red-500/10 text-red-300 border border-red-500/30 hover:bg-red-500/20">
                  ⚠ {mold.is_hatali ? 'Hatayı Geri Al' : 'Hatalı Baskı'}
                </button>
              </div>
            </div>
            <div className="card">
              <h2 className="text-sm font-medium text-gray-200 mb-3">Durum Geçmişi</h2>
              {history.length === 0 ? (
                <p className="text-xs text-gray-500 italic">Henüz değişiklik yok.</p>
              ) : (
                <div className="space-y-2">
                  {history.map(h => (
                    <div key={h.id} className="text-xs border-l-2 border-brand-border pl-2">
                      <div className="text-gray-300">{actionLabel(h)}</div>
                      <div className="text-[10px] text-gray-500">{h.created_by} · {fmtDate(h.created_at)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="lg:col-span-2 card">
            <h2 className="text-sm font-medium text-gray-200 mb-1">Slot Yerleşimi</h2>
            {(!mold.kalip_kodlari || mold.kalip_kodlari.length === 0) ? (
              <div className="text-center py-10">
                <div className="text-4xl mb-3">📭</div>
                <p className="text-sm text-gray-400 mb-1">Bu kalıp boş</p>
                <p className="text-xs text-gray-500 mb-4">İlk eklediğin kılıf ve tasarım kalıbın varyasyonunu ve düzenini belirleyecek.</p>
                <button onClick={() => setAssignTarget({ kalip_kodu: null })} className="btn-primary !text-sm">➕ İlk Kılıfı Ekle</button>
              </div>
            ) : (
              <>
                <p className="text-xs text-gray-500 mb-3">9×3 grid · {mold.kilif_sayisi} slot dolu · slota tıkla → hazır işaretle · boş + → ata</p>
                <SlotGrid items={mold.items} onToggle={toggleSlot} onRemove={setRemoveTarget}
                  onAssign={(kod) => setAssignTarget({ kalip_kodu: kod })} />
              </>
            )}
          </div>
        </div>
      )}

      {removeTarget && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
             onMouseDown={(e) => e.target === e.currentTarget && setRemoveTarget(null)}>
          <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-sm p-5">
            <h2 className="text-lg font-semibold text-gray-100 mb-1">Slotu Kalıptan Çıkar</h2>
            <p className="text-xs text-gray-500 mb-4">
              {removeTarget.kalip_kodu} · {removeTarget.design_code || ''} · {removeTarget.model || ''}
            </p>
            <div className="space-y-2">
              <button onClick={() => removeItem(removeTarget.id, 'replan')}
                className="w-full text-left px-3 py-2.5 rounded-lg bg-accent/10 border border-accent/30 text-accent hover:bg-accent/20">
                ↩ Geri planla <span className="block text-[11px] text-gray-400 mt-0.5">Kalemi tekrar kalıba eklenmemiş yap, sonraki planda çıksın</span>
              </button>
              <button onClick={() => removeItem(removeTarget.id, 'cancel')}
                className="w-full text-left px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 hover:bg-red-500/20">
                ✕ İptal et <span className="block text-[11px] text-gray-400 mt-0.5">Kalemi plandan tamamen çıkar, geri dönmesin</span>
              </button>
              <button onClick={() => setRemoveTarget(null)}
                className="w-full px-3 py-2 rounded-lg border border-brand-border text-gray-400 hover:text-gray-200">
                Vazgeç
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StageTimeline({ stages, current, progress }) {
  const cur = stages.find(s => s.no === current)
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-accent/15 flex items-center justify-center text-xl">
            {cur ? STAGE_ICONS[cur.icon] || '○' : '○'}
          </div>
          <div>
            <div className="text-[10px] uppercase text-gray-500">Şu Anki Aşama</div>
            <div className="text-base font-semibold text-gray-100">{cur?.label || '?'} <span className="text-gray-500 text-sm">({current}/{stages.length})</span></div>
          </div>
        </div>
        <div className="text-sm font-semibold text-accent bg-accent/10 px-2 py-0.5 rounded">%{progress}</div>
      </div>
      <div className="flex items-stretch pt-5 px-2">
        {stages.map((s, i) => {
          const done = s.no < current, active = s.no === current
          return (
            <div key={s.no} className="flex items-start flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1.5 shrink-0">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center text-base border-2 relative ${
                  active ? 'bg-accent border-accent text-white stage-active-beat stage-glow' : done ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300 stage-fade-in' : 'bg-brand-input border-brand-border text-gray-600'}`}>
                  {active && <span className="stage-ring" />}
                  {active && <span className="stage-ring-2" />}
                  {STAGE_ICONS[s.icon] || '○'}
                  <span className={`absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full text-[8px] flex items-center justify-center z-10 ${
                    active ? 'bg-white text-accent' : done ? 'bg-emerald-500 text-white' : 'bg-brand-border text-gray-500'}`}>{s.no}</span>
                </div>
                <div className={`text-[10px] text-center leading-tight whitespace-nowrap ${active ? 'text-accent font-medium' : done ? 'text-emerald-300' : 'text-gray-600'}`}>{s.label}</div>
              </div>
              {i < stages.length - 1 && <div className={`h-0.5 flex-1 mt-6 ${done ? 'bg-emerald-500/50' : 'bg-brand-border'}`} />}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StageDropdown({ stages, current, onSelect }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)} className="btn-secondary !text-sm flex items-center gap-1.5">
        Durum Değiştir <span className="text-xs">⌄</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-1 w-56 bg-brand-card border border-brand-border rounded-lg shadow-2xl z-50 py-1">
            {stages.map(s => (
              <button key={s.no} onClick={() => { onSelect({ stage: s.no }); setOpen(false) }}
                className={`w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-brand-input ${s.no === current ? 'text-accent font-medium' : 'text-gray-300'}`}>
                <span className="w-5 text-center text-gray-500 text-xs">{s.no}</span>{s.label}
                {s.no === current && <span className="ml-auto">✓</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function SlotGrid({ items, onToggle, onRemove, onAssign, big }) {
  // Backend'in atadigi slot_index'e gore yerlestir (1=alt-sag, 27=ust-sol).
  // slot_index 0-tabanli (0..26) -> slot_no = slot_index + 1.
  const bySlot = {}
  for (const it of items) {
    const sn = (typeof it.slot_index === 'number') ? it.slot_index + 1 : null
    if (sn) bySlot[sn] = it
  }
  // her satirin hangi koda ait oldugunu (bos slota atama icin) cikar
  const rowKodOf = (ri) => {
    for (let ci = 0; ci < 9; ci++) {
      const sn = 27 - (ri * 9 + ci)
      if (bySlot[sn]) return bySlot[sn].kalip_kodu
    }
    return null
  }

  return (
    <div className="overflow-x-auto -mx-1 px-1">
    <div className="space-y-1.5 min-w-[520px]">
      {[0, 1, 2].map((ri) => {
        const rowKod = rowKodOf(ri)
        return (
          <div key={ri} className="grid grid-cols-9 gap-1.5">
            {Array.from({ length: 9 }).map((_, ci) => {
              const slotNo = 27 - (ri * 9 + ci)
              const cell = bySlot[slotNo] || null
              const canAssign = !cell && rowKod && onAssign
              return <Slot
                key={ci}
                item={cell}
                no={slotNo}
                onToggle={onToggle}
                onRemove={onRemove}
                onAssign={canAssign ? () => onAssign(rowKod) : null}
                assignKod={canAssign ? rowKod : null}
                big={big}
              />
            })}
          </div>
        )
      })}
    </div>
    </div>
  )
}

function Slot({ item, no, onToggle, onRemove, onAssign, assignKod, big }) {
  if (!item) {
    if (onAssign) {
      return (
        <button
          onClick={onAssign}
          title={`${assignKod} satırına slot ata`}
          className={`${big ? 'aspect-[9/15]' : 'aspect-[9/16]'} rounded-lg border border-dashed border-accent/40 hover:border-accent hover:bg-accent/10 flex flex-col items-center justify-center text-gray-500 hover:text-accent transition-colors group`}>
          <span className="text-2xl leading-none group-hover:scale-110 transition-transform">+</span>
          <span className="text-[9px] mt-0.5 font-mono opacity-60">{assignKod}</span>
          <span className="text-[8px] mt-0.5">#{no}</span>
        </button>
      )
    }
    return (
      <div className={`${big ? 'aspect-[9/15]' : 'aspect-[9/16]'} rounded-lg border border-dashed border-brand-border/40 flex flex-col items-center justify-center text-gray-700`}>
        <span className="text-xs font-medium">{no}</span><span className="text-[8px]">Boş</span>
      </div>
    )
  }
  return (
    <button onClick={() => onToggle(item.id, !item.is_hazir)}
      title={`${item.kalip_kodu} · ${item.design_code || ''} · ${item.model || ''} · #${item.order_number} — tıkla: hazır işaretle`}
      className={`${big ? 'aspect-[9/15]' : 'aspect-[9/16]'} rounded-lg border overflow-hidden relative text-left ${item.is_hazir ? 'border-emerald-500/60' : 'border-accent/40'} bg-brand-input`}>
      {item.thumbnail_url && (
        <img src={item.thumbnail_url} alt="" className="absolute inset-0 w-full h-full object-cover opacity-55" onError={e => { e.target.style.display = 'none' }} />
      )}
      <span className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/30" />
      <div className={`absolute top-1 right-1 w-4 h-4 rounded-full flex items-center justify-center text-[8px] ${item.is_hazir ? 'bg-emerald-500 text-white' : 'bg-black/40 text-gray-400 border border-gray-500'}`}>✓</div>
      <div className="absolute top-1 left-1 text-[9px] font-mono text-accent bg-black/40 rounded px-1">{item.kalip_kodu}</div>
      <span onClick={(e) => { e.stopPropagation(); onRemove && onRemove(item) }} title="Kalıptan çıkar" className="absolute bottom-1 right-1 w-4 h-4 rounded-full bg-red-500/80 hover:bg-red-500 text-white text-[9px] flex items-center justify-center z-20">×</span>
      <div className="relative z-10 h-full flex flex-col justify-end p-1 text-center gap-0.5">
        <div className="text-[9px] font-semibold text-white leading-none truncate drop-shadow">{item.design_code || ''}</div>
        <div className="text-[8px] text-gray-200 leading-none drop-shadow">{shortModel(item.model)}</div>
        <div className="text-[7px] text-amber-200 leading-none drop-shadow truncate">{kilifLabel(item)}</div>
        <div className="text-[7px] text-gray-400 leading-none">#{no}</div>
      </div>
    </button>
  )
}

function shortModel(m) {
  if (!m) return ''
  return m.replace(/i\s*phone/i, '').replace(/apple/i, '').replace(/galaxy/i, '').replace(/samsung/i, '').trim().toUpperCase()
}
function kilifLabel(it) {
  // Kalibin GERCEK rengi (android beyaz->siyah sonrasi). Once kilif_rengi.
  if (it.kilif_rengi) return `Kılıf: ${String(it.kilif_rengi).toUpperCase()}`
  if (it.variation) return `Kılıf: ${String(it.variation).toUpperCase()}`
  return ''
}
function actionLabel(h) {
  if (h.action === 'stage_change') return `${h.from_label || '?'} → ${h.to_label || '?'}`
  const map = {
    hatali: '⚠ Hatalı baskı işaretlendi',
    hatali_geri: 'Hatalı işareti kaldırıldı',
    item_replan: '↩ Slot kalıptan çıkarıldı (geri planlandı)',
    item_cancel: '✕ Slot kalıptan çıkarıldı (iptal edildi)',
    slot_assigned: '➕ Slot atandı',
    deleted: '🗑 Kalıp silindi',
  }
  const base = map[h.action] || h.action
  return h.note ? `${base} — ${h.note}` : base
}
function fmtDate(iso) {
  if (!iso) return '?'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '?'
  return d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
function InfoRow({ label, value, mono }) {
  return (
    <div className="flex justify-between items-center py-1 text-xs">
      <span className="text-gray-500">{label}</span>
      <span className={`text-gray-200 ${mono ? 'font-mono' : ''}`}>{value || '—'}</span>
    </div>
  )
}
