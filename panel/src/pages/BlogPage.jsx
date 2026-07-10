import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import { Modal } from './UrunlerPage'

// Blog — vitrin için SEO içeriği (Shopify Online Store > Blog posts).
export default function BlogPage() {
  const { storeId } = useStore()
  const toast = useToast()
  const [posts, setPosts] = useState([])
  const [editing, setEditing] = useState(null)   // null | 'new' | post

  const load = useCallback(async () => {
    if (!storeId) return
    try { setPosts(await api.get(`/api/blog?store_id=${storeId}`)) }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Yazılar yüklenemedi') }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const togglePublish = async (p) => {
    try {
      await api.patch(`/api/blog/${p.id}`, { is_published: !p.is_published })
      toast.success(p.is_published ? 'Yazı yayından kaldırıldı' : 'Yazı yayınlandı 🎉')
      load()
    } catch { toast.error('Güncellenemedi') }
  }
  const remove = async (p) => {
    if (!window.confirm(`"${p.title}" silinecek. Emin misiniz?`)) return
    try { await api.del(`/api/blog/${p.id}`); load() }
    catch { toast.error('Silinemedi') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Blog</h1>
        <span className="text-sm text-panel-muted">{posts.length} yazı</span>
        <button onClick={() => setEditing('new')} className="btn-primary ml-auto">+ Yeni Yazı</button>
      </div>

      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-panel-muted text-xs bg-panel-input">
            <tr>
              <th className="text-left px-4 py-2.5">Başlık</th>
              <th className="text-left px-4 py-2.5">Adres</th>
              <th className="text-left px-4 py-2.5">Durum</th>
              <th className="text-left px-4 py-2.5">Yayın Tarihi</th>
              <th className="px-2 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {posts.map(p => (
              <tr key={p.id} className="border-t border-panel-border">
                <td className="px-4 py-2.5 font-medium">{p.title}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-panel-muted">/blog/{p.slug}</td>
                <td className="px-4 py-2.5">
                  <button onClick={() => togglePublish(p)}
                    className={`text-xs px-2 py-0.5 rounded-full ${p.is_published
                      ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    {p.is_published ? 'Yayında' : 'Taslak'}
                  </button>
                </td>
                <td className="px-4 py-2.5 text-xs text-panel-muted">
                  {p.published_at ? new Date(p.published_at).toLocaleDateString('tr-TR') : '—'}
                </td>
                <td className="px-2 py-2.5 text-right whitespace-nowrap">
                  <button onClick={() => setEditing(p)} className="text-xs text-panel-muted hover:text-panel-ink px-1.5">Düzenle</button>
                  <button onClick={() => remove(p)} className="text-xs text-red-400 hover:text-red-600 px-1.5">Sil</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {posts.length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">
            Henüz yazı yok — SEO için ürün rehberleri, kılıf bakım ipuçları yazın.
          </div>
        )}
      </div>

      {editing && (
        <PostModal storeId={storeId} post={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />
      )}
    </div>
  )
}

function PostModal({ storeId, post, onClose, onSaved }) {
  const isNew = !post
  const toast = useToast()
  const [form, setForm] = useState(() => ({
    title: post?.title || '',
    slug: post?.slug || '',
    excerpt: post?.excerpt || '',
    content: post?.content || '',
    cover_url: post?.cover_url || null,
    seo_title: post?.seo_title || '',
    seo_description: post?.seo_description || '',
    is_published: post?.is_published || false,
  }))
  const [busy, setBusy] = useState(false)

  const uploadCover = async (file) => {
    if (!file) return
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('kind', 'blog')
      const r = await api.postForm(`/api/store-settings/${storeId}/assets`, fd)
      setForm(f => ({ ...f, cover_url: r.url }))
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Görsel yüklenemedi')
    } finally { setBusy(false) }
  }

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm(f => ({ ...f, [k]: v }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    const payload = {
      title: form.title.trim(),
      slug: form.slug.trim() || null,
      excerpt: form.excerpt.trim() || null,
      content: form.content,
      cover_url: form.cover_url,
      seo_title: form.seo_title.trim() || null,
      seo_description: form.seo_description.trim() || null,
      is_published: form.is_published,
    }
    try {
      if (isNew) await api.post('/api/blog', { ...payload, store_id: storeId })
      else await api.patch(`/api/blog/${post.id}`, payload)
      toast.success('Yazı kaydedildi')
      onSaved()
    } catch (e2) {
      toast.error(typeof e2?.detail === 'string' ? e2.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  return (
    <Modal title={isNew ? 'Yeni Yazı' : `Yazı: ${post.title}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Başlık</span>
          <input className="input mt-1" value={form.title} onChange={set('title')}
            required minLength={2} maxLength={300} />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Adres (boş = başlıktan üretilir)</span>
          <input className="input mt-1 font-mono text-xs" value={form.slug}
            onChange={set('slug')} placeholder="kilif-bakim-rehberi" />
        </label>
        <div className="text-sm">
          <span className="text-panel-muted text-xs">Kapak görseli (ops.)</span>
          <div className="mt-1 flex items-center gap-2">
            {form.cover_url ? (
              <>
                <img src={form.cover_url} alt="Kapak"
                  className="h-16 max-w-[160px] object-cover rounded-lg border border-panel-border" />
                <button type="button" onClick={() => setForm(f => ({ ...f, cover_url: null }))}
                  className="text-xs text-red-400 hover:text-red-600">Kaldır</button>
              </>
            ) : (
              <label className="btn-ghost !py-1.5 text-xs cursor-pointer">
                ⬆ Görsel Yükle
                <input type="file" accept="image/*" className="hidden"
                  onChange={e => uploadCover(e.target.files?.[0])} />
              </label>
            )}
          </div>
        </div>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Özet (listede görünür, ops.)</span>
          <input className="input mt-1" value={form.excerpt} onChange={set('excerpt')} maxLength={500} />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">İçerik (satır sonları korunur)</span>
          <textarea className="input mt-1" rows={10} value={form.content}
            onChange={set('content')} maxLength={100000} />
        </label>
        <details className="text-sm">
          <summary className="text-xs text-panel-muted cursor-pointer">SEO ayarları (ops.)</summary>
          <div className="mt-2 space-y-2">
            <input className="input" value={form.seo_title} onChange={set('seo_title')}
              placeholder="SEO başlığı" maxLength={300} />
            <input className="input" value={form.seo_description} onChange={set('seo_description')}
              placeholder="SEO açıklaması" maxLength={500} />
          </div>
        </details>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.is_published} onChange={set('is_published')} />
          Yayında (vitrinde /blog altında görünür)
        </label>
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button disabled={busy} className="btn-primary">
            {busy ? 'Kaydediliyor…' : isNew ? 'Oluştur' : 'Kaydet'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
