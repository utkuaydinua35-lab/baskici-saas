import { useEffect, useState, useRef } from 'react'
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
  const [view, setView] = useState('sohbet')   // sohbet | uret
  const [persona, setPersona] = useState('')
  const [personaOpen, setPersonaOpen] = useState(false)
  const [hasPersona, setHasPersona] = useState(false)

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

  const loadPersona = async (sid) => {
    if (!sid) return
    try { const r = await api.get(`/api/instagram/persona?store_id=${sid}`); setPersona(r.persona || ''); setHasPersona(!!r.persona) }
    catch { setPersona(''); setHasPersona(false) }
  }

  useEffect(() => { loadStores() }, [])
  useEffect(() => { if (storeId) { loadDesigns(storeId); loadPosts(); loadPersona(storeId); setHandle(store?.instagram_handle || '') } }, [storeId])
  useEffect(() => { loadPosts() }, [tab, storeId])

  const saveHandle = async () => {
    try {
      await api.patch('/api/instagram/stores/handle', { store_id: storeId, handle })
      toast.success('Instagram hesabı kaydedildi')
      loadStores()
    } catch (e) { toast.error(e?.detail || 'Kaydedilemedi') }
  }

  const savePersona = async () => {
    try {
      const r = await api.patch('/api/instagram/persona', { store_id: storeId, persona })
      setHasPersona(r.has_persona)
      toast.success('Karakter kaydedildi — asistan artık bu persona')
    } catch (e) { toast.error(e?.detail || 'Kaydedilemedi') }
  }

  const generate = async () => {
    if (!storeId) return
    if (!designId) { toast.error('Önce bir tasarım seç (görsel bundan üretilir)'); return }
    setBusy(true)
    try {
      const r = await api.post('/api/instagram/generate', { store_id: storeId, design_id: designId, kind, style: 'mockup' })
      if (r && !r.image_url) toast.error('Metin üretildi ama görsel çıkmadı — bu tasarımın görseli açılamıyor olabilir, başka tasarım dene.')
      else toast.success('Taslak üretildi')
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
            <input className="input flex-1" placeholder="orn: bernzcases" value={handle}
              onChange={e => setHandle(e.target.value.trim().replace(/^@/, ''))} />
            <button onClick={saveHandle} className="btn-secondary !text-sm">Kaydet</button>
          </div>
          <p className="text-[10px] text-gray-600 mt-1">
            Bu markanın hangi hesaptan paylaşılacağını belirler.
            {store?.instagram_handle && <> · <a href={`https://instagram.com/${store.instagram_handle}`} target="_blank" rel="noreferrer" className="text-accent hover:underline">@{store.instagram_handle} aç ↗</a></>}
          </p>
        </div>
      </div>

      {/* Karakter / Persona — bir kez tanımla, asistan hep o karakter olsun */}
      <div className="card mb-4">
        <button onClick={() => setPersonaOpen(o => !o)} className="w-full flex items-center justify-between text-left">
          <span className="text-sm font-semibold text-gray-200">🎭 Karakter (Persona) {hasPersona ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 ml-1">tanımlı</span> : <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 ml-1">yok</span>}</span>
          <span className="text-gray-500">{personaOpen ? '▲' : '▼'}</span>
        </button>
        {personaOpen && (
          <div className="mt-3">
            <p className="text-xs text-gray-500 mb-2">
              Asistanın kalıcı kimliği. Bir kez yaz (örn. "Lara" karakteri) — asistan hep bu persona olarak konuşur ve
              <b> tutarlı görünüşlü</b> görseller üretir (fiziksel özellikler her görsel promptuna otomatik girer).
            </p>
            <textarea className="input w-full !text-sm font-mono" rows={10} placeholder="Karakter tanımını buraya yapıştır…"
              value={persona} onChange={e => setPersona(e.target.value)} />
            <div className="flex items-center gap-2 mt-2">
              <button onClick={savePersona} className="btn-primary !text-sm">Karakteri Kaydet</button>
              {persona && <button onClick={() => { setPersona(''); }} className="btn-secondary !text-sm">Temizle</button>}
            </div>
          </div>
        )}
      </div>

      {/* Mod: hızlı üret vs AI sohbet */}
      <div className="flex gap-2 mb-4">
        <button onClick={() => setView('uret')} className={`px-3 py-1.5 rounded-lg text-sm ${view === 'uret' ? 'bg-accent/15 text-accent border border-accent/40' : 'btn-secondary'}`}>✨ Hızlı Üret</button>
        <button onClick={() => setView('sohbet')} className={`px-3 py-1.5 rounded-lg text-sm ${view === 'sohbet' ? 'bg-accent/15 text-accent border border-accent/40' : 'btn-secondary'}`}>💬 AI Sohbet</button>
      </div>

      {view === 'sohbet' && (
        <ChatPanel storeId={storeId} toast={toast}
          onCreated={() => { setView('uret'); setTab('taslak'); loadPosts() }} />
      )}

      {view === 'uret' && <>
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
      </>}
    </div>
  )
}

