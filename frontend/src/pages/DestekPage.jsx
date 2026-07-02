import { useEffect, useState, useRef } from 'react'
import { api } from '../lib/api'

const STATUS_LABEL = { acik: 'Açık', cevaplandi: 'Cevaplandı', kapali: 'Kapalı' }
const STATUS_COLOR = {
  acik: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  cevaplandi: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  kapali: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
}

function fmt(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return ts }
}

// Hazır mesaj şablonları. {siparis}/{musteri}/{takip} otomatik dolar; "..." kullanıcıya kalır.
const DEFAULT_TEMPLATES = [
  { name: 'Hazırlanıyor', body: 'Merhaba {musteri}, {siparis} numaralı siparişiniz şu anda hazırlanıyor. En kısa sürede kargoya verilecektir. İlginiz için teşekkürler 🙏' },
  { name: 'Kargoya verildi', body: 'Merhaba {musteri}, {siparis} numaralı siparişiniz kargoya verildi. Takip numaranız: {takip}. Sağlıkla kullanın 😊' },
  { name: 'Kargo takip', body: 'Merhaba, siparişiniz ... tarihinde kargoya verildi, tahmini teslim ... . Takip no: {takip}.' },
  { name: 'Adres teyidi', body: 'Merhaba {musteri}, siparişinizi göndermeden önce adresinizi teyit etmek istiyoruz: ... . Doğru mudur?' },
  { name: 'Görsel isteği', body: 'Merhaba, size daha iyi yardımcı olabilmemiz için ürünün/sorunun fotoğrafını paylaşabilir misiniz?' },
  { name: 'Gecikme / özür', body: 'Merhaba {musteri}, yaşanan gecikme için özür dileriz. Siparişiniz ... nedeniyle ... . En kısa sürede çözüp size döneceğiz.' },
  { name: 'Kapanış / teşekkür', body: 'Rica ederiz, başka bir sorunuz olursa buradan yazabilirsiniz. İyi günler dileriz 🌸' },
]
const TPL_KEY = 'destek_templates'
function loadCustomTemplates() {
  try { const a = JSON.parse(localStorage.getItem(TPL_KEY) || '[]'); return Array.isArray(a) ? a : [] } catch { return [] }
}

