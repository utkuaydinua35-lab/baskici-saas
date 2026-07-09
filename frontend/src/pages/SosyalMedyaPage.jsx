import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

const STATUS = [
  { key: 'taslak', label: 'Taslak', color: 'bg-amber-500/15 text-amber-300' },
  { key: 'onaylandi', label: 'Onaylı', color: 'bg-emerald-500/15 text-emerald-300' },
  { key: 'paylasildi', label: 'Paylaşıldı', color: 'bg-sky-500/15 text-sky-300' },
  { key: 'red', label: 'Reddedildi', color: 'bg-red-500/15 text-red-300' },
]
const MONTHS = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
const WD = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']

export default function SosyalMedyaPage() {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [handle, setHandle] = useState('')
  const [view, setView] = useState('kuyruk')   // kuyruk | takvim
  const [posts, setPosts] = useState([])
  const [tab, setTab] = useState('taslak')
  const [composer, setComposer] = useState(null)   // {date, kind} | null
  const store = stores.find(s => String(s.id) === String(storeId))

  const loadStores = async () => {
    try { const r = await api.get('/api/instagram/stores'); setStores(r.items || []); if (!storeId && r.items?.length) setStoreId(String(r.items[0].id)) }
    catch { toast.error('Mağazalar yüklenemedi') }
  }
  const loadPosts = async () => {
    if (!storeId) return
    try { const r = await api.get(`/api/instagram/posts?store_id=${storeId}&status=${tab}`); setPosts(r.items || []) }
    catch { setPosts([]) }
  }
  useEffect(() => { loadStores() }, [])
  useEffect(() => { if (storeId) { loadPosts(); setHandle(store?.instagram_handle || '') } }, [storeId])
  useEffect(() => { loadPosts() }, [tab, storeId])

  const saveHandle = async () => {
    try { await api.patch('/api/instagram/stores/handle', { store_id: storeId, handle }); toast.success('Instagram hesabı kaydedildi'); loadStores() }
    catch (e) { toast.error(e?.detail || 'Kaydedilemedi') }
  }
  const setStatus = async (p, status) => {
    try { await api.patch(`/api/instagram/posts/${p.id}`, { status }); loadPosts() }
    catch (e) { toast.error(e?.detail || 'Güncellenemedi') }
  }
  const saveEdit = async (p, caption, hashtags) => {
    try { await api.patch(`/api/instagram/posts/${p.id}`, { caption, hashtags }); toast.success('Kaydedildi'); loadPosts() }
    catch (e) { toast.error(e?.detail || 'Kaydedilemedi') }
  }
  const del = async (p) => {
    if (!confirm('Bu gönderi silinsin mi?')) return
    try { await api.del(`/api/instagram/posts/${p.id}`); loadPosts() }
    catch { toast.error('Silinemedi') }
  }

  return (
    <div className="mx-auto max-w-5xl animate-fadein">
      <div className="mb-5 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">📸 Sosyal Medya Planlama</h1>
          <p className="text-sm text-gray-500 mt-1">Görsel + açıklama gir, takvime planla, onayla, paylaş.</p>
        </div>
        <button onClick={() => setComposer({ date: null, kind: 'post' })} className="btn-primary !text-sm">+ Yeni Gönderi</button>
      </div>

      {/* Marka + IG hesap */}
      <div className="card mb-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Marka / Profil</label>
          <select className="input" value={storeId} onChange={e => setStoreId(e.target.value)}>
            {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div className="flex-1 min-w-[180px]">
          <label className="block text-xs text-gray-500 mb-1">Instagram hesabı (@)</label>
          <div className="flex gap-2">
            <input className="input flex-1" placeholder="orn: bernzcases" value={handle} onChange={e => setHandle(e.target.value.trim().replace(/^@/, ''))} />
            <button onClick={saveHandle} className="btn-secondary !text-sm">Kaydet</button>
          </div>
          {store?.instagram_handle && <p className="text-[10px] text-gray-600 mt-1"><a href={`https://instagram.com/${store.instagram_handle}`} target="_blank" rel="noreferrer" className="text-accent hover:underline">@{store.instagram_handle} aç ↗</a></p>}
        </div>
      </div>

      {/* Görünüm */}
      <div className="flex gap-2 mb-4">
        <button onClick={() => setView('kuyruk')} className={`px-3 py-1.5 rounded-lg text-sm ${view === 'kuyruk' ? 'bg-accent/15 text-accent border border-accent/40' : 'btn-secondary'}`}>📋 Kuyruk</button>
        <button onClick={() => setView('takvim')} className={`px-3 py-1.5 rounded-lg text-sm ${view === 'takvim' ? 'bg-accent/15 text-accent border border-accent/40' : 'btn-secondary'}`}>📅 Takvim</button>
      </div>

      {view === 'kuyruk' && <>
        <div className="flex gap-1 border-b border-brand-border mb-4">
          {STATUS.map(s => (
            <button key={s.key} onClick={() => setTab(s.key)} className={`px-3 py-2 text-sm border-b-2 -mb-px ${tab === s.key ? 'border-accent text-accent' : 'border-transparent text-gray-400 hover:text-gray-200'}`}>{s.label}</button>
          ))}
        </div>
        {posts.length === 0 ? (
          <div className="card text-center py-10 text-gray-500 text-sm">Bu durumda gönderi yok. "+ Yeni Gönderi" ile ekle.</div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {posts.map(p => <PostCard key={p.id} post={p} onStatus={setStatus} onSave={saveEdit} onDelete={del} toast={toast} />)}
          </div>
        )}
      </>}

      {view === 'takvim' && <CalendarView storeId={storeId} toast={toast} onAddDay={(d) => setComposer({ date: d, kind: 'post' })} />}

      {composer && (
        <Composer storeId={storeId} initial={composer} toast={toast}
          onClose={() => setComposer(null)}
          onCreated={() => { setComposer(null); if (view === 'kuyruk') { setTab('taslak'); loadPosts() } }} />
      )}
    </div>
  )
}

// ─── Manuel gönderi oluşturucu ───────────────────────────────
function Composer({ storeId, initial, toast, onClose, onCreated }) {
  const [kind, setKind] = useState(initial.kind || 'post')
  const [caption, setCaption] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [date, setDate] = useState(initial.date || '')
  const [img, setImg] = useState(null)   // {path,url}
  const [busy, setBusy] = useState(false)

  const upload = async (e) => {
    const f = (e.target.files || [])[0]; e.target.value = ''
    if (!f) return
    try { const fd = new FormData(); fd.append('file', f); const r = await api.postForm('/api/instagram/upload', fd); setImg({ path: r.path, url: r.url }) }
    catch { toast.error('Görsel yüklenemedi') }
  }
  const isStory = kind === 'story'
  const save = async () => {
    if (!storeId) { toast.error('Önce marka seç'); return }
    if (isStory) { if (!img) { toast.error('Story için görsel gerekli'); return } }
    else if (!img && !caption.trim()) { toast.error('En az bir görsel ya da açıklama gir'); return }
    setBusy(true)
    try {
      await api.post('/api/instagram/draft', {
        store_id: storeId, caption, hashtags: hashtags || null, kind,
        image_path: img?.path || null,
        scheduled_for: date ? new Date(date + 'T09:00:00').toISOString() : null,
      })
      toast.success('Gönderi eklendi ✓')
      onCreated()
    } catch (e) { toast.error(e?.detail || 'Eklenemedi') }
    finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] bg-black/60 flex items-center justify-center p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-2xl w-full max-w-lg p-5 my-8">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-100">Yeni Gönderi</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-xl">×</button>
        </div>

        <label className="block text-xs text-gray-500 mb-1">Görsel</label>
        {img
          ? <div className="relative w-full aspect-square rounded-lg overflow-hidden mb-3 bg-brand-input"><img src={img.url} alt="" className="w-full h-full object-cover" /><button onClick={() => setImg(null)} className="absolute top-2 right-2 bg-red-500 text-white rounded-full w-6 h-6">×</button></div>
          : <label className="block w-full aspect-square rounded-lg border-2 border-dashed border-brand-border mb-3 flex items-center justify-center text-gray-500 text-sm cursor-pointer hover:border-accent/40">📎 Görsel yükle<input type="file" accept="image/*" className="hidden" onChange={upload} /></label>}

        <div className="flex gap-2 mb-3">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Tür</label>
            <select className="input w-full" value={kind} onChange={e => setKind(e.target.value)}>
              <option value="post">Gönderi</option>
              <option value="story">Story</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Takvim günü (ops.)</label>
            <input type="date" className="input w-full" value={date || ''} onChange={e => setDate(e.target.value)} />
          </div>
        </div>

        {isStory ? (
          <p className="text-[11px] text-gray-500 mb-4">Story için yalnızca görsel yeterli — açıklama/hashtag istenmez.</p>
        ) : (
          <>
            <label className="block text-xs text-gray-500 mb-1">Açıklama</label>
            <textarea className="input w-full mb-2 !text-sm" rows={4} placeholder="Gönderi açıklaması…" value={caption} onChange={e => setCaption(e.target.value)} />
            <label className="block text-xs text-gray-500 mb-1">Hashtag</label>
            <input className="input w-full mb-4 !text-sm" placeholder="#kilif #tasarim" value={hashtags} onChange={e => setHashtags(e.target.value)} />
          </>
        )}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary !text-sm">Vazgeç</button>
          <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? 'Ekleniyor…' : 'Ekle'}</button>
        </div>
      </div>
    </div>
  )
}