// Canlı asistan orb'u — durum: idle | thinking | speaking
function AssistantOrb({ state }) {
  return (
    <div className="relative w-12 h-12 shrink-0">
      <div className={`absolute inset-0 rounded-full bg-gradient-to-br from-accent via-fuchsia-500 to-purple-600 ${state === 'thinking' ? 'animate-pulse' : ''}`}
        style={{ animation: state === 'idle' ? 'ig-breathe 3s ease-in-out infinite' : undefined, boxShadow: '0 0 24px rgba(168,85,247,0.5)' }} />
      <div className="absolute inset-1.5 rounded-full bg-brand-card/70 backdrop-blur flex items-center justify-center text-lg">✨</div>
      {state === 'thinking' && <div className="absolute -inset-0.5 rounded-full border-2 border-white/50 border-t-transparent animate-spin" />}
      {state === 'idle' && <div className="absolute inset-0 rounded-full bg-accent/30 animate-ping" style={{ animationDuration: '3s' }} />}
      <style>{`@keyframes ig-breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}`}</style>
    </div>
  )
}

function ChatPanel({ storeId, toast, onCreated }) {
  const [msgs, setMsgs] = useState([])   // {role, text, images:[{path,url}], proposal?}
  const [input, setInput] = useState('')
  const [attach, setAttach] = useState([])
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => { scrollRef.current?.scrollTo({ top: 1e9, behavior: 'smooth' }) }, [msgs, busy])

  const upload = async (e) => {
    const files = Array.from(e.target.files || [])
    e.target.value = ''
    for (const f of files) {
      const fd = new FormData(); fd.append('file', f)
      try { const r = await api.postForm('/api/instagram/upload', fd); setAttach(a => [...a, { path: r.path, url: r.url }]) }
      catch { toast.error('Görsel yüklenemedi') }
    }
  }

  const send = async (quick) => {
    const txt = (quick ?? input).trim()
    if (!txt && attach.length === 0) return
    if (!storeId) { toast.error('Önce marka seç'); return }
    const userMsg = { role: 'user', text: txt, images: attach }
    const next = [...msgs, userMsg]
    setMsgs(next); setInput(''); setAttach([]); setBusy(true)
    try {
      const payload = next.map(m => ({ role: m.role, text: m.text, images: (m.images || []).map(i => i.path) }))
      const r = await api.post('/api/instagram/chat', { store_id: storeId, messages: payload })
      setMsgs(m => [...m, { role: 'assistant', text: r.reply, images: [], proposal: r.proposal || null }])
    } catch (e) { toast.error(e?.detail || 'AI yanıtı alınamadı'); setMsgs(m => m.slice(0, -1)); setInput(userMsg.text); setAttach(userMsg.images) }
    finally { setBusy(false) }
  }

  const feedback = async (caption, rating) => {
    try { await api.post('/api/instagram/feedback', { store_id: storeId, caption, rating }); toast.success(rating === 'iyi' ? 'Beğenildi — bunu öğrendim 👍' : 'Not aldım, bundan kaçınacağım 👎') }
    catch { toast.error('Kaydedilemedi') }
  }

  const addDraft = async (prop) => {
    try {
      await api.post('/api/instagram/draft', {
        store_id: storeId, caption: prop.caption, hashtags: prop.hashtags || null,
        image_path: prop.image_path || null,     // üretilen sahne görseli
        design_id: prop.image_path ? null : (prop.design_id || null),
      })
      toast.success('Taslak kuyruğa eklendi ✓')
      onCreated && onCreated()
    } catch (e) { toast.error(e?.detail || 'Eklenemedi') }
  }

  const QUICK = ['Yeni koleksiyon için 1 gönderi üret', 'Bu tasarımı öne çıkaran bir caption yaz', 'Story fikri ver']

  return (
    <div className="card !p-0 overflow-hidden flex flex-col" style={{ height: '68vh' }}>
      {/* Asistan başlık */}
      <div className="px-4 py-3 border-b border-brand-border flex items-center gap-3 bg-gradient-to-r from-accent/5 to-fuchsia-500/5">
        <AssistantOrb state={busy ? 'thinking' : 'idle'} />
        <div>
          <div className="text-sm font-semibold text-gray-100">Sosyal Medya Asistanı</div>
          <div className="text-[11px] text-gray-500">{busy ? 'düşünüyor…' : 'çevrimiçi · sana içerik üretebilirim'}</div>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {msgs.length === 0 && (
          <div className="text-center py-6">
            <div className="text-gray-400 text-sm mb-3">Ne paylaşalım? Anlat, örnek görsel yükle — senin için üretirim.</div>
            <div className="flex flex-wrap gap-2 justify-center">
              {QUICK.map(q => <button key={q} onClick={() => send(q)} className="text-xs px-3 py-1.5 rounded-full border border-brand-border text-gray-300 hover:bg-brand-input">{q}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-fadein`}>
            <div className={`max-w-[88%] rounded-2xl px-3 py-2 ${m.role === 'user' ? 'bg-accent/15 text-gray-100' : 'bg-brand-input text-gray-200'}`}>
              {(m.images || []).length > 0 && (
                <div className="flex gap-1 flex-wrap mb-1">
                  {m.images.map((im, j) => <img key={j} src={im.url} alt="" className="w-16 h-16 rounded object-cover" />)}
                </div>
              )}
              {m.text && <p className="text-sm whitespace-pre-wrap">{m.text}</p>}
              {m.proposal && <ProposalCard prop={m.proposal} onAdd={addDraft} onFeedback={feedback} />}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="bg-brand-input rounded-2xl px-4 py-3 flex gap-1">
              {[0, 1, 2].map(d => <span key={d} className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: `${d * 0.15}s` }} />)}
            </div>
          </div>
        )}
      </div>

      {attach.length > 0 && (
        <div className="px-3 pt-2 flex gap-1 flex-wrap border-t border-brand-border">
          {attach.map((a, i) => (
            <div key={i} className="relative">
              <img src={a.url} alt="" className="w-12 h-12 rounded object-cover" />
              <button onClick={() => setAttach(x => x.filter((_, k) => k !== i))} className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-4 h-4 text-[10px] leading-none">×</button>
            </div>
          ))}
        </div>
      )}
      <div className="p-3 border-t border-brand-border flex items-end gap-2">
        <label className="btn-secondary !text-sm cursor-pointer whitespace-nowrap" title="Örnek görsel yükle">📎<input type="file" accept="image/*" multiple className="hidden" onChange={upload} /></label>
        <textarea className="input flex-1 !text-sm" rows={1} placeholder="Asistana yaz…" value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
        <button onClick={() => send()} disabled={busy} className="btn-primary !text-sm">Gönder</button>
      </div>
    </div>
  )
}

function ProposalCard({ prop, onAdd, onFeedback }) {
  const [rated, setRated] = useState(null)
  const text = `${prop.caption}${prop.hashtags ? '\n\n' + prop.hashtags : ''}`
  return (
    <div className="mt-2 rounded-xl border border-accent/30 bg-brand-card/60 overflow-hidden">
      {prop.image_url
        ? <img src={prop.image_url} alt="" className="w-full aspect-square object-cover" />
        : <div className="w-full aspect-square bg-brand-input flex flex-col items-center justify-center text-gray-600 text-xs p-3 text-center">
            <span>Görsel üretilemedi</span>
            {prop.image_reason && <span className="text-[10px] text-amber-400/70 mt-1">{prop.image_reason}</span>}
          </div>}
      <div className="p-2.5">
        <p className="text-sm text-gray-100 whitespace-pre-wrap">{prop.caption}</p>
        {prop.hashtags && <p className="text-xs text-accent mt-1">{prop.hashtags}</p>}
        <div className="flex flex-wrap items-center gap-1.5 mt-2">
          <button onClick={() => onAdd(prop)} className="text-[11px] px-2 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10">+ Taslağa ekle</button>
          <button onClick={() => { onFeedback(text, 'iyi'); setRated('iyi') }} className={`text-[13px] px-2 py-1 rounded border ${rated === 'iyi' ? 'border-emerald-500 bg-emerald-500/15' : 'border-brand-border'} hover:bg-brand-input`}>👍</button>
          <button onClick={() => { onFeedback(text, 'kotu'); setRated('kotu') }} className={`text-[13px] px-2 py-1 rounded border ${rated === 'kotu' ? 'border-red-500 bg-red-500/15' : 'border-brand-border'} hover:bg-brand-input`}>👎</button>
          <button onClick={() => navigator.clipboard?.writeText(text)} className="text-[11px] px-2 py-1 rounded border border-brand-border text-gray-300 hover:bg-brand-input">📋 Kopyala</button>
        </div>
      </div>
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
