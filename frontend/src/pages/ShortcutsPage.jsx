import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

const KIND_BADGES = {
  simple:  { label: 'Basit',   color: 'bg-gray-500/15 text-gray-300' },
  color:   { label: 'Renkli',  color: 'bg-blue-500/15 text-blue-300' },
  couple:  { label: 'Couple',  color: 'bg-pink-500/15 text-pink-300' },
  variant: { label: 'Variant', color: 'bg-amber-500/15 text-amber-300' },
}

export default function ShortcutsPage() {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [storesLoading, setStoresLoading] = useState(true)
  const [selectedStore, setSelectedStore] = useState('')
  const [shortcuts, setShortcuts] = useState([])
  const [stats, setStats] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [editingShortcut, setEditingShortcut] = useState(null)
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())

  // ─── 1) Mount: stores'u yükle ─────────────────────────────
  useEffect(() => {
    let cancelled = false
    setStoresLoading(true)
    api.get('/api/stores')
      .then(s => {
        if (cancelled) return
        console.log('[shortcuts] stores yüklendi:', s)
        const list = Array.isArray(s) ? s : []
        setStores(list)
        if (list.length > 0) setSelectedStore(list[0].id)
      })
      .catch(e => {
        if (cancelled) return
        console.error('[shortcuts] stores hatası:', e)
        setError('Mağazalar yüklenemedi: ' + (e.detail || e.message || 'bilinmeyen'))
      })
      .finally(() => {
        if (!cancelled) setStoresLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  // ─── 2) selectedStore veya search değişince shortcuts yükle ───
  useEffect(() => {
    if (!selectedStore) return
    let cancelled = false
    setLoading(true)
    const delay = search ? 350 : 0
    const t = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ store_id: selectedStore })
        if (search) params.set('search', search)
        const [list, st] = await Promise.all([
          api.get(`/api/shortcuts?${params}`),
          api.get(`/api/shortcuts/_stats?store_id=${selectedStore}`),
        ])
        if (cancelled) return
        console.log('[shortcuts] yüklendi:', list?.length, 'kayıt')
        setShortcuts(Array.isArray(list) ? list : [])
        setStats(st)
        setSelectedIds(new Set())
        setError('')
      } catch (e) {
        if (cancelled) return
        console.error('[shortcuts] yükleme hatası:', e)
        setError(e.detail || 'Yükleme başarısız')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, delay)
    return () => { cancelled = true; clearTimeout(t) }
  }, [selectedStore, search])

  // ─── İşlemler ────────────────────────────────────────────
  const reload = () => {
    // Search state'ini değiştirmeden yeniden yüklemek için trick: aynı search ile re-trigger
    setSearch(s => s)
    // Yukarıdaki state aynıysa re-render etmez, o yüzden:
    if (!selectedStore) return
    setLoading(true)
    Promise.all([
      api.get(`/api/shortcuts?store_id=${selectedStore}${search ? `&search=${encodeURIComponent(search)}` : ''}`),
      api.get(`/api/shortcuts/_stats?store_id=${selectedStore}`),
    ])
      .then(([list, st]) => {
        setShortcuts(Array.isArray(list) ? list : [])
        setStats(st)
        setSelectedIds(new Set())
      })
      .catch(e => setError(e.detail || 'Yükleme başarısız'))
      .finally(() => setLoading(false))
  }

  const handleDelete = async (shortcut) => {
    if (!confirm(`"${shortcut.key}" kısayolunu sil?`)) return
    try {
      await api.del(`/api/shortcuts/${shortcut.id}`)
      reload()
    } catch (e) {
      toast.error(e.detail || 'Silinemedi')
    }
  }

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`${selectedIds.size} kısayolu silmek istiyor musun?`)) return
    try {
      await api.post('/api/shortcuts/bulk-delete', { ids: Array.from(selectedIds) })
      reload()
    } catch (e) {
      toast.error(e.detail || 'Silinemedi')
    }
  }

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === shortcuts.length) setSelectedIds(new Set())
    else setSelectedIds(new Set(shortcuts.map(s => s.id)))
  }

  // ─── Render ──────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">Kısayollar</h1>
          <p className="text-sm text-gray-500 mt-1">
            Tasarım adı → tasarım kodu eşleştirmeleri
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowImportDialog(true)} className="btn-secondary !text-xs" disabled={!selectedStore}>
            ↑ JSON Yükle
          </button>
          <button onClick={() => setShowAddDialog(true)} className="btn-primary" disabled={!selectedStore}>
            + Yeni
          </button>
        </div>
      </div>

      {storesLoading && (
        <div className="card text-center py-8 text-gray-500">
          <div className="text-3xl mb-2">⏳</div>
          Yükleniyor...
        </div>
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
          {/* Store selector + search + stats */}
          <div className="card mb-4 !p-3 space-y-3">
            <div className="flex gap-2 flex-wrap items-center">
              <select
                value={selectedStore}
                onChange={e => setSelectedStore(e.target.value)}
                className="input !text-sm !py-1.5 min-w-[200px]"
              >
                {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>

              <input
                type="text"
                placeholder="Anahtar veya değer ara..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="input !text-sm !py-1.5 flex-1 min-w-[200px]"
              />

              {selectedIds.size > 0 && (
                <button onClick={handleBulkDelete} className="btn-secondary !text-xs !text-red-400">
                  🗑 {selectedIds.size} seçileni sil
                </button>
              )}
            </div>

            {stats && stats.total > 0 && (
              <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                <span><strong className="text-gray-300">{stats.total}</strong> toplam</span>
                {Object.entries(stats.by_kind || {}).map(([kind, count]) => (
                  <span key={kind}>
                    <strong className="text-gray-300">{count}</strong> {KIND_BADGES[kind]?.label || kind}
                  </span>
                ))}
              </div>
            )}
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
              {error}
            </div>
          )}

          {loading && <div className="text-gray-500 text-sm text-center py-8">Yükleniyor...</div>}

          {!loading && shortcuts.length === 0 && !error && (
            <div className="card text-center py-12 text-gray-500">
              <div className="text-3xl mb-2">🔗</div>
              {search ? 'Arama sonucu yok.' : 'Hiç kısayol yok. + Yeni ile başla veya JSON yükle.'}
            </div>
          )}

          {!loading && shortcuts.length > 0 && (
            <div className="card !p-0 overflow-hidden">
              <div className="overflow-x-auto"><table className="w-full text-sm min-w-[640px]">
                <thead className="bg-brand-input border-b border-brand-border">
                  <tr className="text-left text-xs text-gray-500">
                    <th className="px-3 py-2 w-8">
                      <input
                        type="checkbox"
                        checked={selectedIds.size === shortcuts.length && shortcuts.length > 0}
                        onChange={toggleSelectAll}
                      />
                    </th>
                    <th className="px-3 py-2 font-medium">Anahtar (tasarım adı)</th>
                    <th className="px-3 py-2 font-medium">Değer (kod)</th>
                    <th className="px-3 py-2 font-medium">Tip</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border/50">
                  {shortcuts.map(s => {
                    const kind = KIND_BADGES[s.kind] || KIND_BADGES.simple
                    return (
                      <tr key={s.id} className="hover:bg-brand-input/30">
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(s.id)}
                            onChange={() => toggleSelect(s.id)}
                          />
                        </td>
                        <td className="px-3 py-2 text-gray-300 font-mono text-xs">{s.key}</td>
                        <td className="px-3 py-2 text-accent font-mono text-xs break-all">{s.value}</td>
                        <td className="px-3 py-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${kind.color}`}>
                            {kind.label}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <button onClick={() => setEditingShortcut(s)} className="text-xs text-accent hover:underline mr-2">
                            Düzenle
                          </button>
                          <button onClick={() => handleDelete(s)} className="text-xs text-red-400 hover:underline">
                            Sil
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table></div>
            </div>
          )}
        </>
      )}

      {showAddDialog && (
        <ShortcutDialog
          storeId={selectedStore}
          onClose={() => setShowAddDialog(false)}
          onSaved={() => { setShowAddDialog(false); reload() }}
        />
      )}

      {editingShortcut && (
        <ShortcutDialog
          storeId={selectedStore}
          shortcut={editingShortcut}
          onClose={() => setEditingShortcut(null)}
          onSaved={() => { setEditingShortcut(null); reload() }}
        />
      )}

      {showImportDialog && (
        <ImportDialog
          storeId={selectedStore}
          onClose={() => setShowImportDialog(false)}
          onImported={() => { setShowImportDialog(false); reload() }}
        />
      )}
    </div>
  )
}


