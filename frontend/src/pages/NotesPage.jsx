import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

export default function NotesPage() {
  const toast = useToast()
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [selId, setSelId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(false)
  const [search, setSearch] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [manualDraft, setManualDraft] = useState('')

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
    if (!selId) { setDetail(null); return }
    api.get(`/api/notes/${selId}`).then(d => {
      setDetail(d)
      setManualDraft(d.manual_content || '')
      setEditMode(false)
    }).catch(() => toast.error('Not acilamadi'))
  }, [selId])

  const refresh = async () => {
    setBusy(true)
    try {
      const r = await api.post('/api/notes/refresh', {})
      toast.success(`Notlar guncellendi (${r.guncellenen} guncel, ${r.olusturulan} yeni)`)
      await load()
      if (selId) { const d = await api.get(`/api/notes/${selId}`); setDetail(d) }
    } catch (e) {
      toast.error('Yenileme basarisiz')
    } finally { setBusy(false) }
  }

  const saveManual = async () => {
    try {
      const d = await api.patch(`/api/notes/${selId}`, { manual_content: manualDraft })
      setDetail(d); setEditMode(false)
      toast.success('Not kaydedildi')
    } catch (e) { toast.error('Kaydedilemedi') }
  }

  const togglePin = async (n) => {
    try {
      await api.patch(`/api/notes/${n.id}`, { pinned: !n.pinned })
      await load()
    } catch (e) { toast.error('Guncellenemedi') }
  }

  const addSerbest = async () => {
    const baslik = prompt('Yeni not basligi:')
    if (!baslik) return
    try {
      const d = await api.post('/api/notes', { baslik })
      await load(); setSelId(d.id)
      toast.success('Not olusturuldu')
    } catch (e) { toast.error('Olusturulamadi') }
  }

  const delSerbest = async (n) => {
    if (!confirm(`"${n.baslik}" silinsin mi?`)) return
    try {
      await api.del(`/api/notes/${n.id}`)
      await load(); if (selId === n.id) setSelId(null)
      toast.success('Not silindi')
    } catch (e) { toast.error(e?.detail || 'Silinemedi') }
  }

  const filtered = useMemo(() => {
    if (!search) return notes
    const q = search.toLowerCase()
    return notes.filter(n => (n.baslik || '').toLowerCase().includes(q))
  }, [notes, search])

  // Notlari grupla: acik / gonderilmis / serbest
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
      {/* Sol panel: not listesi */}
      <aside className="w-72 shrink-0 border-r border-brand-border flex flex-col bg-brand-bg/40">
        <div className="p-3 border-b border-brand-border space-y-2">
          <div className="flex items-center justify-between">
            <h1 className="text-sm font-semibold text-gray-100">📝 Notlar</h1>
            <div className="flex gap-1">
              <button onClick={refresh} disabled={busy}
                className="text-xs px-2 py-1 rounded bg-accent/15 text-accent hover:bg-accent/25 disabled:opacity-50"
                title="Siparislerden yenile">{busy ? '...' : '🔄'}</button>
              <button onClick={addSerbest}
                className="text-xs px-2 py-1 rounded bg-brand-input text-gray-300 hover:text-gray-100"
                title="Yeni serbest not">➕</button>
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
              Hic not yok. "🔄" ile siparislerden otomatik not olustur.
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

      {/* Sag panel: not icerigi */}
      <main className="flex-1 overflow-y-auto">
        {!detail ? (
          <div className="h-full flex items-center justify-center text-gray-600 text-sm">Bir not sec</div>
        ) : (
          <div className="p-5 max-w-3xl">
            <div className="flex items-start justify-between mb-4 gap-3">
              <div>
                <h2 className="text-lg font-semibold text-gray-100">{detail.baslik}</h2>
                {detail.updated_at && (
                  <p className="text-[11px] text-gray-500 mt-0.5">
                    Guncelleme: {new Date(detail.updated_at).toLocaleString('tr-TR')}
                    {detail.siparis_sayisi != null && ` · ${(detail.auto_content?.siparis_sayisi ?? 0)} siparis`}
                  </p>
                )}
              </div>
              {!detail.is_serbest && (
                <button onClick={() => setEditMode(m => !m)}
                  className="text-xs px-2.5 py-1 rounded bg-brand-input text-gray-300 hover:text-gray-100 shrink-0">
                  {editMode ? 'Vazgec' : '✏️ Elle Not Ekle'}
                </button>
              )}
            </div>

            {/* Otomatik icerik (siparisler) */}
            {detail.auto_content?.gunler?.length > 0 && (
              <div className="space-y-5 mb-6">
                {detail.auto_content.gunler.map((gun, gi) => (
                  <div key={gi}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-base">📅</span>
                      <span className="font-bold text-gray-100">{gun.tarih}</span>
                    </div>
                    <div className="space-y-3 pl-1">
                      {gun.siparisler.map((sip, si) => (
                        <SiparisBlok key={si} sip={sip} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {detail.is_serbest && !detail.auto_content?.gunler?.length && !editMode && (
              <div className="whitespace-pre-wrap text-sm text-gray-300 leading-relaxed mb-4">
                {detail.manual_content || <span className="text-gray-600">Bos not. Duzenlemek icin asagidan yaz.</span>}
              </div>
            )}

            {/* Elle eklenen not (manual_content) */}
            {!detail.is_serbest && detail.manual_content && !editMode && (
              <div className="border-t border-brand-border pt-4 mt-4">
                <p className="text-[11px] text-gray-500 mb-2 uppercase tracking-wide">Elle Eklenen Not</p>
                <div className="whitespace-pre-wrap text-sm text-gray-300 leading-relaxed">{detail.manual_content}</div>
              </div>
            )}

            {(editMode || (detail.is_serbest && !detail.auto_content?.gunler?.length)) && (
              <div className="border-t border-brand-border pt-4 mt-4">
                <textarea value={manualDraft} onChange={e => setManualDraft(e.target.value)}
                  rows={8} placeholder="Elle not ekle..."
                  className="input w-full !text-sm font-mono leading-relaxed" />
                <div className="flex justify-end gap-2 mt-2">
                  <button onClick={saveManual} className="btn-primary !text-sm">Kaydet</button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
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
          <div key={n.id}
            onClick={() => onSel(n.id)}
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
                className="text-[10px] px-1 hover:text-amber-400" title="Sabitle">📌</button>
              {onDel && (
                <button onClick={(e) => { e.stopPropagation(); onDel(n) }}
                  className="text-[10px] px-1 hover:text-red-400" title="Sil">🗑</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function SiparisBlok({ sip }) {
  return (
    <div className="text-sm">
      <div className="text-gray-100 font-medium mb-1">
        {sip.order_number} - {sip.musteri} - {sip.toplam} ADET
        {sip.not && <span className="text-amber-300/80 font-normal"> ({sip.not})</span>}
      </div>
      <div className="space-y-0.5 pl-1">
        {sip.kalemler.map((k, ki) => (
          <div key={ki} className="flex items-center gap-1.5 text-[13px]">
            <span className={`shrink-0 ${k.kaliba_eklendi ? 'text-emerald-400' : 'text-gray-600'}`}>
              {k.kaliba_eklendi ? '☑' : '☐'}
            </span>
            <span className="text-gray-400">{k.sira} -</span>
            <span className="text-gray-200">{k.model}</span>
            {k.tasarim && <span className="text-accent">"{k.tasarim}"</span>}
            {k.kalip_kodu ? (
              <span className="text-gray-400">-{k.kalip_kodu}</span>
            ) : (
              <span className="text-[11px] text-gray-600 italic">(henuz kaliba eklenmedi)</span>
            )}
            {k.hazir && <span className="text-emerald-400">✅</span>}
            {k.uyari && <span className="text-[11px] text-amber-500/80" title={k.uyari}>⚠</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
