import { useState, useEffect } from 'react'
import { api, getToken } from '../lib/api'
import { useToast } from '../components/Toast'
import { mutlak } from '../lib/taban'

const STATUS_LABEL = { subscribed: 'Onaylı', pending: 'Onay bekliyor', unsubscribed: 'Çıktı', bounced: 'Hatalı' }
const STATUS_CLS = {
  subscribed: 'bg-emerald-500/15 text-emerald-300',
  pending: 'bg-amber-500/15 text-amber-300',
  unsubscribed: 'bg-gray-500/15 text-gray-400',
  bounced: 'bg-red-500/15 text-red-300',
}
const SOURCE_LABEL = {
  order_mail: 'Sipariş maili', support_mail: 'Destek maili', public_form: 'Form',
  'panel-manual': 'Manuel', import: 'İçe aktarma', manual: 'Manuel',
}

export default function PazarlamaPage() {
  const toast = useToast()
  const [tab, setTab] = useState('aboneler')
  return (
    <div className="space-y-4 animate-fadein">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-semibold text-gray-100">📣 Pazarlama</h1>
        <div className="flex gap-1 bg-brand-input rounded-lg p-1">
          {[['aboneler', 'Aboneler'], ['kampanyalar', 'Kampanyalar']].map(([v, l]) => (
            <button key={v} onClick={() => setTab(v)}
              className={`text-sm px-3 py-1 rounded-md ${tab === v ? 'bg-accent text-white' : 'text-gray-400 hover:text-gray-200'}`}>{l}</button>
          ))}
        </div>
      </div>
      {tab === 'aboneler' ? <SubscribersTab toast={toast} /> : <CampaignsTab toast={toast} />}
    </div>
  )
}