function ShortcutDialog({ storeId, shortcut, onClose, onSaved }) {
  const isEdit = !!shortcut
  const [key, setKey] = useState(shortcut?.key || '')
  const [value, setValue] = useState(shortcut?.value || '')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      if (isEdit) {
        await api.patch(`/api/shortcuts/${shortcut.id}`, { key, value })
      } else {
        await api.post('/api/shortcuts', { store_id: storeId, key, value })
      }
      onSaved()
    } catch (err) {
      setError(err.detail || 'Kaydedilemedi')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl p-5 w-full max-w-md">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">
          {isEdit ? 'Kısayolu Düzenle' : 'Yeni Kısayol'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Anahtar (tasarım adı)</label>
            <input
              type="text"
              required
              autoFocus={!isEdit}
              value={key}
              onChange={e => setKey(e.target.value)}
              className="input w-full"
              placeholder="örn: redline apex"
            />
            <p className="text-[10px] text-gray-600 mt-1">Otomatik normalize edilir (küçük harf, boşluk temizliği).</p>
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Değer (kod)</label>
            <input
              type="text"
              required
              value={value}
              onChange={e => setValue(e.target.value)}
              className="input w-full font-mono"
              placeholder="B580 / B580|siyah / COUPLE::... / VARIANT::..."
            />
            <p className="text-[10px] text-gray-600 mt-1">
              Formatlar: <code>B580</code>, <code>B580|siyah</code>,
              <code>COUPLE::d1|siyah::d2|beyaz</code>,
              <code>VARIANT::opsiyon::kod</code>
            </p>
          </div>

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">İptal</button>
            <button type="submit" disabled={saving} className="btn-primary flex-1">
              {saving ? 'Kaydediliyor...' : 'Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


function ImportDialog({ storeId, onClose, onImported }) {
  const fileInputRef = useRef(null)
  const [jsonText, setJsonText] = useState('')
  const [mode, setMode] = useState('merge')
  const [error, setError] = useState('')
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState(null)

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      setJsonText(text)
    } catch (err) {
      setError('Dosya okunamadı: ' + err.message)
    }
  }

  const handleImport = async () => {
    setError('')
    setResult(null)
    let data
    try {
      data = JSON.parse(jsonText)
    } catch (err) {
      setError('Geçersiz JSON: ' + err.message)
      return
    }
    if (typeof data !== 'object' || Array.isArray(data) || data === null) {
      setError('JSON bir nesne (object) olmalı, örn: { "key": "value", ... }')
      return
    }

    setImporting(true)
    try {
      const r = await api.post('/api/shortcuts/import', { store_id: storeId, data, mode })
      setResult(r)
    } catch (err) {
      setError(err.detail || 'Import başarısız')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
         onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl p-5 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-gray-100 mb-1">Kısayol JSON İçe Aktar</h2>
        <p className="text-xs text-gray-500 mb-4">
          BERNZ formatından kısayolları toplu yükle. <code>_</code> ile başlayan key'ler atlanır.
        </p>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Mod</label>
            <div className="flex gap-2">
              <ModeOption value="merge" current={mode} onChange={setMode}
                label="Birleştir" hint="Mevcutları korur, yenileri ekler" />
              <ModeOption value="replace" current={mode} onChange={setMode}
                label="Değiştir" hint="⚠ Mevcut hepsini siler, sonra ekler" />
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">JSON içerik</label>
            <div className="flex gap-2 mb-2">
              <input ref={fileInputRef} type="file" accept=".json" onChange={handleFileSelect} className="hidden" />
              <button type="button" onClick={() => fileInputRef.current?.click()}
                className="btn-secondary !text-xs">📁 Dosya seç</button>
              <button type="button" onClick={() => setJsonText('')}
                className="btn-secondary !text-xs">Temizle</button>
            </div>
            <textarea
              value={jsonText}
              onChange={e => setJsonText(e.target.value)}
              className="input w-full font-mono !text-xs"
              rows={12}
              placeholder='{ "redline apex": "B580", "silverstone machine": "B593" }'
            />
          </div>

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {result && (
            <div className="text-xs bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2 text-emerald-300">
              ✓ {result.message}<br />
              Mağazada toplam: <strong>{result.total_after}</strong> kısayol
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Kapat</button>
            {!result && (
              <button onClick={handleImport} disabled={!jsonText.trim() || importing}
                className="btn-primary flex-1">
                {importing ? 'Yükleniyor...' : '📥 İçe Aktar'}
              </button>
            )}
            {result && (
              <button onClick={onImported} className="btn-primary flex-1">Tamam</button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


function ModeOption({ value, current, onChange, label, hint }) {
  const active = current === value
  return (
    <button
      type="button"
      onClick={() => onChange(value)}
      className={`flex-1 px-3 py-2 rounded-lg border text-left transition-colors ${
        active
          ? 'bg-accent/15 border-accent/50 text-accent'
          : 'bg-brand-input border-brand-border text-gray-300 hover:border-gray-600'
      }`}
    >
      <div className="text-sm font-medium">{label}</div>
      <div className="text-[10px] opacity-70 mt-0.5">{hint}</div>
    </button>
  )
}
