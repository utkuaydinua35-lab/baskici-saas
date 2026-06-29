import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'

const VARYASYON_SIRA = ['SİYAH', 'BEYAZ', 'MAGSAFE', 'PARLAK', 'ŞEFFAF']

// Model adından marka çıkar
function markaBul(modelKey) {
  const m = (modelKey || '').toUpperCase()
  if (m.includes('IPHONE')) return 'APPLE'
  if (m.includes('SAMSUNG') || m.includes('NOTE') || /\bS\d/.test(m) || /^A\d/.test(m) || /^M\d/.test(m) || /^J\d/.test(m)) return 'SAMSUNG'
  if (m.includes('XIAOMI') || m.includes('REDMI') || m.includes('POCO') || m.startsWith('MI ')) return 'XIAOMI'
  if (m.includes('REALME')) return 'REALME'
  if (m.includes('OPPO')) return 'OPPO'
  if (m.includes('VIVO')) return 'VIVO'
  if (m.includes('HUAWEI')) return 'HUAWEI'
  if (m.includes('TECNO')) return 'TECNO'
  if (m.includes('INFINIX')) return 'INFINIX'
  if (m.includes('CASPER')) return 'CASPER'
  if (m.includes('GENERAL')) return 'GENERAL MOBILE'
  return 'DİĞER'
}
const MARKA_ONCELIK = ['APPLE', 'SAMSUNG', 'XIAOMI', 'REALME', 'OPPO', 'VIVO', 'HUAWEI', 'TECNO', 'INFINIX']