function SubscribersTab({ toast }) {
  const [data, setData] = useState({ counts: {}, subscribers: [] })
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [q, setQ] = useState('')
  const [publicUrl, setPublicUrl] = useState('')
  const [addEmail, setAddEmail] = useState('')
  const [addName, setAddName] = useState('')
  const [adding, setAdding] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filter) params.set('status', filter)
      if (q.trim()) params.set('q', q.trim())
      setData(await api.get(`/api/marketing/subscribers?${params}`))
    } catch (e) { toast.error(e.detail || 'Yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [filter])  // eslint-disable-line
  useEffect(() => { api.get('/api/marketing/public-link').then(r => setPublicUrl(r.url || '')).catch(() => {}) }, [])

  const add = async () => {
    if (!addEmail.trim()) return
    setAdding(true)
    try {
      const r = await api.post('/api/marketing/subscribers', { email: addEmail.trim(), name: addName.trim() })
      toast.success(r.message || 'Davet gönderildi')
      setAddEmail(''); setAddName(''); load()
    } catch (e) { toast.error(e.detail || 'Eklenemedi') }
    finally { setAdding(false) }
  }

  const removeOne = async (s) => {
    if (!confirm(`${s.email} abonelikten çıkarılsın mı?`)) return
    try { await api.post(`/api/marketing/subscribers/${s.id}/unsubscribe`, {}); toast.success('Çıkarıldı'); load() }
    catch (e) { toast.error(e.detail || 'Olmadı') }
  }

  const exportCsv = async () => {
    try {
      const res = await fetch(mutlak('/api/marketing/subscribers/export.csv'), { headers: { Authorization: `Bearer ${getToken()}` } })
      if (!res.ok) { toast.error('İndirilemedi'); return }
      const blob = await res.blob(); const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = 'aboneler.csv'; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch { toast.error('İndirilemedi') }
  }

  // Vitrin bültenine kayıtlı ama kampanya listesinde olmayan müşterileri taşı
  // (eşitleme eklenmeden önce abone olanlar kampanyalarda atlanıyordu)
  const backfill = async () => {
    try {
      const kuru = await api.post('/api/marketing/subscribers/backfill', {})
      if (!kuru.eklenecek) {
        toast.success(`Taşınacak abone yok (${kuru.zaten_vardi} kayıt zaten listede)`)
        return
      }
      if (!window.confirm(
        `Vitrin bültenine kayıtlı ${kuru.eklenecek} müşteri kampanya listesinde yok.

` +
        'Onlar da abone olarak eklensin mi? (Rıza tarihleri kendi kayıtlarından taşınır.)')) return
      const r = await api.post('/api/marketing/subscribers/backfill?apply=true', {})
      toast.success(`${r.eklendi} abone eklendi`)
      load()
    } catch { toast.error('Taşıma başarısız') }
  }

  const copyLink = () => {
    if (!publicUrl) return
    navigator.clipboard?.writeText(publicUrl).then(() => toast.success('Link kopyalandı')).catch(() => {})
  }

  const c = data.counts || {}
  const subs = data.subscribers || []

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[['Toplam', c.total, 'text-gray-100'], ['Onaylı', c.subscribed, 'text-emerald-300'],
          ['Onay bekliyor', c.pending, 'text-amber-300'], ['Çıkanlar', c.unsubscribed, 'text-gray-400']].map(([l, v, cls]) => (
          <div key={l} className="card !p-3">
            <div className="text-xs text-gray-500">{l}</div>
            <div className={`text-2xl font-semibold ${cls}`}>{v ?? 0}</div>
          </div>
        ))}
      </div>

      <div className="card space-y-3">
        <div>
          <div className="text-xs text-gray-400 mb-1">Public abonelik linki — müşterilerle paylaş (sosyal medya, web, QR)</div>
          <div className="flex gap-2">
            <input readOnly value={publicUrl} placeholder="—" className="input flex-1 !text-xs font-mono" />
            <button onClick={copyLink} disabled={!publicUrl} className="btn-secondary !text-sm disabled:opacity-40">⧉ Kopyala</button>
          </div>
        </div>
        <div className="border-t border-brand-border pt-3">
          <div className="text-xs text-gray-400 mb-1">
            Manuel abone ekle <span className="text-gray-600">— KVKK gereği müşteriye onay maili gider, onaylayınca listeye girer</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <input value={addName} onChange={e => setAddName(e.target.value)} placeholder="Ad (opsiyonel)" className="input !text-sm w-40" />
            <input value={addEmail} onChange={e => setAddEmail(e.target.value)} type="email" placeholder="E-posta" className="input !text-sm flex-1 min-w-[180px]" />
            <button onClick={add} disabled={adding || !addEmail.trim()} className="btn-primary !text-sm disabled:opacity-40">{adding ? '...' : '+ Davet gönder'}</button>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {[['', 'Tümü'], ['subscribed', 'Onaylı'], ['pending', 'Bekleyen'], ['unsubscribed', 'Çıkanlar']].map(([v, l]) => (
          <button key={v} onClick={() => setFilter(v)}
            className={`!text-xs px-3 py-1.5 rounded-lg border ${filter === v ? 'bg-accent/15 border-accent/40 text-accent' : 'border-brand-border text-gray-400 hover:text-gray-200'}`}>{l}</button>
        ))}
        <div className="flex-1" />
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} placeholder="E-posta ara..." className="input !text-sm w-48" />
        <button onClick={load} className="btn-secondary !text-sm">Ara</button>
        <button onClick={backfill} className="btn-secondary !text-sm" title="Vitrin bültenine kayıtlı müşterileri kampanya listesine taşı">⇄ Vitrinle eşitle</button>
        <button onClick={exportCsv} className="btn-secondary !text-sm">⬇ CSV</button>
      </div>

      <div className="card !p-0 overflow-hidden">
        {loading ? <div className="p-8 text-center text-gray-500 text-sm">Yükleniyor…</div>
          : subs.length === 0 ? <div className="p-8 text-center text-gray-500 text-sm">Abone yok.</div>
          : (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-gray-500 border-b border-brand-border">
                <th className="px-3 py-2">E-posta</th>
                <th className="px-3 py-2">Ad</th>
                <th className="px-3 py-2">Durum</th>
                <th className="px-3 py-2 hidden sm:table-cell">Kaynak</th>
                <th className="px-3 py-2 hidden md:table-cell">Rıza tarihi</th>
                <th className="px-3 py-2"></th>
              </tr></thead>
              <tbody>
                {subs.map(s => (
                  <tr key={s.id} className="border-b border-brand-border/40 last:border-0">
                    <td className="px-3 py-2 text-gray-200">{s.email}</td>
                    <td className="px-3 py-2 text-gray-400">{s.name || '—'}</td>
                    <td className="px-3 py-2"><span className={`text-[11px] px-1.5 py-0.5 rounded ${STATUS_CLS[s.status] || ''}`}>{STATUS_LABEL[s.status] || s.status}</span></td>
                    <td className="px-3 py-2 text-gray-500 hidden sm:table-cell">{SOURCE_LABEL[s.source] || s.source || '—'}</td>
                    <td className="px-3 py-2 text-gray-500 hidden md:table-cell text-xs">{s.consent_at ? new Date(s.consent_at).toLocaleDateString('tr-TR') : '—'}</td>
                    <td className="px-3 py-2 text-right">{s.status !== 'unsubscribed' && <button onClick={() => removeOne(s)} className="text-xs text-red-400 hover:text-red-300">Çıkar</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  )
}

const CAMP_STATUS = {
  draft: ['Taslak', 'bg-gray-500/15 text-gray-300'],
  sending: ['Gönderiliyor…', 'bg-amber-500/15 text-amber-300'],
  sent: ['Gönderildi', 'bg-emerald-500/15 text-emerald-300'],
  failed: ['Hata', 'bg-red-500/15 text-red-300'],
}
const EMPTY_CAMP = { subject: '', title: '', body: '', button_label: '', button_url: '', image_url: '', preheader: '', personalize: false }

function CampaignsTab({ toast }) {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [f, setF] = useState(EMPTY_CAMP)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)

  const uploadImg = async (e) => {
    const file = e.target.files?.[0]; if (!file) return
    setUploading(true)
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await api.postForm('/api/marketing/campaigns/upload-image', fd)
      setF(prev => ({ ...prev, image_url: r.url }))
    } catch (err) { toast.error(err.detail || 'Görsel yüklenemedi') }
    finally { setUploading(false); e.target.value = '' }
  }

  // Ürün kartları
  const addProduct = () => setF(p => ({ ...p, products: [...(p.products || []), { image: '', title: '', url: '' }] }))
  const updateProduct = (i, k, v) => setF(p => { const ps = [...(p.products || [])]; ps[i] = { ...ps[i], [k]: v }; return { ...p, products: ps } })
  const removeProduct = (i) => setF(p => ({ ...p, products: (p.products || []).filter((_, j) => j !== i) }))
  const uploadProductImg = async (i, e) => {
    const file = e.target.files?.[0]; if (!file) return
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await api.postForm('/api/marketing/campaigns/upload-image', fd)
      updateProduct(i, 'image', r.url)
    } catch (err) { toast.error(err.detail || 'Görsel yüklenemedi') }
    finally { e.target.value = '' }
  }

  // Canlı önizleme (form değiştikçe, debounced)
  const [previewHtml, setPreviewHtml] = useState('')
  useEffect(() => {
    if (!showNew) return
    const t = setTimeout(() => {
      api.post('/api/marketing/campaigns/preview', f).then(r => setPreviewHtml(r.html || '')).catch(() => {})
    }, 500)
    return () => clearTimeout(t)
  }, [f, showNew])

  const load = async () => {
    setLoading(true)
    try { setList((await api.get('/api/marketing/campaigns')).campaigns || []) }
    catch (e) { toast.error(e.detail || 'Yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])  // eslint-disable-line

  const create = async () => {
    if (!f.subject.trim()) { toast.error('Konu gerekli'); return }
    setSaving(true)
    try {
      await api.post('/api/marketing/campaigns', f)
      toast.success('Kampanya taslağı oluşturuldu'); setF(EMPTY_CAMP); setShowNew(false); load()
    } catch (e) { toast.error(e.detail || 'Olmadı') }
    finally { setSaving(false) }
  }

  const test = async (c) => {
    const email = prompt('Test e-postası hangi adrese gönderilsin?')
    if (!email) return
    try { const r = await api.post(`/api/marketing/campaigns/${c.id}/test`, { email }); toast.success(r.message || 'Test gönderildi') }
    catch (e) { toast.error(e.detail || 'Gönderilemedi') }
  }
  const send = async (c) => {
    if (!confirm(`"${c.subject}" kampanyası TÜM onaylı abonelere gönderilecek. Emin misin?`)) return
    try { const r = await api.post(`/api/marketing/campaigns/${c.id}/send`, {}); toast.success(r.message || 'Gönderim başladı'); setTimeout(load, 1500) }
    catch (e) { toast.error(e.detail || 'Gönderilemedi') }
  }
  const del = async (c) => {
    if (!confirm('Kampanya silinsin mi?')) return
    try { await api.del(`/api/marketing/campaigns/${c.id}`); toast.success('Silindi'); load() }
    catch (e) { toast.error(e.detail || 'Silinemedi') }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center gap-2">
        <p className="text-sm text-gray-400">Onaylı abonelere markalı toplu e-posta gönder. Önce <b>Test</b> et, sonra <b>Gönder</b>.</p>
        <div className="flex gap-2 shrink-0">
          <button onClick={load} className="btn-secondary !text-sm">↻ Yenile</button>
          <button onClick={() => setShowNew(s => !s)} className="btn-primary !text-sm">{showNew ? 'Kapat' : '+ Yeni Kampanya'}</button>
        </div>
      </div>

      {showNew && (
        <div className="grid lg:grid-cols-2 gap-4 items-start">
          <div className="card space-y-2">
            <input value={f.subject} onChange={e => setF({ ...f, subject: e.target.value })} placeholder="Konu — e-posta başlığı *" className="input !text-sm w-full" />
            <input value={f.preheader} onChange={e => setF({ ...f, preheader: e.target.value })} placeholder="Önizleme metni — gelen kutusunda görünür (ops.)" className="input !text-sm w-full" />
            <input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} placeholder="İçerik başlığı (opsiyonel)" className="input !text-sm w-full" />

            {f.image_url ? (
              <div className="flex items-center gap-3">
                <img src={f.image_url} alt="" className="h-14 rounded-lg border border-brand-border" />
                <button onClick={() => setF({ ...f, image_url: '' })} className="text-xs text-red-400 hover:text-red-300">Görseli kaldır</button>
              </div>
            ) : (
              <label className="btn-secondary !text-sm cursor-pointer inline-flex w-fit">
                {uploading ? 'Yükleniyor…' : '🖼 Üst görsel ekle'}
                <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={uploadImg} disabled={uploading} />
              </label>
            )}

            <textarea value={f.body} onChange={e => setF({ ...f, body: e.target.value })} rows={4} placeholder="Mesaj metni... (boş satır = yeni paragraf)" className="input !text-sm w-full resize-y" />

            {/* Ürün kartları */}
            <div className="border-t border-brand-border pt-2">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-gray-400">Ürün kartları (görsel + ad + link)</span>
                <button onClick={addProduct} className="text-xs text-accent hover:text-accent/80">+ Ürün ekle</button>
              </div>
              <div className="space-y-2">
                {(f.products || []).map((p, i) => (
                  <div key={i} className="flex gap-2 items-start bg-brand-input/40 rounded-lg p-2">
                    {p.image
                      ? <img src={p.image} alt="" className="w-12 h-12 object-cover rounded border border-brand-border shrink-0" />
                      : <label className="w-12 h-12 shrink-0 rounded border border-dashed border-brand-border flex items-center justify-center text-base text-gray-500 cursor-pointer">🖼<input type="file" accept="image/*" className="hidden" onChange={e => uploadProductImg(i, e)} /></label>}
                    <div className="flex-1 space-y-1 min-w-0">
                      <input value={p.title} onChange={e => updateProduct(i, 'title', e.target.value)} placeholder="Ürün adı" className="input !text-xs w-full" />
                      <input value={p.url} onChange={e => updateProduct(i, 'url', e.target.value)} placeholder="Ürün linki" className="input !text-xs w-full" />
                    </div>
                    <button onClick={() => removeProduct(i)} className="text-gray-500 hover:text-red-400 text-sm shrink-0" title="Kaldır">✕</button>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap gap-2 border-t border-brand-border pt-2">
              <input value={f.button_label} onChange={e => setF({ ...f, button_label: e.target.value })} placeholder="Buton yazısı (ops.)" className="input !text-sm flex-1 min-w-[140px]" />
              <input value={f.button_url} onChange={e => setF({ ...f, button_url: e.target.value })} placeholder="Buton linki (ops.)" className="input !text-sm flex-1 min-w-[140px]" />
            </div>
            <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
              <input type="checkbox" checked={f.personalize} onChange={e => setF({ ...f, personalize: e.target.checked })} />
              İsimle kişiselleştir — adı varsa "Merhaba [ad]," ile başlar
            </label>
            <div className="flex justify-end"><button onClick={create} disabled={saving} className="btn-primary !text-sm disabled:opacity-40">{saving ? '...' : 'Taslak Oluştur'}</button></div>
          </div>

          {/* Canlı önizleme */}
          <div className="lg:sticky lg:top-4">
            <div className="text-xs text-gray-400 mb-1">📧 Canlı önizleme</div>
            <iframe srcDoc={previewHtml} title="Önizleme" className="w-full h-[640px] rounded-lg border border-brand-border bg-white" />
          </div>
        </div>
      )}

      {loading ? <div className="card text-center text-gray-500 text-sm py-8">Yükleniyor…</div>
        : list.length === 0 ? <div className="card text-center text-gray-500 text-sm py-8">Henüz kampanya yok.</div>
        : list.map(c => {
          const [lbl, cls] = CAMP_STATUS[c.status] || [c.status, '']
          return (
            <div key={c.id} className="card">
              <div className="flex justify-between items-start gap-3">
                <div className="min-w-0">
                  <div className="font-medium text-gray-100 truncate">{c.subject}</div>
                  <div className="text-xs text-gray-500 mt-0.5 truncate">{c.title || (c.body ? c.body.slice(0, 60) : '—')}</div>
                  <div className="mt-2 flex items-center gap-2 flex-wrap">
                    <span className={`text-[11px] px-1.5 py-0.5 rounded ${cls}`}>{lbl}</span>
                    {(c.status === 'sent' || c.status === 'sending') && (
                      <span className="text-xs text-gray-500">
                        {c.sent_count}/{c.recipient_count} gönderildi{c.fail_count ? ` · ${c.fail_count} hata` : ''}
                        {c.status === 'sent' && c.sent_count > 0 && (
                          <> · 👁 {c.open_count} (%{Math.round(100 * c.open_count / c.sent_count)}) · 🖱 {c.click_count} (%{Math.round(100 * c.click_count / c.sent_count)})</>
                        )}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-1.5 shrink-0">
                  <button onClick={() => test(c)} className="btn-secondary !text-xs !py-1 !px-2">Test</button>
                  {c.status === 'draft' && (
                    <>
                      <button onClick={() => send(c)} className="!text-xs !py-1 !px-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium">Gönder</button>
                      <button onClick={() => del(c)} className="text-xs text-red-400 hover:text-red-300 px-1">Sil</button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        })}
    </div>
  )
}
