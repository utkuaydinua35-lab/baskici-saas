import { useState, useEffect, useMemo, useRef } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

// APPLE_NOTES_LINE_EDITOR — satir-tabanli checklist editoru
export default function NotesPage() {
  const toast = useToast()
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [selId, setSelId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [lines, setLines] = useState([])
  const [busy, setBusy] = useState(false)
  const [search, setSearch] = useState('')
  const saveTimer = useRef(null)
  const inputRefs = useRef({})
  const [noteQuery, setNoteQuery] = useState('')
  const [activeMatch, setActiveMatch] = useState(0)

  const load = async () => {
    try {
      const r = await api.get('/api/notes')
      setNotes(r.items || [])
      if (!selId && r.items?.length) setSelId(r.items[0].id)
    } catch (e) {
      toast.error('Notlar yuklenemedi')
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!selId) { setDetail(null); setLines([]); return }
    api.get(`/api/notes/${selId}`).then(d => {
      setDetail(d)
      setLines(Array.isArray(d.lines) ? d.lines : [])
    }).catch(() => toast.error('Not acilamadi'))
  }, [selId])

  const refresh = async () => {
    setBusy(true)
    try {
      const r = await api.post('/api/notes/refresh', {})
      toast.success(`Notlar guncellendi (${r.guncellenen} guncel, ${r.olusturulan} yeni)`)
      await load()
      if (selId) { const d = await api.get(`/api/notes/${selId}`); setDetail(d); setLines(d.lines || []) }
    } catch (e) {
      toast.error('Yenileme basarisiz')
    } finally { setBusy(false) }
  }

  // Satirlari kaydet (debounce)
  const scheduleSave = (newLines) => {
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try {
        await api.patch(`/api/notes/${selId}/lines`, { lines: newLines })
      } catch (e) { /* sessiz */ }
    }, 800)
  }

  const updateLines = (newLines) => {
    setLines(newLines)
    scheduleSave(newLines)
  }

  // Checkbox: hazir/degil. Kalem satiriysa backend is_hazir senkron eder.
  const toggleCheck = async (idx) => {
    const nl = lines.map((l, i) => i === idx ? { ...l, checked: !l.checked } : l)
    setLines(nl)
    const line = nl[idx]
    try {
      if (line.key) {
        await api.patch(`/api/notes/${selId}/toggle-line`, { key: line.key, checked: line.checked })
      } else {
        scheduleSave(nl)
      }
    } catch (e) { toast.error('Guncellenemedi') }
  }

  // Satir metni degis
  const editText = (idx, text) => {
    updateLines(lines.map((l, i) => i === idx ? { ...l, text } : l))
  }

  // Enter -> yeni elle satir (idx'ten sonra)
  const addLineAfter = (idx) => {
    const newKey = `elle:${Date.now()}:${Math.random().toString(36).slice(2, 7)}`
    const nl = [...lines]
    nl.splice(idx + 1, 0, { key: newKey, text: '', checked: false, kind: 'elle', line_item_id: null, order_id: null, uyari: null })
    updateLines(nl)
    setTimeout(() => inputRefs.current[newKey]?.focus(), 30)
  }

  // Bos satirda Backspace -> sil + onceki satira odaklan
  const removeLine = (idx) => {
    if (lines.length <= 1) return
    const prev = lines[idx - 1]
    const nl = lines.filter((_, i) => i !== idx)
    updateLines(nl)
    if (prev?.key) setTimeout(() => {
      const el = inputRefs.current[prev.key]
      if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length) }
    }, 30)
  }

  const onKeyDown = (e, idx) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addLineAfter(idx)
    } else if (e.key === 'Backspace' && lines[idx].text === '') {
      e.preventDefault()
      removeLine(idx)
    }
  }

  const togglePin = async (n) => {
    try { await api.patch(`/api/notes/${n.id}`, { pinned: !n.pinned }); await load() }
    catch (e) { toast.error('Guncellenemedi') }
  }

  const addSerbest = async () => {
    const baslik = prompt('Yeni not basligi:')
    if (!baslik) return
    try { const d = await api.post('/api/notes', { baslik }); await load(); setSelId(d.id); toast.success('Not olusturuldu') }
    catch (e) { toast.error('Olusturulamadi') }
  }

  const delSerbest = async (n) => {
    if (!confirm(`"${n.baslik}" silinsin mi?`)) return
    try { await api.del(`/api/notes/${n.id}`); await load(); if (selId === n.id) setSelId(null); toast.success('Not silindi') }
    catch (e) { toast.error(e?.detail || 'Silinemedi') }
  }

  const matches = useMemo(() => {
    if (!noteQuery.trim()) return []
    const q = noteQuery.toLowerCase()
    return lines.map((l, i) => ((l.text || '').toLowerCase().includes(q) ? i : -1)).filter(i => i >= 0)
  }, [lines, noteQuery])

  useEffect(() => { setActiveMatch(0) }, [noteQuery, selId])

  // Aktif eslesmeye scroll
  useEffect(() => {
    if (matches.length && matches[activeMatch] != null) {
      const l = lines[matches[activeMatch]]
      const el = l?.key && inputRefs.current[l.key]
      if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [activeMatch, matches])

  const gotoMatch = (dir) => {
    if (!matches.length) return
    setActiveMatch(m => (m + dir + matches.length) % matches.length)
  }

  const filtered = useMemo(() => {
    if (!search) return notes
    const q = search.toLowerCase()
    return notes.filter(n => (n.baslik || '').toLowerCase().includes(q))
  }, [notes, search])

  const groups = useMemo(() => {
    const g = { acik: [], gonderilmis: [], serbest: [] }
    for (const n of filtered) {
      if (n.is_serbest) g.serbest.push(n)
      else if (n.note_type === 'gonderilmis') g.gonderilmis.push(n)
      else g.acik.push(n)
    }
    return g
  }, [filtered])

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-0 rounded-xl overflow-hidden border border-brand-border bg-brand-card">
      {/* Sol: not listesi */}
      <aside className="w-72 shrink-0 border-r border-brand-border flex flex-col bg-brand-bg/40">
        <div className="p-3 border-b border-brand-border space-y-2">
          <div className="flex items-center justify-between">
            <h1 className="text-sm font-semibold text-gray-100">Notlar</h1>
            <div className="flex gap-1">
              <button onClick={refresh} disabled={busy}
                className="text-xs px-2 py-1 rounded bg-accent/15 text-accent hover:bg-accent/25 disabled:opacity-50"
                title="Siparislerden yenile">{busy ? '...' : 'Yenile'}</button>
              <button onClick={addSerbest}
                className="text-xs px-2 py-1 rounded bg-brand-input text-gray-300 hover:text-gray-100"
                title="Yeni serbest not">+</button>
            </div>
          </div>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Not ara..." className="input w-full !text-xs" />
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-3">
          {loading ? (
            <div className="text-xs text-gray-500 text-center py-8">Yukleniyor...</div>
          ) : notes.length === 0 ? (
            <div className="text-xs text-gray-500 text-center py-8 px-3">
              Hic not yok. "Yenile" ile siparislerden otomatik not olustur.
            </div>
          ) : (
            <>
              <NoteGroup title="Acik Siparisler" items={groups.acik} selId={selId} onSel={setSelId} onPin={togglePin} />
              <NoteGroup title="Gonderilmis" items={groups.gonderilmis} selId={selId} onSel={setSelId} onPin={togglePin} />
              <NoteGroup title="Serbest Notlar" items={groups.serbest} selId={selId} onSel={setSelId} onPin={togglePin} onDel={delSerbest} />
            </>
          )}
        </div>
      </aside>

      {/* Sag: satir editoru */}
      <main className="flex-1 overflow-y-auto">
        {!detail ? (
          <div className="h-full flex items-center justify-center text-gray-600 text-sm">Bir not sec</div>
        ) : (
          <div className="p-5 max-w-3xl">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-gray-100">{detail.baslik}</h2>
              {detail.updated_at && (
                <p className="text-[11px] text-gray-500 mt-0.5">
                  Guncelleme: {new Date(detail.updated_at).toLocaleString('tr-TR')}
                </p>
              )}
              <div className="flex items-center gap-2 mt-2">
                <input
                  value={noteQuery}
                  onChange={e => setNoteQuery(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); gotoMatch(e.shiftKey ? -1 : 1) } }}
                  placeholder="Not icinde ara..."
                  className="input !text-xs !py-1 w-48" />
                {noteQuery.trim() && (
                  <div className="flex items-center gap-1 text-[11px] text-gray-400">
                    <span>{matches.length ? `${activeMatch + 1}/${matches.length}` : '0/0'}</span>
                    <button onClick={() => gotoMatch(-1)} disabled={!matches.length}
                      className="px-1.5 py-0.5 rounded bg-brand-input hover:text-gray-100 disabled:opacity-30" title="Onceki">↑</button>
                    <button onClick={() => gotoMatch(1)} disabled={!matches.length}
                      className="px-1.5 py-0.5 rounded bg-brand-input hover:text-gray-100 disabled:opacity-30" title="Sonraki">↓</button>
                    <button onClick={() => setNoteQuery('')}
                      className="px-1.5 py-0.5 rounded bg-brand-input hover:text-gray-100" title="Temizle">×</button>
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-0.5">
              {lines.length === 0 ? (
                <div onClick={() => addLineAfter(-1)}
                  className="text-sm text-gray-600 cursor-text py-2">Yazmaya basla...</div>
              ) : (
                lines.map((l, idx) => {
                  const mi = matches.indexOf(idx)
                  const isMatch = mi >= 0
                  const isActive = isMatch && mi === activeMatch
                  return (
                    <LineRow key={l.key || idx} line={l} idx={idx}
                      highlight={isActive ? 'active' : isMatch ? 'match' : null}
                      onToggle={toggleCheck} onEdit={editText} onKeyDown={onKeyDown}
                      inputRef={el => { if (l.key) inputRefs.current[l.key] = el }} />
                  )
                })
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

function LineRow({ line, idx, onToggle, onEdit, onKeyDown, inputRef, highlight }) {
  const isTarih = line.kind === 'tarih'
  const isSiparis = line.kind === 'siparis'
  const isAyrac = line.kind === 'ayrac'
  const taRef = useRef(null)

  // Auto-resize: icerik kadar yukseklik (uzun metin alt satira sarar)
  const autoSize = (el) => {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = el.scrollHeight + 'px'
  }
  useEffect(() => { autoSize(taRef.current) }, [line.text])

  // Ayrac (bos satir) — ince bosluk
  if (isAyrac && !line.text) {
    return <div className="h-2" />
  }
  const hlClass = highlight === 'active' ? 'bg-amber-400/30 rounded' : highlight === 'match' ? 'bg-amber-400/10 rounded' : ''
  return (
    <div className={`flex items-start gap-2 group ${hlClass}`}>
      <button onClick={() => onToggle(idx)}
        className={`mt-0.5 shrink-0 w-4 text-center cursor-pointer hover:scale-110 transition-transform ${line.checked ? 'text-emerald-400' : 'text-gray-600'}`}
        title={line.checked ? 'Isaretli (tikla: kaldir)' : 'Isaretle'}>
        {line.checked ? '\u2611' : '\u2610'}
      </button>
      {line.uyari && (
        <span className="mt-1 text-[11px] text-amber-500/80 shrink-0" title={line.uyari}>!</span>
      )}
      <textarea
        ref={el => { taRef.current = el; if (inputRef) inputRef(el) }}
        value={line.text}
        rows={1}
        onChange={e => { onEdit(idx, e.target.value); autoSize(e.target) }}
        onKeyDown={e => onKeyDown(e, idx)}
        className={`flex-1 min-w-0 bg-transparent border-none outline-none resize-none overflow-hidden text-sm leading-relaxed py-0.5 break-words
          ${isTarih ? 'font-bold text-gray-100' : isSiparis ? 'font-medium text-gray-100' : 'text-gray-300'}
          ${line.checked ? 'line-through text-gray-500' : ''}`} />
    </div>
  )
}

function NoteGroup({ title, items, selId, onSel, onPin, onDel }) {
  if (!items.length) return null
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-gray-600 px-2 mb-1">{title}</p>
      <div className="space-y-0.5">
        {items.map(n => (
          <div key={n.id} onClick={() => onSel(n.id)}
            className={`group px-2.5 py-2 rounded-lg cursor-pointer flex items-center justify-between gap-1 ${
              selId === n.id ? 'bg-accent/15 text-accent' : 'hover:bg-brand-input/60 text-gray-300'
            }`}>
            <div className="min-w-0">
              <div className="text-xs font-medium truncate flex items-center gap-1">
                {n.pinned && <span className="text-amber-400">📌</span>}
                {n.baslik}
              </div>
              {n.siparis_sayisi != null && !n.is_serbest && (
                <div className="text-[10px] text-gray-500">{n.siparis_sayisi} siparis</div>
              )}
            </div>
            <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 shrink-0">
              <button onClick={(e) => { e.stopPropagation(); onPin(n) }}
                className="text-xs px-1 hover:text-amber-400" title="Sabitle">📌</button>
              {onDel && (
                <button onClick={(e) => { e.stopPropagation(); onDel(n) }}
                  className="text-xs px-1 hover:text-red-400" title="Sil">🗑️</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
