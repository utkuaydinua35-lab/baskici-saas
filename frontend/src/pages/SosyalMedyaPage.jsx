import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

const STATUS = [
  { key: 'taslak', label: 'Taslak', color: 'bg-amber-500/15 text-amber-300' },
  { key: 'onaylandi', label: 'Onaylı', color: 'bg-emerald-500/15 text-emerald-300' },
  { key: 'paylasildi', label: 'Paylaşıldı', color: 'bg-sky-500/15 text-sky-300' },
  { key: 'red', label: 'Reddedildi', color: 'bg-red-500/15 text-red-300' },
]

export default function SosyalMedyaPage() {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [designs, setDesigns] = useState([])
  const [designId, setDesignId] = useState('')
  const [kind, setKind] = useState('post')
  const [posts, setPosts] = useState([])
  const [tab, setTab] = useState('taslak')
  const [busy, setBusy] = useState(false)
  const [handle, setHandle] = useState('')

  const store = stores.find(s => String(s.id) === String(storeId))

  const loadStores = async () => {
    try {
      const r = await api.get('/api/instagram/stores')
      setStores(r.items || [])
      if (!storeId && r.items?.length) setStoreId(String(r.items[0].id))
    } catch { toast.error('Mağazalar yüklenemedi') }
  }
  const loadDesigns = async (sid) => {
    if (!sid) return
    try {
      const d = await api.get(`/api/designs?store_id=${sid}&per_page=200`)
      setDesigns(Array.isArray(d) ? d : (d?.items || []))
    } catch { setDesigns([]) }
  }
  const loadPosts = async () => {
    if (!storeId) return
    try {
      const r = await api.get(`/api/instagram/posts?store_id=${storeId}&status=${tab}`)
      setPosts(r.items || [])
    } catch { setPosts([]) }
  }

  useEffect(() => { loadStores() }, [])
  useEffect(() => { if (storeId) { loadDesigns(storeId); loadPosts(); setHandle(store?.instagram_handle || '') } }, [storeId])
  useEffect(() => { loadPosts() }, [tab, storeId])

  const saveHandle = async () => {
    try {
      await api.patch('/api/instagram/stores/handle', { store_id: storeId, handle })
      toast.success('Instagram hesabı kaydedildi')
      loadStores()
    } catch (e) { toast.error(e?.detail || 'Kaydedilemedi') }
  }

  const generate = async () => {
    if (!storeId) return
    setBusy(true)
    try {
      await api.post('/api/instagram/generate', { store_id: storeId, design_id: designId || null, kind, style: 'mockup' })
      toast.success('Taslak üretildi')
      setTab('taslak'); loadPosts()
    } catch (e) { toast.error(e?.detail || 'Üretilemedi') }
    finally { setBusy(false) }
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
    if (!confirm('Bu taslak silinsin mi?')) return
    try { await api.del(`/api/instagram/posts/${p.id}`); loadPosts() }
    catch (e) { toast.error('Silinemedi') }
  }

  return (
    <div className="mx-auto max-w-5xl animate-fadein">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">📸 Sosyal Medya</h1>
        <p className="text-sm text-gray-500 mt-1">Instagram gönderi taslakları — AI üretir, sen onaylar paylaşırsın.</p>
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
            <input className="input flex-1" placeholder="orn: bernzcompany" value={handle}
              onChange={e => setHandle(e.target.value)} />
            <button onClick={saveHandle} className="btn-secondary !text-sm">Kaydet</button>
          </div>
        </div>
      </div>

      {/* Taslak üret */}
      <div className="card mb-4">
        <h3 className="text-sm font-semibold text-gray-200 mb-2">Yeni taslak üret</h3>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-gray-500 mb-1">Tasarım (ops.)</label>
            <select className="input w-full" value={designId} onChange={e => setDesignId(e.target.value)}>
              <option value="">— Tasarım seç —</option>
              {designs.map(d => <option key={d.id} value={d.id}>{d.name || d.code}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Tür</label>
            <select className="input" value={kind} onChange={e => setKind(e.target.value)}>
              <option value="post">Gönderi</option>
              <option value="story">Story</option>
            </select>
          </div>
          <button onClick={generate} disabled={busy} className="btn-primary !text-sm">
            {busy ? 'Üretiliyor…' : '✨ Taslak Üret'}
          </button>
        </div>
        <p className="text-[11px] text-gray-600 mt-2">
          Görsel şu an tasarımın mockup'ı; "müşteriden çekilmiş gibi" (UGC) görsel üretimi örnek görsellerin ile eklenecek.
        </p>
      </div>

      {/* Durum sekmeleri */}
      <div className="flex gap-1 border-b border-brand-border mb-4">
        {STATUS.map(s => (
          <button key={s.key} onClick={() => setTab(s.key)}
            className={`px-3 py-2 text-sm border-b-2 -mb-px ${tab === s.key ? 'border-accent text-accent' : 'border-transparent text-gray-400 hover:text-gray-200'}`}>
            {s.label}
          </button>
        ))}
      </div>

      {/* Kuyruk */}
      {posts.length === 0 ? (
        <div className="card text-center py-10 text-gray-500 text-sm">Bu durumda gönderi yok.</div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {posts.map(p => <PostCard key={p.id} post={p} onStatus={setStatus} onSave={saveEdit} onDelete={del} toast={toast} />)}
        </div>
      )}
    </div>
  )
}

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
          {post.status === 'onaylandi' && <>
            <button onClick={() => onStatus(post, 'paylasildi')} className="text-[11px] px-2 py-1 rounded border border-sky-500/40 text-sky-300 hover:bg-sky-500/10">Paylaşıldı ✓</button>
          </>}
          <button onClick={copyAll} className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-300 hover:bg-brand-input">📋 Metni kopyala</button>
          {post.image_url && <a href={post.image_url} download target="_blank" rel="noreferrer" className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-300 hover:bg-brand-input">⬇ Görsel</a>}
          {!edit && <button onClick={() => setEdit(true)} className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-300 hover:bg-brand-input">Düzenle</button>}
          <button onClick={() => onDelete(post)} className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-500 hover:text-red-300">Sil</button>
        </div>
      </div>
    </div>
  )
}
