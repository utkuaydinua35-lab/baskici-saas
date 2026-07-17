import { useEffect } from 'react'

// Kaydedilmemiş değişiklik çubuğu — Shopify'ın imza deseni.
// dirty=true olunca üstten kayarak belirir; Kaydet / Vazgeç + Cmd/Ctrl+S.
export default function SaveBar({ dirty, busy, onSave, onDiscard }) {
  useEffect(() => {
    if (!dirty) return
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        if (!busy) onSave()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dirty, busy, onSave])

  return (
    <div className={`fixed top-0 left-0 right-0 z-[90] transition-transform duration-300 ${
      dirty ? 'translate-y-0' : '-translate-y-full'}`}>
      <div className="bg-panel-ink text-white px-4 py-2.5 flex items-center gap-3 shadow-lg">
        <span className="text-sm flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          Kaydedilmemiş değişiklikleriniz var
        </span>
        <span className="hidden sm:inline text-[11px] text-white/50">⌘S ile kaydet</span>
        <div className="ml-auto flex gap-2">
          <button onClick={onDiscard} disabled={busy}
            className="px-3 py-1.5 rounded-lg text-xs text-white/80 hover:text-white border border-white/25 disabled:opacity-50">
            Vazgeç
          </button>
          <button onClick={onSave} disabled={busy}
            className="px-4 py-1.5 rounded-lg text-xs font-medium bg-panel-accent hover:bg-emerald-500/100 disabled:opacity-50">
            {busy ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
      </div>
    </div>
  )
}
