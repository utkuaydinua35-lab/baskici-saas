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

export default function DestekPage() {
  const [threads, setThreads] = useState([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [active, setActive] = useState(null)        // detay (mesajlarla)
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)
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

  const openThread = async (id) => {
    try {
      const t = await api.get(`/api/support/threads/${id}`)
      setActive(t)
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

  const sendReply = async () => {
    if (!active || reply.trim().length < 1) return
    setSending(true)
    try {
      const updated = await api.post(`/api/support/threads/${active.id}/reply`, { message: reply.trim() })
      setActive(updated)
      setReply('')
      loadThreads()
    } catch (e) {
      setError(e.detail || 'Cevap gönderilemedi')
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
    <div className="max-w-5xl">
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

              <div className="flex-1 overflow-y-auto space-y-2 mb-3 max-h-[420px]">
                {(active.messages || []).map(m => {
                  const mine = m.sender === 'admin'
                  return (
                    <div key={m.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-xl px-3 py-2 ${
                        mine ? 'bg-emerald-500/15 text-emerald-100' : 'bg-white/5 text-gray-200'
                      }`}>
                        <div className="text-[10px] opacity-60 mb-0.5">{mine ? 'Sen' : 'Müşteri'} · {fmt(m.created_at)}</div>
                        <div className="text-sm whitespace-pre-wrap leading-relaxed">{m.body}</div>
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
                  <textarea value={reply} onChange={e => setReply(e.target.value)} rows={3}
                    placeholder="Cevabını yaz... (müşteri takip sayfasında görecek)"
                    className="w-full bg-brand-input border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100 resize-y focus:outline-none focus:border-white/25"
                    onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendReply() }} />
                  <div className="flex justify-between items-center mt-2">
                    <span className="text-[10px] text-gray-600">⌘/Ctrl + Enter ile gönder</span>
                    <button onClick={sendReply} disabled={sending || reply.trim().length < 1}
                      className="btn-primary !text-xs !py-1.5 !px-3 disabled:opacity-40">
                      {sending ? 'Gönderiliyor...' : 'Cevapla →'}
                    </button>
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