export default function StockPage() {
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeId, setActiveId] = useState(null)
  const [search, setSearch] = useState('')
  const [msg, setMsg] = useState(null)
  // dialoglar
  const [showNewGroup, setShowNewGroup] = useState(false)
  const [addItemGroup, setAddItemGroup] = useState(null)
  const [linkGroup, setLinkGroup] = useState(null)
  const [editItem, setEditItem] = useState(null)
  const [moveItem, setMoveItem] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/stock/groups')
      const gs = r.groups || []
      setGroups(gs)
      setActiveId(prev => (prev && gs.some(g => g.id === prev)) ? prev : (gs[0]?.id || null))
    } catch { setGroups([]) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const toplamStok = groups.reduce((a, g) => a + (g.toplam_stok || 0), 0)
  const dusukToplam = groups.reduce((a, g) => a + (g.dusuk_count || 0), 0)
  const cesit = groups.reduce((a, g) => a + (g.item_count || 0), 0)
  const active = groups.find(g => g.id === activeId) || null

  const flash = (ok, text) => { setMsg({ ok, text }); setTimeout(() => setMsg(null), 3500) }

  return (
    <div className="max-w-5xl">
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🗃️ Stok</h1>
          <p className="text-sm text-gray-500 mt-1">Model × varyasyon matrisi — hücreye tıkla, yerinde düzenle</p>
        </div>
        <button onClick={() => setShowNewGroup(true)} className="btn-secondary !text-sm">➕ Yeni ana kalem</button>
      </div>

      {msg && <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${msg.ok ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' : 'bg-red-500/10 border-red-500/20 text-red-300'}`}>{msg.text}</div>}

      <div className="grid grid-cols-3 gap-3 mb-5">
        <Kpi label="Toplam stok" value={toplamStok} />
        <Kpi label="Çeşit (model)" value={cesit} />
        <Kpi label="Düşük stok" value={dusukToplam} color={dusukToplam > 0 ? 'amber' : 'gray'} />
      </div>

      {loading ? (
        <div className="card text-center py-12 text-gray-500">Yükleniyor...</div>
      ) : groups.length === 0 ? (
        <div className="card text-center py-12 text-gray-500">
          <div className="text-3xl mb-2">📦</div>
          Henüz ana kalem yok. "Yeni ana kalem" ile başla (örn. "Boş Kılıf").
        </div>
      ) : (
        <>
          {/* Grup filtre chip'leri */}
          <div className="flex gap-2 mb-3 flex-wrap items-center">
            {groups.map(g => (
              <button key={g.id} onClick={() => setActiveId(g.id)}
                className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${activeId === g.id
                  ? 'bg-accent text-white border-accent'
                  : 'bg-brand-input/50 text-gray-300 border-brand-border hover:text-gray-100'}`}>
                {g.name}
                <span className={`ml-1.5 text-[11px] ${activeId === g.id ? 'text-white/80' : 'text-gray-500'}`}>{g.toplam_stok}</span>
                {g.dusuk_count > 0 && <span className="ml-1 text-[10px] text-amber-300">●{g.dusuk_count}</span>}
              </button>
            ))}
          </div>

          {/* Arama + grup araçları */}
          <div className="flex gap-2 items-center mb-3 flex-wrap">
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="🔍 Model ara — iPhone 13, S24…"
              className="input flex-1 min-w-[200px] !text-sm" />
            {active && (
              <>
                <button onClick={() => setAddItemGroup(active)} className="btn-secondary !text-sm whitespace-nowrap">➕ Model ekle</button>
                <GroupMenu group={active}
                  onLink={() => setLinkGroup(active)}
                  onDelete={async () => {
                    if (!confirm(`"${active.name}" ana kalemi ve tüm modelleri silinecek. Emin misin?`)) return
                    try { await api.del(`/api/stock/groups/${active.id}`); flash(true, 'Ana kalem silindi'); load() }
                    catch (e) { flash(false, 'Silinemedi: ' + (e?.detail || '')) }
                  }} />
              </>
            )}
          </div>

          {active && (
            <StockMatrix
              group={active} search={search} onReload={load} onFlash={flash}
              onEdit={(it) => setEditItem(it)} onMove={(it) => setMoveItem(it)} />
          )}
        </>
      )}

      {showNewGroup && <NewGroupDialog onClose={() => setShowNewGroup(false)} onSaved={(id) => { setShowNewGroup(false); load().then(() => id && setActiveId(id)) }} />}
      {addItemGroup && <AddItemDialog group={addItemGroup} onClose={() => setAddItemGroup(null)} onSaved={() => { setAddItemGroup(null); load() }} />}
      {linkGroup && <LinkProductsDialog group={linkGroup} onClose={() => setLinkGroup(null)} onSaved={() => { setLinkGroup(null); load() }} />}
      {editItem && <EditItemDialog item={editItem} onClose={() => setEditItem(null)} onSaved={() => { setEditItem(null); load() }} />}
      {moveItem && <MovementsDialog item={moveItem} onClose={() => setMoveItem(null)} />}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// Matris: satır = model (uyumlu modeller tek satır), sütun = varyasyon
// ═══════════════════════════════════════════════════════════

function StockMatrix({ group, search, onReload, onFlash, onEdit, onMove }) {
  const [edit, setEdit] = useState(null)      // { rowKey, col }
  const [editVal, setEditVal] = useState('')
  const [busy, setBusy] = useState(false)
  const [menuRow, setMenuRow] = useState(null)
  const [mergeFor, setMergeFor] = useState(null)

  // Sütunlar: grupta herhangi bir varyasyon varsa 5 standart sütunu hep göster
  // (boş hücreler tıklanıp doldurulabilsin). Hiç yoksa tek "Genel" sütun.
  const cols = useMemo(() => {
    const present = new Set(); let hasVar = false, hasNull = false
    for (const it of group.items) {
      const v = (it.variation || '').toUpperCase()
      if (v) { present.add(v); hasVar = true } else hasNull = true
    }
    if (!hasVar) return ['']
    const extra = [...present].filter(v => !VARYASYON_SIRA.includes(v)).sort()
    const c = [...VARYASYON_SIRA, ...extra]
    if (hasNull) c.push('')
    return c
  }, [group.items])

  // Satırlar: model-key bazında grupla
  const rows = useMemo(() => {
    const map = {}
    for (const it of group.items) {
      const models = (it.models && it.models.length ? it.models : [it.model]).filter(Boolean)
      const key = models.join(' / ') || '—'
      if (!map[key]) map[key] = { key, models, byVar: {}, toplam: 0 }
      map[key].byVar[(it.variation || '').toUpperCase()] = it
      map[key].toplam += it.quantity || 0
    }
    let list = Object.values(map)
    if (search.trim()) { const q = search.toLowerCase(); list = list.filter(r => r.key.toLowerCase().includes(q)) }
    list.sort((a, b) => {
      const ba = markaBul(a.key), bb = markaBul(b.key)
      const ia = MARKA_ONCELIK.indexOf(ba), ib = MARKA_ONCELIK.indexOf(bb)
      const pa = ia < 0 ? 99 : ia, pb = ib < 0 ? 99 : ib
      if (pa !== pb) return pa - pb
      if (ba !== bb) return ba.localeCompare(bb, 'tr')
      return a.key.localeCompare(b.key, 'tr')
    })
    return list
  }, [group.items, search])

  const startEdit = (row, col) => {
    const it = row.byVar[col]
    setEdit({ rowKey: row.key, col }); setEditVal(String(it?.quantity ?? ''))
  }
  const saveCell = async (row, col) => {
    const target = parseInt(editVal, 10)
    if (isNaN(target) || target < 0) { setEdit(null); return }
    const it = row.byVar[col]
    setBusy(true)
    try {
      if (it) {
        const delta = target - (it.quantity || 0)
        if (delta !== 0) await api.post(`/api/stock/${it.id}/adjust`, { delta, reason: 'manuel' })
      } else if (target > 0) {
        await api.post(`/api/stock/groups/${group.id}/items`, { models: row.models, variation: col || null, quantity: target })
      }
      setEdit(null); onReload()
    } catch (e) { onFlash(false, 'Kaydedilemedi: ' + (e?.detail || '')) }
    finally { setBusy(false) }
  }
  const bump = (d) => setEditVal(v => String(Math.max(0, (parseInt(v, 10) || 0) + d)))

  // "Genel" (varyasyonsuz) kaydı bir varyasyona taşı (toplu temizlik için tek tek)
  const moveToVariation = async (it, v) => {
    if (!v) return
    try { await api.patch(`/api/stock/${it.id}`, { variation: v }); setEdit(null); onReload() }
    catch (e) { onFlash(false, 'Taşınamadı: ' + (e?.detail || '')) }
  }

  const delRow = async (row) => {
    const items = Object.values(row.byVar)
    if (!confirm(`"${row.key}" satırı (${items.length} kayıt) silinecek. Emin misin?`)) return
    try { for (const it of items) await api.del(`/api/stock/${it.id}`); onFlash(true, 'Satır silindi'); onReload() }
    catch (e) { onFlash(false, 'Silinemedi: ' + (e?.detail || '')) }
    setMenuRow(null)
  }

  const allModels = useMemo(() => [...new Set(group.items.flatMap(it => (it.models && it.models.length ? it.models : [it.model]).filter(Boolean)))], [group.items])

  if (group.items.length === 0) {
    return <div className="card text-center py-10 text-gray-500"><div className="text-2xl mb-2">📭</div>Bu ana kalemde henüz model yok. "Model ekle" ile başla.</div>
  }

  // marka ayraçları için son markayı takip et
  let lastBrand = null

  return (
    <div className="card !p-0 overflow-x-auto">
      <table className="w-full text-sm" style={{ minWidth: 520 }}>
        <thead>
          <tr className="bg-brand-input/30 text-gray-400">
            <th className="text-left font-medium px-3 py-2.5">Model</th>
            {cols.map(c => <th key={c || '_'} className="font-medium px-2 py-2.5 text-center w-[78px]">{c || 'Genel'}</th>)}
            <th className="font-medium px-3 py-2.5 text-right w-[64px]">Toplam</th>
            <th className="w-8"></th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={cols.length + 3} className="text-center text-gray-500 py-6">Aramayla eşleşen model yok.</td></tr>
          ) : rows.map(row => {
            const brand = markaBul(row.key)
            const showBrand = brand !== lastBrand; lastBrand = brand
            return (
              <RowWithBrand key={row.key} showBrand={showBrand} brand={brand} colSpan={cols.length + 3}>
                <td className="px-3 py-2 align-middle">
                  <div className="flex items-center gap-1.5">
                    <span className="text-gray-200 truncate">{row.key}</span>
                    {row.models.length > 1 && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/15 text-blue-300 shrink-0" title={row.models.join(' / ')}>🔗{row.models.length}</span>}
                  </div>
                </td>
                {cols.map(col => {
                  const it = row.byVar[col]
                  const editing = edit && edit.rowKey === row.key && edit.col === col
                  if (editing) {
                    return (
                      <td key={col || '_'} className="px-1 py-1 text-center bg-accent/10">
                        <div className="flex items-center justify-center gap-0.5">
                          <button onClick={() => bump(-1)} className="w-6 h-7 rounded bg-brand-input text-gray-300 hover:text-white">−</button>
                          <input autoFocus type="number" value={editVal} onChange={e => setEditVal(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') saveCell(row, col); if (e.key === 'Escape') setEdit(null) }}
                            className="w-12 h-7 text-center rounded bg-brand-card border border-brand-border text-gray-100 text-sm" />
                          <button onClick={() => bump(1)} className="w-6 h-7 rounded bg-brand-input text-gray-300 hover:text-white">+</button>
                          <button disabled={busy} onClick={() => saveCell(row, col)} className="w-7 h-7 rounded bg-accent text-white" title="Kaydet">✓</button>
                        </div>
                        {it && <button onClick={() => { onMove(it); setEdit(null) }} className="text-[10px] text-gray-400 hover:underline mt-0.5">geçmiş</button>}
                        {col === '' && it && (
                          <select defaultValue="" onClick={e => e.stopPropagation()}
                            onChange={e => moveToVariation(it, e.target.value)}
                            className="mt-1 input !text-[10px] !py-0.5 w-full" title="Bu varyasyonsuz kaydı bir varyasyona taşı">
                            <option value="">→ varyasyona taşı…</option>
                            {VARYASYON_SIRA.map(v => <option key={v} value={v}>{v}</option>)}
                          </select>
                        )}
                      </td>
                    )
                  }
                  return (
                    <td key={col || '_'} onClick={() => startEdit(row, col)}
                      className={`px-2 py-2 text-center cursor-pointer hover:bg-accent/10 transition-colors ${it?.is_low ? 'bg-amber-500/15' : ''}`}>
                      {it ? (
                        <span className={`font-semibold ${it.is_low ? 'text-amber-300' : 'text-gray-200'}`}>{it.quantity}</span>
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                  )
                })}
                <td className="px-3 py-2 text-right font-semibold text-gray-200">{row.toplam}</td>
                <td className="px-1 py-2 text-center relative">
                  <button onClick={() => setMenuRow(menuRow === row.key ? null : row.key)} className="text-gray-500 hover:text-gray-200 px-1">⋯</button>
                  {menuRow === row.key && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setMenuRow(null)} />
                      <div className="absolute right-2 top-8 z-20 w-44 bg-brand-card border border-brand-border rounded-lg shadow-lg py-1 text-left">
                        <button onClick={() => { setMergeFor({ anaKey: row.key, anaModel: row.models[0], mevcut: row.models }); setMenuRow(null) }} className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-brand-input/50">🔗 Uyumlu model ekle</button>
                        <button onClick={() => { onEdit(Object.values(row.byVar)[0]); setMenuRow(null) }} className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-brand-input/50">✎ Modeli düzenle</button>
                        <button onClick={() => delRow(row)} className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10">🗑 Satırı sil</button>
                      </div>
                    </>
                  )}
                </td>
              </RowWithBrand>
            )
          })}
        </tbody>
      </table>

      {mergeFor && (
        <MergeModelDialog groupId={group.id} mergeFor={mergeFor} allModels={allModels}
          onClose={() => setMergeFor(null)} onDone={() => { setMergeFor(null); onReload() }} />
      )}
    </div>
  )
}

function RowWithBrand({ showBrand, brand, colSpan, children }) {
  return (
    <>
      {showBrand && (
        <tr className="bg-brand-bg/40"><td colSpan={colSpan} className="px-3 py-1 text-[11px] font-semibold text-gray-500 uppercase tracking-wide border-t border-brand-border/60">{brand}</td></tr>
      )}
      <tr className="border-t border-brand-border/40 hover:bg-brand-input/10">{children}</tr>
    </>
  )
}

function GroupMenu({ group, onLink, onDelete }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)} className="btn-secondary !text-sm">⋯</button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-10 z-20 w-48 bg-brand-card border border-brand-border rounded-lg shadow-lg py-1">
            <button onClick={() => { onLink(); setOpen(false) }} className="w-full text-left px-3 py-2 text-xs text-gray-300 hover:bg-brand-input/50">🔗 Ürün eşleştir ({group.linked_products?.length || 0})</button>
            <button onClick={() => { onDelete(); setOpen(false) }} className="w-full text-left px-3 py-2 text-xs text-red-400 hover:bg-red-500/10">🗑 Ana kalemi sil</button>
          </div>
        </>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// Dialoglar (korundu)
// ═══════════════════════════════════════════════════════════

function MergeModelDialog({ groupId, mergeFor, allModels, onClose, onDone }) {
  const [sel, setSel] = useState([])
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')
  const [katalog, setKatalog] = useState([])
  useEffect(() => { api.get('/api/stock/_models').then(r => setKatalog(r.models || [])).catch(() => setKatalog([])) }, [])
  const mevcutSet = new Set(mergeFor.mevcut.map(m => m.toUpperCase()))
  const havuz = [...new Set([...(katalog || []), ...(allModels || [])])]
  let secilebilir = havuz.filter(m => !mevcutSet.has(m.toUpperCase())).sort((a, b) => a.localeCompare(b, 'tr'))
  if (q.trim()) { const ql = q.toLowerCase(); secilebilir = secilebilir.filter(m => m.toLowerCase().includes(ql)) }
  const toggle = (m) => setSel(s => s.includes(m) ? s.filter(x => x !== m) : [...s, m])
  const kaydet = async () => {
    if (sel.length === 0) return
    setBusy(true)
    try {
      await api.post(`/api/stock/groups/${groupId}/merge-models`, { ana_model: mergeFor.anaModel, eklenecek_modeller: sel })
      onDone()
    } catch (e) { alert('Birleştirilemedi: ' + (e?.detail || '')); setBusy(false) }
  }
  return createPortal((
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 my-8 animate-popin max-h-[80vh] flex flex-col">
        <h2 className="text-base font-semibold text-gray-100 mb-1">🔗 Uyumlu model ekle</h2>
        <p className="text-xs text-gray-500 mb-1"><span className="text-gray-300">{mergeFor.anaKey}</span> ile aynı kalıbı paylaşan modeller:</p>
        <p className="text-[11px] text-gray-600 mb-3">Seçilen modeller bu stok havuzuna eklenir; ayrı kayıtları varsa pasifleşir.</p>
        <input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="🔍 Model ara..." className="input w-full !text-sm mb-2" />
        {sel.length > 0 && <p className="text-[11px] text-blue-300 mb-2">{sel.length} model seçili</p>}
        <div className="flex-1 overflow-y-auto -mx-1 px-1 space-y-1">
          {secilebilir.length === 0 ? (
            <p className="text-xs text-gray-500 py-4 text-center">Eklenebilecek başka model yok.</p>
          ) : secilebilir.map(m => (
            <label key={m} className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-brand-input/30 cursor-pointer">
              <input type="checkbox" checked={sel.includes(m)} onChange={() => toggle(m)} className="accent-blue-400" />
              <span className="text-sm text-gray-200">{m}</span>
            </label>
          ))}
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={kaydet} disabled={busy || sel.length === 0} className="btn-primary !text-sm">{busy ? '…' : `Birleştir (${sel.length})`}</button>
        </div>
      </div>
    </div>
  ), document.body)
}

function NewGroupDialog({ onClose, onSaved }) {
  const [name, setName] = useState('')
  const [threshold, setThreshold] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const save = async () => {
    if (!name.trim()) { setErr('İsim gerekli'); return }
    setSaving(true); setErr('')
    try {
      const r = await api.post('/api/stock/groups', { name: name.trim(), low_stock_threshold: threshold === '' ? 0 : parseInt(threshold, 10) })
      onSaved(r?.id)
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setSaving(false) }
  }
  return (
    <Modal title="Yeni ana kalem" onClose={onClose}>
      {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
      <F label="Ana kalem adı"><input className="input w-full" placeholder="Örn. Boş Kılıf" value={name} onChange={e => setName(e.target.value)} autoFocus /></F>
      <F label="Düşük stok uyarı eşiği (varsayılan)"><input type="number" className="input w-full" placeholder="0" value={threshold} onChange={e => setThreshold(e.target.value)} /></F>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
        <button onClick={save} disabled={saving} className="btn-primary !text-sm">{saving ? '...' : 'Oluştur'}</button>
      </div>
    </Modal>
  )
}

function ModelPicker({ models, setModels, modelList }) {
  const [input, setInput] = useState('')
  const [suggest, setSuggest] = useState([])
  const add = (m) => {
    const v = (m || '').trim()
    if (!v) return
    if (!models.includes(v)) setModels([...models, v])
    setInput('')
  }
  const remove = (m) => setModels(models.filter(x => x !== m))
  const loadSuggest = async (m) => {
    try {
      const r = await api.get(`/api/stock/groups/_suggest-compatible?model=${encodeURIComponent(m)}`)
      setSuggest((r.compatible || []).filter(x => !models.includes(x)))
    } catch { setSuggest([]) }
  }
  return (
    <div>
      <div className="flex gap-2">
        <input className="input flex-1" placeholder="Yazıp listeden seç..." list="stock-model-list" value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add(input) } }} />
        <button type="button" onClick={() => add(input)} className="btn-secondary !text-sm">+ Ekle</button>
      </div>
      <datalist id="stock-model-list">{modelList.map(m => <option key={m} value={m} />)}</datalist>
      {models.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {models.map(m => (
            <span key={m} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-accent/15 text-accent">
              {m}<button type="button" onClick={() => remove(m)} className="hover:text-red-300">×</button>
            </span>
          ))}
        </div>
      )}
      {models.length > 0 && (
        <button type="button" onClick={() => loadSuggest(models[models.length - 1])} className="text-[11px] text-gray-400 hover:text-accent mt-2">
          💡 "{models[models.length - 1]}" ile uyumlu olabilecekleri öner
        </button>
      )}
      {suggest.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2 p-2 rounded-lg bg-brand-input/40 border border-brand-border">
          <span className="text-[10px] text-gray-500 w-full">Öneriler (tıkla → ekle):</span>
          {suggest.map(s => (
            <button type="button" key={s} onClick={() => { add(s); setSuggest(suggest.filter(x => x !== s)) }}
              className="text-xs px-2 py-1 rounded-full bg-brand-card border border-brand-border text-gray-300 hover:border-accent hover:text-accent">+ {s}</button>
          ))}
        </div>
      )}
    </div>
  )
}

function AddItemDialog({ group, onClose, onSaved }) {
  const [models, setModels] = useState([])
  const [name, setName] = useState('')
  const [variation, setVariation] = useState('')
  const [quantity, setQuantity] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [modelList, setModelList] = useState([])
  useEffect(() => { api.get('/api/stock/_models').then(r => setModelList(r.models || [])).catch(() => {}) }, [])
  const save = async () => {
    if (models.length === 0) { setErr('En az bir model ekle'); return }
    setSaving(true); setErr('')
    try {
      await api.post(`/api/stock/groups/${group.id}/items`, {
        models, name: name.trim() || null, variation: variation.trim() || null,
        quantity: quantity === '' ? 0 : parseInt(quantity, 10),
      })
      onSaved()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setSaving(false) }
  }
  return (
    <Modal title={`Model ekle — ${group.name}`} onClose={onClose}>
      {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
      <F label="Uyumlu telefon modelleri">
        <ModelPicker models={models} setModels={setModels} modelList={modelList} />
        <span className="block text-[10px] text-gray-500 mt-1">Eklediğin modellerden herhangi biri sipariş edilince buradan düşer.</span>
      </F>
      <F label="Varyasyon (opsiyonel)"><input className="input w-full" placeholder="siyah / beyaz / şeffaf — boş bırakılabilir" value={variation} onChange={e => setVariation(e.target.value)} /></F>
      <F label="Etiket (opsiyonel)"><input className="input w-full" placeholder="Boş bırakılırsa modellerden üretilir" value={name} onChange={e => setName(e.target.value)} /></F>
      <F label="Başlangıç adedi"><input type="number" className="input w-full" placeholder="0" value={quantity} onChange={e => setQuantity(e.target.value)} /></F>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
        <button onClick={save} disabled={saving} className="btn-primary !text-sm">{saving ? '...' : 'Ekle'}</button>
      </div>
    </Modal>
  )
}

function EditItemDialog({ item, onClose, onSaved }) {
  const [models, setModels] = useState(item.models && item.models.length ? item.models : (item.model ? [item.model] : []))
  const [name, setName] = useState(item.name || '')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [modelList, setModelList] = useState([])
  useEffect(() => { api.get('/api/stock/_models').then(r => setModelList(r.models || [])).catch(() => {}) }, [])
  const save = async () => {
    if (models.length === 0) { setErr('En az bir model gerekli'); return }
    setSaving(true); setErr('')
    try {
      await api.patch(`/api/stock/${item.id}`, { models, name: name.trim() || null })
      onSaved()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setSaving(false) }
  }
  return (
    <Modal title="Modeli düzenle" onClose={onClose}>
      {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
      <F label="Uyumlu telefon modelleri">
        <ModelPicker models={models} setModels={setModels} modelList={modelList} />
      </F>
      <F label="Etiket (opsiyonel)"><input className="input w-full" placeholder="Boş bırakılırsa modellerden üretilir" value={name} onChange={e => setName(e.target.value)} /></F>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
        <button onClick={save} disabled={saving} className="btn-primary !text-sm">{saving ? '...' : 'Kaydet'}</button>
      </div>
    </Modal>
  )
}

function LinkProductsDialog({ group, onClose, onSaved }) {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(() => new Set((group.linked_products || []).map(p => p.product_id)))
  const [filter, setFilter] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  useEffect(() => {
    api.get('/api/stock/groups/_assignable-products')
      .then(r => setProducts(r.products || []))
      .catch(() => setErr('Ürünler yüklenemedi'))
      .finally(() => setLoading(false))
  }, [])
  const toggle = (pid) => {
    const next = new Set(selected)
    if (next.has(pid)) next.delete(pid); else next.add(pid)
    setSelected(next)
  }
  const filtered = products.filter(p => !filter || (p.title || '').toLowerCase().includes(filter.toLowerCase()))
  const save = async () => {
    setSaving(true); setErr('')
    try {
      const linked = products.filter(p => selected.has(p.product_id))
        .map(p => ({ product_id: p.product_id, title: p.title, store_id: p.store_id }))
      await api.patch(`/api/stock/groups/${group.id}`, { linked_products: linked })
      onSaved()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setSaving(false) }
  }
  return (
    <Modal title={`Ürün eşleştir — ${group.name}`} onClose={onClose} wide>
      <p className="text-xs text-gray-500 mb-3">Bu ana kaleme bağlı ürünler kargoya verilince, siparişteki modele göre stok düşer.</p>
      {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
      <input className="input w-full mb-3 !text-sm" placeholder="Ürün ara..." value={filter} onChange={e => setFilter(e.target.value)} />
      {loading ? <p className="text-sm text-gray-500 py-4">Yükleniyor...</p> : (
        <div className="max-h-80 overflow-y-auto space-y-1">
          {filtered.map(p => (
            <label key={p.product_id} className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer ${selected.has(p.product_id) ? 'border-accent bg-accent/10' : 'border-brand-border hover:bg-brand-input/30'}`}>
              <input type="checkbox" checked={selected.has(p.product_id)} onChange={() => toggle(p.product_id)} />
              <span className="text-sm text-gray-200 flex-1 truncate">{p.title || '(başlıksız)'}</span>
              <span className="text-[10px] text-gray-500 font-mono">{p.product_id}</span>
            </label>
          ))}
          {filtered.length === 0 && <p className="text-sm text-gray-500 py-4 text-center">Ürün bulunamadı</p>}
        </div>
      )}
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
        <button onClick={save} disabled={saving} className="btn-primary !text-sm">{saving ? '...' : `Kaydet (${selected.size})`}</button>
      </div>
    </Modal>
  )
}

function MovementsDialog({ item, onClose }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    api.get(`/api/stock/${item.id}/movements`).then(r => setRows(r.items || [])).catch(() => setRows([])).finally(() => setLoading(false))
  }, [item.id])
  return (
    <Modal title={`Hareket geçmişi — ${item.model || item.name}${item.variation ? ' · ' + item.variation : ''}`} onClose={onClose} wide>
      {loading ? <p className="text-sm text-gray-500 py-4">Yükleniyor...</p> : rows.length === 0 ? (
        <p className="text-sm text-gray-500 py-4 text-center">Henüz hareket yok</p>
      ) : (
        <div className="max-h-80 overflow-y-auto divide-y divide-brand-border/40">
          {rows.map((m, i) => (
            <div key={i} className="flex items-center gap-3 py-2 text-sm">
              <span className={`font-semibold ${m.delta > 0 ? 'text-emerald-300' : 'text-red-300'}`}>{m.delta > 0 ? '+' : ''}{m.delta}</span>
              <span className="text-gray-400 flex-1">{m.reason}{m.note ? ` · ${m.note}` : ''}</span>
              <span className="text-xs text-gray-500">{m.created_at ? new Date(m.created_at).toLocaleString('tr-TR') : ''}</span>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}

function Modal({ title, children, onClose, wide }) {
  return createPortal((
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className={`bg-brand-card border border-brand-border rounded-xl w-full ${wide ? 'max-w-xl' : 'max-w-md'} max-h-[90vh] overflow-y-auto p-5`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  ), document.body)
}

function F({ label, children }) {
  return <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{label}</span>{children}</label>
}

function Kpi({ label, value, color = 'gray' }) {
  const c = color === 'amber' ? 'text-amber-300' : 'text-gray-100'
  return <div className="card !py-3"><div className="text-xs text-gray-500">{label}</div><div className={`text-xl font-semibold ${c}`}>{value}</div></div>
}