// ─── Takvim (aya göre; görselin üstüne 1sn gelince büyür) ─────
function CalendarView({ storeId, toast, onAddDay }) {
  const today = new Date()
  const [ym, setYm] = useState({ y: today.getFullYear(), m: today.getMonth() + 1 })
  const [days, setDays] = useState({})

  const load = async () => {
    if (!storeId) return
    try { const r = await api.get(`/api/instagram/calendar?store_id=${storeId}&year=${ym.y}&month=${ym.m}`); setDays(r.days || {}) }
    catch { setDays({}) }
  }
  useEffect(() => { load() }, [storeId, ym.y, ym.m])

  const first = new Date(ym.y, ym.m - 1, 1)
  const startWd = (first.getDay() + 6) % 7   // Pzt=0
  const daysInMonth = new Date(ym.y, ym.m, 0).getDate()
  const cells = []
  for (let i = 0; i < startWd; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  const prev = () => setYm(v => v.m === 1 ? { y: v.y - 1, m: 12 } : { y: v.y, m: v.m - 1 })
  const next = () => setYm(v => v.m === 12 ? { y: v.y + 1, m: 1 } : { y: v.y, m: v.m + 1 })
  const key = (d) => `${ym.y}-${String(ym.m).padStart(2, '0')}-${String(d).padStart(2, '0')}`

  return (
    <div className="card !p-3">
      <style>{`.ig-cal-thumb{transition:transform .3s ease 0s}.ig-cal-thumb:hover{transform:scale(2.1);transition-delay:1s;z-index:40;position:relative;box-shadow:0 8px 30px rgba(0,0,0,.6)}`}</style>
      <div className="flex items-center justify-between mb-3">
        <button onClick={prev} className="btn-secondary !text-sm">‹</button>
        <div className="text-sm font-semibold text-gray-200">{MONTHS[ym.m - 1]} {ym.y}</div>
        <button onClick={next} className="btn-secondary !text-sm">›</button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-[10px] text-gray-500 mb-1">
        {WD.map(w => <div key={w}>{w}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-1" style={{ overflow: 'visible' }}>
        {cells.map((d, i) => {
          if (!d) return <div key={i} />
          const items = days[key(d)] || []
          const isToday = ym.y === today.getFullYear() && ym.m === today.getMonth() + 1 && d === today.getDate()
          return (
            <div key={i} className={`min-h-[78px] rounded-lg border p-1 ${isToday ? 'border-accent/50 bg-accent/5' : 'border-brand-border bg-brand-input/20'}`} style={{ overflow: 'visible', position: 'relative' }}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-gray-400">{d}</span>
                <button onClick={() => onAddDay(key(d))} className="text-[11px] text-accent hover:text-accent/70" title="Bu güne gönderi ekle">＋</button>
              </div>
              <div className="flex flex-wrap gap-0.5 mt-0.5">
                {items.slice(0, 6).map(p => (
                  p.image_url
                    ? <img key={p.id} src={p.image_url} alt="" title={`${p.kind === 'story' ? 'Story' : 'Post'}: ${(p.caption || '').slice(0, 60)}`} className="ig-cal-thumb w-7 h-7 rounded object-cover cursor-pointer" />
                    : <div key={p.id} className="w-7 h-7 rounded bg-brand-input flex items-center justify-center text-[8px] text-gray-500" title={(p.caption || '').slice(0, 60)}>{p.kind === 'story' ? 'S' : 'P'}</div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
      <p className="text-[10px] text-gray-600 mt-2">Bir görselin üstüne gelip 1 saniye bekle → büyür. ＋ ile o güne gönderi ekle.</p>
    </div>
  )
}

// ─── Kuyruk kartı ─────────────────────────────────────────────
function PostCard({ post, onStatus, onSave, onDelete, toast }) {
  const [caption, setCaption] = useState(post.caption || '')
  const [hashtags, setHashtags] = useState(post.hashtags || '')
  const [edit, setEdit] = useState(false)
  const copyAll = () => {
    const text = `${caption}\n\n${hashtags}`.trim()
    navigator.clipboard?.writeText(text).then(() => toast.success('Metin kopyalandı'), () => toast.error('Kopyalanamadı'))
  }
  return (
    <div className="card !p-0 overflow-hidden flex flex-col">
      {post.image_url
        ? <img src={post.image_url} alt="" className="w-full aspect-square object-cover bg-brand-input" />
        : <div className="w-full aspect-square bg-brand-input flex items-center justify-center text-gray-600 text-sm">Görsel yok</div>}
      <div className="p-3 flex-1 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-brand-input text-gray-400">{post.kind === 'story' ? 'Story' : 'Gönderi'}</span>
          {post.scheduled_for && <span className="text-gray-500">📅 {new Date(post.scheduled_for).toLocaleDateString('tr-TR')}</span>}
        </div>
        {edit ? (
          <>
            <textarea className="input w-full !text-sm" rows={4} value={caption} onChange={e => setCaption(e.target.value)} />
            <input className="input w-full !text-sm" value={hashtags} onChange={e => setHashtags(e.target.value)} />
            <div className="flex gap-2">
              <button onClick={() => { onSave(post, caption, hashtags); setEdit(false) }} className="btn-primary !text-xs">Kaydet</button>
              <button onClick={() => { setCaption(post.caption || ''); setHashtags(post.hashtags || ''); setEdit(false) }} className="btn-secondary !text-xs">Vazgeç</button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-gray-200 whitespace-pre-wrap">{post.caption}</p>
            <p className="text-xs text-accent">{post.hashtags}</p>
          </>
        )}
        <div className="mt-auto pt-2 flex flex-wrap gap-1.5">
          {post.status === 'taslak' && <>
            <button onClick={() => onStatus(post, 'onaylandi')} className="text-[11px] px-2 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10">✓ Onayla</button>
            <button onClick={() => onStatus(post, 'red')} className="text-[11px] px-2 py-1 rounded border border-red-500/40 text-red-300 hover:bg-red-500/10">Reddet</button>
          </>}
          {post.status === 'onaylandi' && <button onClick={() => onStatus(post, 'paylasildi')} className="text-[11px] px-2 py-1 rounded border border-sky-500/40 text-sky-300 hover:bg-sky-500/10">Paylaşıldı ✓</button>}
          <button onClick={copyAll} className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-300 hover:bg-brand-input">📋 Metni kopyala</button>
          {post.image_url && <a href={post.image_url} download target="_blank" rel="noreferrer" className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-300 hover:bg-brand-input">⬇ Görsel</a>}
          {!edit && <button onClick={() => setEdit(true)} className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-300 hover:bg-brand-input">Düzenle</button>}
          <button onClick={() => onDelete(post)} className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-500 hover:text-red-300">Sil</button>
        </div>
      </div>
    </div>
  )
}
