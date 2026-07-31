import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Ürün yorumları — moderasyon (bekleyen/onaylı/reddedilen).
const TABS = [
  { key: 'pending', label: 'Bekleyen' },
  { key: 'approved', label: 'Onaylı' },
  { key: 'rejected', label: 'Reddedilen' },
]

export default function YorumlarPage() {
  const { storeId } = useStore()
  const [tab, setTab] = useState('pending')
  const [kind, setKind] = useState('review')   // review | question
  const [answers, setAnswers] = useState({})   // {id: yazılan yanıt}
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    if (!storeId) return
    setError('')
    try {
      const r = await api.get(`/api/catalog/reviews?store_id=${storeId}&status=${tab}&kind=${kind}`)
      setItems(r.items || [])
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Yorumlar yüklenemedi')
    }
  }, [storeId, tab, kind])
  useEffect(() => { load() }, [load])

  const moderate = async (id, action) => {
    setBusyId(id)
    try { await api.post(`/api/catalog/reviews/${id}/moderate`, { action }); await load() }
    catch { setError('İşlem başarısız') }
    finally { setBusyId(null) }
  }

  // Soruyu yanıtla — yanıtlanan soru otomatik yayına girer
  const answer = async (id) => {
    const text = (answers[id] || '').trim()
    if (!text) return
    setBusyId(id)
    try {
      await api.post(`/api/catalog/reviews/${id}/moderate`, { action: 'answer', answer: text })
      setAnswers(a => ({ ...a, [id]: '' }))
      await load()
    } catch { setError('Yanıt kaydedilemedi') }
    finally { setBusyId(null) }
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold mr-2">
          {kind === 'question' ? 'Ürün Soruları' : 'Yorumlar'}
        </h1>
        <div className="flex gap-1 bg-panel-input rounded-lg p-0.5 mr-2">
          {[['review', '⭐ Yorumlar'], ['question', '❓ Sorular']].map(([k, l]) => (
            <button key={k} onClick={() => setKind(k)}
              className={`px-2.5 py-1 rounded-md text-xs transition ${kind === k
                ? 'bg-panel-card shadow-sm font-medium' : 'text-panel-muted hover:text-panel-ink'}`}>
              {l}
            </button>
          ))}
        </div>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 rounded-xl text-xs border transition ${tab === t.key
              ? 'border-panel-accent bg-emerald-50 text-emerald-700 font-medium'
              : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
            {t.label}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="space-y-2">
        {items.map(r => (
          <div key={r.id} className="card">
            <div className="flex items-center gap-2 text-sm">
              {r.kind === 'question'
                ? <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-sky-50 text-sky-700">❓ soru</span>
                : <span className="text-amber-500">{'★'.repeat(r.rating || 0)}{'☆'.repeat(5 - (r.rating || 0))}</span>}
              <span className="font-medium">{r.author_name}</span>
              {r.verified && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
                  ✓ doğrulanmış alıcı
                </span>
              )}
              <span className="text-xs text-panel-muted ml-auto">
                {r.created_at ? new Date(r.created_at).toLocaleDateString('tr-TR') : ''}
              </span>
            </div>
            <div className="text-xs text-panel-muted mt-0.5">{r.product_title}</div>
            {r.comment && <p className="text-sm mt-2">{r.comment}</p>}
            {r.kind === 'question' && (
              <div className="mt-2 space-y-1.5">
                {r.answer && (
                  <p className="text-sm bg-panel-input rounded-xl px-3 py-2">
                    <b className="text-xs text-panel-muted">Yanıtınız:</b> {r.answer}
                  </p>
                )}
                <textarea className="input" rows={2}
                  value={answers[r.id] ?? ''}
                  onChange={e => setAnswers(a => ({ ...a, [r.id]: e.target.value }))}
                  placeholder={r.answer ? 'Yanıtı güncelle…' : 'Yanıtınızı yazın — kaydedince ürün sayfasında yayınlanır'} />
                <button onClick={() => answer(r.id)} disabled={busyId === r.id || !(answers[r.id] || '').trim()}
                  className="btn-primary !py-1 text-xs disabled:opacity-50">
                  {busyId === r.id ? 'Kaydediliyor…' : r.answer ? 'Yanıtı Güncelle' : '✉️ Yanıtla ve Yayınla'}
                </button>
              </div>
            )}
            <div className="flex gap-2 mt-3">
              {r.status !== 'approved' && r.kind !== 'question' && (
                <button onClick={() => moderate(r.id, 'approve')} disabled={busyId === r.id}
                  className="px-3 py-1 rounded-lg text-xs bg-emerald-50 text-emerald-700 disabled:opacity-50">
                  Onayla
                </button>
              )}
              {r.status !== 'rejected' && (
                <button onClick={() => moderate(r.id, 'reject')} disabled={busyId === r.id}
                  className="px-3 py-1 rounded-lg text-xs bg-red-50 text-red-700 disabled:opacity-50">
                  Reddet
                </button>
              )}
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <div className="card text-center !p-8 text-sm text-panel-muted">
            {kind === 'question'
              ? (tab === 'pending' ? 'Yanıt bekleyen soru yok.' : 'Bu sekmede soru yok.')
              : (tab === 'pending' ? 'Bekleyen yorum yok.' : 'Bu sekmede yorum yok.')}
          </div>
        )}
      </div>
    </div>
  )
}
