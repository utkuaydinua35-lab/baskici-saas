import { createContext, useCallback, useContext, useState } from 'react'

const ToastContext = createContext(null)

let _idSeq = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const remove = useCallback((id) => {
    setToasts(cur => cur.filter(t => t.id !== id))
  }, [])

  const push = useCallback((message, type = 'info', duration = 3200) => {
    const id = ++_idSeq
    setToasts(cur => [...cur, { id, message, type, leaving: false }])
    if (duration > 0) {
      setTimeout(() => {
        setToasts(cur => cur.map(t => t.id === id ? { ...t, leaving: true } : t))
        setTimeout(() => remove(id), 280)
      }, duration)
    }
    return id
  }, [remove])

  const api = {
    success: (m, d) => push(m, 'success', d),
    error: (m, d) => push(m, 'error', d ?? 4200),
    info: (m, d) => push(m, 'info', d),
    show: push,
  }

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed top-4 right-4 z-[300] flex flex-col gap-2 pointer-events-none max-w-[calc(100vw-2rem)]">
        {toasts.map(t => (
          <div key={t.id}
            onClick={() => { setToasts(cur => cur.map(x => x.id === t.id ? { ...x, leaving: true } : x)); setTimeout(() => remove(t.id), 280) }}
            className={`toast-item pointer-events-auto cursor-pointer flex items-start gap-2.5 min-w-[260px] max-w-sm px-4 py-3 rounded-xl border shadow-lg backdrop-blur-md ${t.leaving ? 'toast-out' : 'toast-in'} ${
              t.type === 'success' ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-200'
              : t.type === 'error' ? 'bg-red-500/15 border-red-500/30 text-red-200'
              : 'bg-brand-card/90 border-brand-border text-gray-200'
            }`}>
            <span className="text-base leading-none mt-0.5">
              {t.type === 'success' ? '✓' : t.type === 'error' ? '⚠️' : 'ℹ️'}
            </span>
            <span className="text-sm leading-snug flex-1">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    // Provider yoksa sessizce konsola dus (cokmesin)
    return { success: console.log, error: console.error, info: console.log, show: console.log }
  }
  return ctx
}