export default function DestekPage() {
  const [threads, setThreads] = useState([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [active, setActive] = useState(null)        // detay (mesajlarla)
  const [reply, setReply] = useState('')
  const [replyImg, setReplyImg] = useState(null)       // File
  const [replyImgPreview, setReplyImgPreview] = useState('')
  const [sending, setSending] = useState(false)
  const [drafting, setDrafting] = useState(false)
  const [aiNote, setAiNote] = useState('')
  const [okMsg, setOkMsg] = useState('')
  const [showTpl, setShowTpl] = useState(false)
  const [customTpl, setCustomTpl] = useState(loadCustomTemplates())

  const fillTokens = (text) => (text || '')
    .replaceAll('{siparis}', active?.order_number || '...')
    .replaceAll('{musteri}', ((active?.order_detail?.customer_name || active?.customer_name || '').trim().split(/\s+/)[0]) || '')
    .replaceAll('{takip}', active?.order_detail?.takip_no || '...')
  const applyTemplate = (body) => {
    const filled = fillTokens(body)
    setReply(r => r.trim() ? r.replace(/\s*$/, '\n') + filled : filled)
    setShowTpl(false)
  }
  const saveCurrentAsTemplate = () => {
    const b = reply.trim()
    if (!b) return
    const name = (prompt('Şablon adı:') || '').trim()
    if (!name) return
    const next = [...customTpl, { name, body: b }]
    setCustomTpl(next); localStorage.setItem(TPL_KEY, JSON.stringify(next))
  }
  const deleteCustomTemplate = (i) => {
    const next = customTpl.filter((_, j) => j !== i)
    setCustomTpl(next); localStorage.setItem(TPL_KEY, JSON.stringify(next))
  }
  const msgEndRef = useRef(null)

  const loadThreads = async () => {
    setLoading(true)
    try {
      const q = filter ? `?status=${filter}` : ''
      setThreads(await api.get(`/api/support/threads${q}`))
    } catch (e) {
      setError(e.detail || 'Yükleme başarısız')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadThreads() }, [filter])

  // Telegram deep-link: /destek?thread=<id> ile gelince o talebi otomatik ac
  useEffect(() => {
    const tid = new URLSearchParams(window.location.search).get('thread')
    if (tid) {
      openThread(tid)
      // URL'i temizle (geri/yenilemede tekrar acmasin)
      window.history.replaceState({}, '', '/destek')
    }
  }, [])

  const openThread = async (id) => {
    try {
      const t = await api.get(`/api/support/threads/${id}`)
      setActive(t)
      setAiNote('')
      if (t.unread_admin > 0) {
        await api.post(`/api/support/threads/${id}/read`, {})
        loadThreads()
      }
    } catch (e) {
      setError(e.detail || 'Konuşma açılamadı')
    }
  }

  useEffect(() => {
    if (msgEndRef.current) msgEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [active])

  const uploadImage = async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const token = localStorage.getItem('baskici_token')
    const res = await fetch('/api/support/upload', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Görsel yüklenemedi')
    return data.url
  }

  const onPickImage = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(f.type)) { setError('Yalnızca JPG, PNG veya WEBP'); e.target.value = ''; return }
    if (f.size > 5 * 1024 * 1024) { setError('Görsel en fazla 5MB'); e.target.value = ''; return }
    setError('')
    setReplyImg(f)
    setReplyImgPreview(URL.createObjectURL(f))
  }

  const clearImage = () => { setReplyImg(null); setReplyImgPreview('') }

  const aiDraft = async () => {
    if (!active) return
    setDrafting(true)
    setError('')
    try {
      const r = await api.post(`/api/support/threads/${active.id}/ai-draft`, {})
      if (r?.draft) setReply(r.draft)
      setAiNote(r?.note || '')
    } catch (e) {
      setError(e.detail || e.message || 'AI taslak üretilemedi')
    } finally {
      setDrafting(false)
    }
  }

  const sendReply = async () => {
    if (!active || (reply.trim().length < 1 && !replyImg)) return
    setSending(true)
    setError(''); setOkMsg('')
    try {
      let image_url = null
      if (replyImg) image_url = await uploadImage(replyImg)
      const updated = await api.post(`/api/support/threads/${active.id}/reply`, {
        message: reply.trim(), image_url,
      })
      setActive(updated)
      setReply('')
      setAiNote('')
      clearImage()
      loadThreads()
      // Backend, müşteri e-postası varsa otomatik "Destek talebiniz yanıtlandı" maili atar
      if (updated.email_sent) {
        setOkMsg(`✅ Cevap gönderildi · müşteriye e-posta iletildi (${active.customer_email})`)
        setTimeout(() => setOkMsg(''), 4000)
      } else if (active.customer_email && updated.email_error) {
        setError(`Cevap kaydedildi ama e-posta gönderilemedi: ${updated.email_error}`)
      } else {
        setOkMsg('✅ Cevap gönderildi')
        setTimeout(() => setOkMsg(''), 3000)
      }
    } catch (e) {
      setError(e.detail || e.message || 'Cevap gönderilemedi')
    } finally {
      setSending(false)
    }
  }

  const closeThread = async () => {
    if (!active) return
    if (!confirm('Bu konuşmayı kapatmak istiyor musun?')) return
    try {
      await api.post(`/api/support/threads/${active.id}/close`, {})
      const t = await api.get(`/api/support/threads/${active.id}`)
      setActive(t)
      loadThreads()
    } catch (e) {
      setError(e.detail || 'Kapatılamadı')
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">Destek</h1>
          <p className="text-sm text-gray-500 mt-1">Müşteri sipariş takip mesajları</p>
        </div>
        <div className="flex gap-1.5">
          {[['', 'Tümü'], ['acik', 'Açık'], ['cevaplandi', 'Cevaplandı'], ['kapali', 'Kapalı']].map(([v, l]) => (
            <button key={v} onClick={() => { setFilter(v); setActive(null) }}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                filter === v ? 'bg-brand-input text-gray-100 border-white/20' : 'text-gray-400 border-white/5 hover:border-white/15'
              }`}>{l}</button>
          ))}
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-4">{error}</div>
      )}
      {okMsg && (
        <div className="text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2 mb-4">{okMsg}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-[340px_1fr] gap-4">
        {/* Thread listesi */}
        <div className="space-y-2">
          {loading && <div className="text-gray-500 text-sm">Yükleniyor...</div>}
          {!loading && threads.length === 0 && (
            <div className="card text-center py-10 text-sm text-gray-500">Konuşma yok</div>
          )}
          {threads.map(t => (
            <button key={t.id} onClick={() => openThread(t.id)}
              className={`w-full text-left card hover:border-white/20 transition-colors ${
                active?.id === t.id ? 'border-white/30' : ''
              }`}>
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-semibold text-gray-100 text-sm">#{t.order_number || '—'}</span>
                <div className="flex items-center gap-1.5">
                  {t.unread_admin > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500 text-white font-bold">{t.unread_admin}</span>
                  )}
                  <span className={`text-[10px] uppercase px-1.5 py-0.5 rounded border ${STATUS_COLOR[t.status] || ''}`}>
                    {STATUS_LABEL[t.status] || t.status}
                  </span>
                </div>
              </div>
              <div className="text-xs text-gray-500 truncate">{t.customer_email}</div>
              {t.last_preview && (
                <div className="text-xs text-gray-400 mt-1.5 truncate">
                  {t.last_sender === 'admin' ? '↩ ' : ''}{t.last_preview}
                </div>
              )}
              <div className="text-[10px] text-gray-600 mt-1">{fmt(t.last_message_at)}</div>
            </button>
          ))}
        </div>

        {/* Konuşma */}
        <div className="card min-h-[420px] flex flex-col">
          {!active && <div className="flex-1 flex items-center justify-center text-sm text-gray-500">Bir konuşma seç</div>}
          {active && (
            <>
              <div className="flex items-center justify-between gap-2 pb-3 border-b border-white/5 mb-3">
                <div>
                  <div className="font-semibold text-gray-100">#{active.order_number || '—'}</div>
                  <div className="text-xs text-gray-500">{active.customer_email}</div>
                </div>
                {active.status !== 'kapali' && (
                  <button onClick={closeThread} className="text-xs px-2 py-1 rounded-lg text-gray-400 hover:bg-white/5">Kapat</button>
                )}
              </div>

              {/* Sipariş detayı */}
              {active.order_detail?.found && (
                <div className="mb-3 rounded-lg bg-brand-input/30 border border-brand-border/60 px-3 py-2">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-semibold text-gray-300">📦 Sipariş detayı · {active.order_detail.total_qty} ürün</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${active.order_detail.cancelled ? 'bg-red-500/15 text-red-300' : (active.order_detail.fulfillment_status === 'fulfilled' || (active.order_detail.stage || 0) >= 8) ? 'bg-emerald-500/15 text-emerald-300' : 'bg-brand-input text-gray-400'}`}>
                      {active.order_detail.cancelled ? 'İptal' : (active.order_detail.stage_label || '—')}
                    </span>
                  </div>
                  <ul className="space-y-0.5 text-xs text-gray-300">
                    {(active.order_detail.items || []).map((it, i) => (
                      <li key={i} className="flex items-center gap-1.5">
                        <span className="tabular-nums text-gray-500 shrink-0">{it.quantity}×</span>
                        <span className="truncate">{it.model || it.title || '—'}</span>
                        {it.is_hazir && <span className="text-emerald-400 shrink-0" title="Hazır">✓</span>}
                      </li>
                    ))}
                  </ul>
                  {active.order_detail.takip_no && (
                    <div className="text-[11px] text-gray-500 mt-1.5 pt-1.5 border-t border-brand-border/40">
                      🚚 {active.order_detail.kargo_firma || 'Kargo'}: <span className="text-gray-300 font-medium">{active.order_detail.takip_no}</span>
                    </div>
                  )}
                </div>
              )}
              {active.order_detail && !active.order_detail.found && (
                <div className="mb-3 text-[11px] text-gray-600">Bu sipariş numarası sistemde bulunamadı.</div>
              )}

              <div className="flex-1 overflow-y-auto space-y-2 mb-3 max-h-[420px]">
                {(active.messages || []).map(m => {
                  const mine = m.sender === 'admin'
                  return (
                    <div key={m.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-xl px-3 py-2 ${
                        mine ? 'bg-emerald-500/15 text-emerald-100' : 'bg-white/5 text-gray-200'
                      }`}>
                        <div className="text-[10px] opacity-60 mb-0.5">{mine ? 'Sen' : 'Müşteri'} · {fmt(m.created_at)}</div>
                        {m.body && <div className="text-sm whitespace-pre-wrap leading-relaxed">{m.body}</div>}
                        {m.image_url && (
                          <a href={m.image_url} target="_blank" rel="noreferrer">
                            <img src={m.image_url} alt="" className="mt-1.5 max-w-[200px] max-h-[200px] rounded-lg border border-white/10" />
                          </a>
                        )}
                      </div>
                    </div>
                  )
                })}
                <div ref={msgEndRef} />
              </div>

              {active.status === 'kapali' ? (
                <div className="text-xs text-gray-500 text-center py-2 border-t border-white/5">Bu konuşma kapatıldı</div>
              ) : (
                <div className="border-t border-white/5 pt-3">
                  {aiNote && (
                    <div className="mb-2 rounded-lg bg-accent/10 border border-accent/25 px-3 py-2 animate-popin">
                      <div className="flex items-start gap-2">
                        <span className="text-sm shrink-0">📝</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-[11px] font-semibold text-accent mb-0.5">Operatöre not — müşteriye gönderilmez</div>
                          <div className="text-xs text-gray-300 whitespace-pre-line leading-relaxed">{aiNote}</div>
                        </div>
                        <button onClick={() => setAiNote('')} title="Notu gizle"
                          className="text-gray-500 hover:text-gray-300 text-sm leading-none shrink-0">✕</button>
                      </div>
                    </div>
                  )}
                  {replyImgPreview && (
                    <div className="mb-2 flex items-center gap-2">
                      <img src={replyImgPreview} alt="" className="max-w-[80px] max-h-[80px] rounded-lg border border-white/10" />
                      <button onClick={clearImage} className="text-xs text-red-400 hover:underline">kaldır</button>
                    </div>
                  )}
                  <textarea value={reply} onChange={e => setReply(e.target.value)} rows={3}
                    placeholder="Cevabını yaz... (müşteri takip sayfasında görecek)"
                    className="w-full bg-brand-input border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100 resize-y focus:outline-none focus:border-white/25"
                    onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendReply() }} />
                  <div className="flex justify-between items-center mt-2">
                    <div className="flex items-center gap-3">
                      <label className="text-xs text-gray-400 hover:text-gray-200 cursor-pointer">
                        📎 Görsel
                        <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={onPickImage} />
                      </label>
                      <button onClick={aiDraft} disabled={drafting || sending}
                        className="text-xs text-accent hover:text-accent/80 disabled:opacity-40 flex items-center gap-1"
                        title="Müşterinin mesajına Claude ile yanıt taslağı üret">
                        {drafting ? '✨ Yazılıyor…' : '✨ AI Taslak'}
                      </button>
                      <div className="relative">
                        <button onClick={() => setShowTpl(v => !v)} className="text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1"
                          title="Hazır mesaj şablonu ekle">💬 Hazır mesaj</button>
                        {showTpl && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={() => setShowTpl(false)} />
                            <div className="absolute bottom-6 left-0 z-50 w-64 max-h-72 overflow-y-auto bg-brand-card border border-brand-border rounded-lg shadow-2xl p-1">
                              {DEFAULT_TEMPLATES.map((t, i) => (
                                <button key={`d${i}`} onClick={() => applyTemplate(t.body)}
                                  className="w-full text-left px-2.5 py-1.5 rounded hover:bg-brand-input text-xs text-gray-200">{t.name}</button>
                              ))}
                              {customTpl.length > 0 && <div className="border-t border-brand-border/50 my-1" />}
                              {customTpl.map((t, i) => (
                                <div key={`c${i}`} className="flex items-center group">
                                  <button onClick={() => applyTemplate(t.body)}
                                    className="flex-1 text-left px-2.5 py-1.5 rounded hover:bg-brand-input text-xs text-gray-200 truncate">⭐ {t.name}</button>
                                  <button onClick={() => deleteCustomTemplate(i)} className="text-gray-600 hover:text-red-400 px-1.5 text-xs">×</button>
                                </div>
                              ))}
                              <div className="border-t border-brand-border/50 my-1" />
                              <button onClick={saveCurrentAsTemplate} disabled={!reply.trim()}
                                className="w-full text-left px-2.5 py-1.5 rounded hover:bg-brand-input text-xs text-accent disabled:opacity-40">+ Mevcut cevabı şablon yap</button>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {active?.customer_email && (
                        <span className="text-[10px] text-gray-500 hidden sm:inline" title={active.customer_email}>📧 müşteriye e-posta gider</span>
                      )}
                      <button onClick={() => sendReply()} disabled={sending || (reply.trim().length < 1 && !replyImg)}
                        className="btn-primary !text-xs !py-1.5 !px-3 disabled:opacity-40">
                        {sending ? 'Gönderiliyor...' : 'Cevapla →'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
