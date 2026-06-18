import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function StockPage() {
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)       // acik ana kalem id
  const [showNewGroup, setShowNewGroup] = useState(false)
  const [addItemGroup, setAddItemGroup] = useState(null)  // alt kalem ekleme dialogu
  const [linkGroup, setLinkGroup] = useState(null)        // urun eslestirme dialogu
  const [adjItem, setAdjItem] = useState(null)            // stok ayarlama
  const [editItem, setEditItem] = useState(null)          // alt kalem duzenleme
  const [moveItem, setMoveItem] = useState(null)          // hareket gecmisi
  const [msg, setMsg] = useState(null)
  const [search, setSearch] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/stock/groups')
      setGroups(r.groups || [])
    } catch { setGroups([]) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const toplamStok = groups.reduce((a, g) => a + (g.toplam_stok || 0), 0)
  const dusukToplam = groups.reduce((a, g) => a + (g.dusuk_count || 0), 0)

  return (
    <div className="max-w-5xl">
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🗃️ Stok</h1>
          <p className="text-sm text-gray-500 mt-1">Ana kalem (ürün) · alt kalem (model) bazlı stok takibi</p>
        </div>
        <button onClick={() => setShowNewGroup(true)} className="btn-primary !text-sm">➕ Yeni Ana Kalem</button>
      </div>

      {msg && <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${msg.ok ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' : 'bg-red-500/10 border-red-500/20 text-red-300'}`}>{msg.text}</div>}

      <div className="grid grid-cols-3 gap-3 mb-5">
        <Kpi label="Ana Kalem" value={groups.length} />
        <Kpi label="Toplam Stok" value={toplamStok} />
        <Kpi label="Düşük Stok" value={dusukToplam} color={dusukToplam > 0 ? 'amber' : 'gray'} />
      </div>

      <div className="mb-4">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="🔍 Model ara (örn. iPhone 13, S21)..."
          className="input w-full !text-sm" />
      </div>

      {loading ? (
        <div className="card text-center py-12 text-gray-500">Yükleniyor...</div>
      ) : groups.length === 0 ? (
        <div className="card text-center py-12 text-gray-500">
          <div className="text-3xl mb-2">📦</div>
          Henüz ana kalem yok. "Yeni Ana Kalem" ile başla (örn. "Ekran Koruyucu").
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map(g => (
            <GroupCard
              key={g.id} g={g} search={search} onReload={load}
              expanded={expanded === g.id || (!!search && (g.items || []).some(it => ((it.models && it.models.length ? it.models : [it.model]).filter(Boolean).join(' ')).toLowerCase().includes(search.toLowerCase())))}
              onToggle={() => setExpanded(expanded === g.id ? null : g.id)}
              onAddItem={() => setAddItemGroup(g)}
              onLink={() => setLinkGroup(g)}
              onAdjust={(it) => setAdjItem(it)}
              onMove={(it) => setMoveItem(it)}
              onEdit={(it) => setEditItem(it)}
              onDeleteGroup={async () => {
                if (!confirm(`"${g.name}" ana kalemi ve tüm alt kalemleri silinecek. Emin misin?`)) return
                try { await api.del(`/api/stock/groups/${g.id}`); load() }
                catch (e) { setMsg({ ok: false, text: 'Silinemedi: ' + (e?.detail || '') }) }
              }}
            />
          ))}
        </div>
      )}

      {showNewGroup && <NewGroupDialog onClose={() => setShowNewGroup(false)} onSaved={() => { setShowNewGroup(false); load() }} />}
      {addItemGroup && <AddItemDialog group={addItemGroup} onClose={() => setAddItemGroup(null)} onSaved={() => { setAddItemGroup(null); load() }} />}
      {linkGroup && <LinkProductsDialog group={linkGroup} onClose={() => setLinkGroup(null)} onSaved={() => { setLinkGroup(null); load() }} />}
      {adjItem && <AdjustDialog item={adjItem} onClose={() => setAdjItem(null)} onSaved={() => { setAdjItem(null); load() }} />}
      {editItem && <EditItemDialog item={editItem} onClose={() => setEditItem(null)} onSaved={() => { setEditItem(null); load() }} />}
      {moveItem && <MovementsDialog item={moveItem} onClose={() => setMoveItem(null)} />}
    </div>
  )
}

const VARYASYON_SIRA = ['SİYAH', 'BEYAZ', 'MAGSAFE', 'PARLAK', 'ŞEFFAF']

// Model adindan marka cikar
function markaBul(modelKey) {
  const m = (modelKey || '').toUpperCase()
  if (m.includes('IPHONE')) return 'APPLE'
  if (m.startsWith('S') && /^S\d/.test(m.replace(/[^A-Z0-9].*/, ''))) return 'SAMSUNG'
  if (m.includes('SAMSUNG') || m.includes('NOTE') || /\bS\d/.test(m) || m.startsWith('A') || m.startsWith('M') || m.startsWith('J')) return 'SAMSUNG'
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

function ModelGroupedItems({ items, search, groupId, onReload, onEdit, onAdjust, onMove }) {
  const [openBrand, setOpenBrand] = useState(null)
  const [openModel, setOpenModel] = useState(null)
  const [mergeFor, setMergeFor] = useState(null)  // { anaKey, anaModel, mevcut }
  // Model bazinda grupla (uyumlu modeller tek satir)
  const mgroups = {}
  for (const it of items) {
    const modelsArr = (it.models && it.models.length ? it.models : [it.model]).filter(Boolean)
    const key = modelsArr.join(' / ') || '—'
    if (!mgroups[key]) mgroups[key] = { key, models: modelsArr, items: [] }
    mgroups[key].items.push(it)
  }
  let modelList = Object.values(mgroups)
  if (search) {
    const q = search.toLowerCase()
    modelList = modelList.filter(mg => mg.key.toLowerCase().includes(q))
  }
  // Marka bazinda grupla
  const brands = {}
  for (const mg of modelList) {
    const b = markaBul(mg.key)
    if (!brands[b]) brands[b] = []
    brands[b].push(mg)
  }
  // Marka sirasi: APPLE, SAMSUNG, sonra alfabetik
  const ONCELIK = ['APPLE', 'SAMSUNG', 'XIAOMI', 'REALME', 'OPPO', 'VIVO', 'HUAWEI', 'TECNO', 'INFINIX']
  const brandList = Object.keys(brands).sort((a, b) => {
    const ia = ONCELIK.indexOf(a), ib = ONCELIK.indexOf(b)
    if (ia < 0 && ib < 0) return a.localeCompare(b, 'tr')
    if (ia < 0) return 1
    if (ib < 0) return -1
    return ia - ib
  })
  if (modelList.length === 0) {
    return <p className="text-xs text-gray-500 py-2">Aramayla eşleşen model yok.</p>
  }
  const varSort = (a, b) => {
    const ia = VARYASYON_SIRA.indexOf((a.variation || '').toUpperCase())
    const ib = VARYASYON_SIRA.indexOf((b.variation || '').toUpperCase())
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  }
  // Arama varsa markalar+modeller acik gelsin
  const autoOpen = !!search
  return (
    <div className="space-y-1">
      {brandList.map(brand => {
        const bModels = [...brands[brand]].sort((a, b) => a.key.localeCompare(b.key, 'tr'))
        const bToplam = bModels.reduce((a, mg) => a + mg.items.reduce((s, it) => s + (it.quantity || 0), 0), 0)
        const bAcik = autoOpen || openBrand === brand
        return (
          <div key={brand} className="border border-brand-border/40 rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 bg-brand-input/30 cursor-pointer hover:bg-brand-input/50" onClick={() => setOpenBrand(bAcik && !autoOpen ? null : brand)}>
              <span className="text-gray-500 text-xs">{bAcik ? '▾' : '▸'}</span>
              <span className="flex-1 text-sm font-semibold text-gray-100">{brand}</span>
              <span className="text-[11px] text-gray-500">{bModels.length} model</span>
              <span className="text-sm font-semibold text-gray-300">{bToplam} adet</span>
            </div>
            {bAcik && (
              <div className="divide-y divide-brand-border/30 px-2">
                {bModels.map(mg => {
                  const toplam = mg.items.reduce((a, it) => a + (it.quantity || 0), 0)
                  const mAcik = autoOpen || openModel === mg.key
                  const dusuk = mg.items.some(it => it.is_low)
                  // 5 varyasyonu doldur (eksik = 0, kayit yok)
                  const byVar = {}
                  for (const it of mg.items) byVar[(it.variation || '').toUpperCase()] = it
                  const tumVar = VARYASYON_SIRA.map(v => byVar[v] || { _bos: true, variation: v, quantity: 0, model: mg.models[0], models: mg.models })
                  return (
                    <div key={mg.key}>
                      <div className="flex items-center gap-2 py-2 pl-4 cursor-pointer hover:bg-brand-input/20" onClick={() => setOpenModel(mAcik && !autoOpen ? null : mg.key)}>
                        <span className="text-gray-500 text-xs">{mAcik ? '▾' : '▸'}</span>
                        <span className="flex-1 text-sm text-gray-200 truncate">{mg.key}</span>
                        {mg.models.length > 1 && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/15 text-blue-300" title={mg.models.join(' / ')}>🔗 {mg.models.length}</span>}
                        {dusuk && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300">düşük</span>}
                        <span className="text-sm font-semibold text-gray-200">{toplam} adet</span>
                        <button onClick={(e) => { e.stopPropagation(); setMergeFor({ anaKey: mg.key, anaModel: mg.models[0], mevcut: mg.models }) }}
                          className="text-[11px] text-blue-300/80 hover:text-blue-200 hover:underline whitespace-nowrap" title="Bu modelle uyumlu (ayni kalip) modeller ekle">🔗 Uyumlu</button>
                      </div>
                      {mAcik && (
                        <div className="pl-8 pb-2 space-y-1">
                          {[...tumVar].sort(varSort).map((it, vi) => (
                            <div key={it.id || ('bos-' + vi)} className="flex items-center gap-3 py-1.5 border-l-2 border-brand-border/40 pl-3">
                              <span className={`flex-1 text-xs ${it._bos ? 'text-gray-600' : 'text-gray-300'}`}>{it.variation || '—'}</span>
                              {it.is_low && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300">düşük</span>}
                              <span className={`text-sm font-semibold ${it._bos ? 'text-gray-600' : it.is_low ? 'text-amber-300' : 'text-gray-200'}`}>{it.quantity}</span>
                              {it._bos ? (
                                <span className="text-[10px] text-gray-600">kayıt yok</span>
                              ) : (
                                <>
                                  <button onClick={() => onEdit(it)} className="text-xs text-gray-400 hover:text-accent hover:underline">✎</button>
                                  <button onClick={() => onAdjust(it)} className="text-xs text-accent hover:underline">± Ayarla</button>
                                  <button onClick={() => onMove(it)} className="text-xs text-gray-400 hover:underline">Geçmiş</button>
                                </>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
      {mergeFor && (
        <MergeModelDialog groupId={groupId} mergeFor={mergeFor} allModels={[...new Set(items.flatMap(it => (it.models && it.models.length ? it.models : [it.model]).filter(Boolean)))]}
          onClose={() => setMergeFor(null)} onDone={() => { setMergeFor(null); onReload && onReload() }} />
      )}
    </div>
  )
}

function MergeModelDialog({ groupId, mergeFor, allModels, onClose, onDone }) {
  const [sel, setSel] = useState([])
  const [busy, setBusy] = useState(false)
  // Ana modelle zaten birlesik olanlar haric, secilebilir modeller
  const mevcutSet = new Set(mergeFor.mevcut.map(m => m.toUpperCase()))
  const secilebilir = allModels.filter(m => !mevcutSet.has(m.toUpperCase())).sort((a, b) => a.localeCompare(b, 'tr'))
  const toggle = (m) => setSel(s => s.includes(m) ? s.filter(x => x !== m) : [...s, m])
  const kaydet = async () => {
    if (sel.length === 0) return
    setBusy(true)
    try {
      await api.post(`/api/stock/groups/${groupId}/merge-models`, { ana_model: mergeFor.anaModel, eklenecek_modeller: sel })
      onDone()
    } catch (e) { alert('Birleştirilemedi: ' + (e?.detail || '')); setBusy(false) }
  }
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 my-8 animate-popin max-h-[80vh] flex flex-col">
        <h2 className="text-base font-semibold text-gray-100 mb-1">🔗 Uyumlu Model Ekle</h2>
        <p className="text-xs text-gray-500 mb-1"><span className="text-gray-300">{mergeFor.anaKey}</span> ile aynı kalıbı paylaşan modeller:</p>
        <p className="text-[11px] text-gray-600 mb-3">Seçilen modeller bu stok havuzuna eklenir; ayrı kayıtları varsa pasifleşir (stok bu modelden yönetilir).</p>
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
  )
}

function GroupCard({ g, search, expanded, onToggle, onAddItem, onLink, onAdjust, onMove, onEdit, onDeleteGroup, onReload }) {
  return (
    <div className="card !p-0 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 hover:bg-brand-input/30 cursor-pointer" onClick={onToggle}>
        <span className="text-gray-500 text-sm">{expanded ? '▾' : '▸'}</span>
        <span className="font-medium text-gray-100 flex-1">{g.name}</span>
        {g.dusuk_count > 0 && <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300">⚠ {g.dusuk_count} düşük</span>}
        <span className="text-xs text-gray-400">{g.item_count} model</span>
        <span className="text-sm font-semibold text-gray-200">{g.toplam_stok} adet</span>
        {(g.linked_products?.length || 0) > 0 && <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300">🔗 {g.linked_products.length}</span>}
      </div>
      {expanded && (
        <div className="border-t border-brand-border px-4 py-3 bg-brand-bg/30">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <button onClick={onAddItem} className="btn-secondary !text-xs">➕ Model Ekle</button>
            <button onClick={onLink} className="btn-secondary !text-xs">🔗 Ürün Eşleştir ({g.linked_products?.length || 0})</button>
            <button onClick={onDeleteGroup} className="text-xs text-red-400/70 hover:text-red-300 ml-auto">🗑 Ana Kalemi Sil</button>
          </div>
          {g.items.length === 0 ? (
            <p className="text-xs text-gray-500 py-2">Henüz model eklenmemiş. "Model Ekle" ile telefon modeli + adet gir.</p>
          ) : (
            <ModelGroupedItems items={g.items} search={search} groupId={g.id} onReload={onReload} onEdit={onEdit} onAdjust={onAdjust} onMove={onMove} />
          )}
        </div>
      )}
    </div>
  )
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
      await api.post('/api/stock/groups', { name: name.trim(), low_stock_threshold: threshold === '' ? 0 : parseInt(threshold, 10) })
      onSaved()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setSaving(false) }
  }
  return (
    <Modal title="Yeni Ana Kalem" onClose={onClose}>
      {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
      <F label="Ana kalem adı"><input className="input w-full" placeholder="Örn. Ekran Koruyucu" value={name} onChange={e => setName(e.target.value)} autoFocus /></F>
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
    <Modal title={`Alt Kalem Ekle — ${group.name}`} onClose={onClose}>
      {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
      <F label="Uyumlu telefon modelleri">
        <ModelPicker models={models} setModels={setModels} modelList={modelList} />
        <span className="block text-[10px] text-gray-500 mt-1">Bu alt kalem tek stok tutar; eklediğin modellerden herhangi biri sipariş edilince buradan düşer.</span>
      </F>
      <F label="Etiket (opsiyonel)"><input className="input w-full" placeholder="Boş bırakılırsa modellerden üretilir" value={name} onChange={e => setName(e.target.value)} /></F>
      <F label="Varyasyon (opsiyonel)"><input className="input w-full" placeholder="siyah / beyaz / şeffaf — boş bırakılabilir" value={variation} onChange={e => setVariation(e.target.value)} /></F>
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
    <Modal title="Alt Kalem Düzenle" onClose={onClose}>
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
    <Modal title={`Ürün Eşleştir — ${group.name}`} onClose={onClose} wide>
      <p className="text-xs text-gray-500 mb-3">Bu ana kaleme bağlı ürünler kargoya verilince, siparişteki modele göre alt kalem stoğu düşer.</p>
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

function AdjustDialog({ item, onClose, onSaved }) {
  const [sign, setSign] = useState(1)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('manuel')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const save = async () => {
    const n = parseInt(amount, 10)
    if (!n || n <= 0) { setErr('Geçerli miktar gir'); return }
    setSaving(true); setErr('')
    try {
      await api.post(`/api/stock/${item.id}/adjust`, { delta: sign * n, reason, note: note || null })
      onSaved()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Hata'); setSaving(false) }
  }
  return (
    <Modal title={`Stok Ayarla — ${item.model || item.name}`} onClose={onClose}>
      {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
      <p className="text-sm text-gray-400 mb-3">Mevcut: <span className="font-semibold text-gray-200">{item.quantity}</span> adet</p>
      <div className="flex gap-2 mb-3">
        <button onClick={() => setSign(1)} className={`flex-1 py-2 rounded-lg text-sm ${sign === 1 ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-brand-input text-gray-400'}`}>➕ Giriş</button>
        <button onClick={() => setSign(-1)} className={`flex-1 py-2 rounded-lg text-sm ${sign === -1 ? 'bg-red-500/20 text-red-300 border border-red-500/40' : 'bg-brand-input text-gray-400'}`}>➖ Çıkış</button>
      </div>
      <F label="Miktar"><input type="number" className="input w-full" placeholder="0" value={amount} onChange={e => setAmount(e.target.value)} autoFocus /></F>
      <F label="Not (opsiyonel)"><input className="input w-full" value={note} onChange={e => setNote(e.target.value)} /></F>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
        <button onClick={save} disabled={saving} className="btn-primary !text-sm">{saving ? '...' : 'Uygula'}</button>
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
    <Modal title={`Hareket Geçmişi — ${item.model || item.name}`} onClose={onClose} wide>
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
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className={`bg-brand-card border border-brand-border rounded-xl w-full ${wide ? 'max-w-xl' : 'max-w-md'} max-h-[90vh] overflow-y-auto p-5`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function F({ label, children }) {
  return <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{label}</span>{children}</label>
}

function Kpi({ label, value, color = 'gray' }) {
  const c = color === 'amber' ? 'text-amber-300' : 'text-gray-100'
  return <div className="card !py-3"><div className="text-xs text-gray-500">{label}</div><div className={`text-xl font-semibold ${c}`}>{value}</div></div>
}
