import { createContext, useCallback, useContext, useRef, useState } from 'react'

// Toast bildirimleri — sağ altta belirir, otomatik kaybolur (Shopify hissi).
// Kullanım: const toast = useToast(); toast.success('Kaydedildi')
const ToastContext = createContext(null)

const STYLES = {
  // Koyu temada okunurluk: success teal dolgu + koyu metin (btn-primary ile aynı dil)
  success: 'bg-panel-accent text-[#04130d] font-medium',
  error: 'bg-red-600 text-white',
  info: 'bg-panel-card text-panel-ink border border-panel-border',
}
const ICONS = { success: '✓', error: '✕', info: 'ℹ' }

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const push = useCallback((kind, text) => {
    const id = ++idRef.current
    setToasts(t => [...t, { id, kind, text }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), kind === 'error' ? 5000 : 3000)
  }, [])

  const api = {
    success: (t) => push('success', t),
    error: (t) => push('error', t),
    info: (t) => push('info', t),
  }

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[100] space-y-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id}
            className={`toast-in pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-lg text-sm ${STYLES[t.kind]}`}
            onClick={() => setToasts(list => list.filter(x => x.id !== t.id))}>
            <span className="font-semibold">{ICONS[t.kind]}</span>
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast, ToastProvider içinde kullanılmalı')
  return ctx
}
