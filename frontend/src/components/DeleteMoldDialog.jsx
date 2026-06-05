import { useState, useEffect } from 'react'
import { api } from '../lib/api'

export default function DeleteMoldDialog({ open, mold, onClose, onDeleted }) {
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (open) { setConfirm(''); setErr(''); setBusy(false) }
  }, [open])

  if (!open || !mold) return null

  const target = (mold.kod || '').toUpperCase()
  const canDelete = confirm.trim().toUpperCase() === target && !busy && target.length > 0

  const handleDelete = async () => {
    if (!canDelete) return
    setBusy(true); setErr('')
    try {
      const data = await api.del(`/api/molds/${mold.id}`)
      onDeleted?.(data)
    } catch (e) {
      setErr(e?.message || 'Silme başarısız')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card max-w-md w-full p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-100 mb-2">Kalıbı Sil</h2>
        <div className="text-sm text-gray-300 space-y-2 mb-4">
          <p><span className="font-mono text-gray-100">{mold.kod}</span> kalıbı kalıcı olarak silinecek.</p>
          <p className="text-amber-300/90 bg-amber-500/10 border border-amber-500/30 rounded px-3 py-2">
            Kalıptaki ürünlerin sipariş durumu <span className="font-semibold">"kalıp bekliyor"</span> olarak güncellenecektir.
          </p>
        </div>
        <label className="block text-sm text-gray-300 mb-1">
          Onaylamak için kalıp kodunu yazın: <span className="font-mono text-gray-100">{mold.kod}</span>
        </label>
        <input
          autoFocus
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder={mold.kod}
          className="input w-full mb-3 font-mono"
          disabled={busy}
          onKeyDown={(e) => { if (e.key === 'Enter' && canDelete) handleDelete() }}
        />
        {err && (
          <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>
        )}
        <div className="flex items-center justify-end gap-2">
          <button onClick={onClose} disabled={busy} className="btn-secondary">Vazgeç</button>
          <button
            onClick={handleDelete}
            disabled={!canDelete}
            className={`px-3 py-1.5 rounded text-sm font-medium ${canDelete ? 'bg-red-600 hover:bg-red-500 text-white' : 'bg-red-900/40 text-red-300/60 cursor-not-allowed'}`}
          >
            {busy ? 'Siliniyor…' : 'Kalıbı Sil'}
          </button>
        </div>
      </div>
    </div>
  )
}
