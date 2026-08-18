import { useEffect, useRef } from 'react'

// Zengin metin editörü — ürün açıklaması için (kalın/italik/altı-üstü çizili,
// başlık, liste, bağlantı). HTML üretir; sunucu kaydederken beyaz listeyle
// temizler (script/olay/javascript: linki asla saklanmaz).
const BTNS = [
  { cmd: 'bold', label: 'B', title: 'Kalın', cls: 'font-bold' },
  { cmd: 'italic', label: 'I', title: 'İtalik', cls: 'italic' },
  { cmd: 'underline', label: 'U', title: 'Altı çizili', cls: 'underline' },
  { cmd: 'strikeThrough', label: 'S', title: 'Üstü çizili', cls: 'line-through' },
]

export default function RichTextEditor({ value, onChange, placeholder }) {
  const ref = useRef(null)
  const lastHtml = useRef(null)

  // Dış değer değişirse (ürün yüklendi/vazgeçildi) editörü eşitle —
  // kullanıcı yazarken caret zıplamasın diye yalnız farklıysa yaz.
  useEffect(() => {
    if (ref.current && value !== lastHtml.current) {
      ref.current.innerHTML = value || ''
      lastHtml.current = value
    }
  }, [value])

  const emit = () => {
    const html = ref.current?.innerHTML ?? ''
    const cleaned = html === '<br>' ? '' : html
    lastHtml.current = cleaned
    onChange(cleaned)
  }

  const exec = (cmd, arg = null) => {
    ref.current?.focus()
    document.execCommand(cmd, false, arg)
    emit()
  }

  const link = () => {
    const url = window.prompt('Bağlantı adresi (https://… veya /sayfa):', 'https://')
    if (!url) return
    exec('createLink', url)
  }

  return (
    <div className="mt-1 rounded-xl border border-panel-border bg-panel-card overflow-hidden focus-within:border-panel-accent">
      <div className="flex items-center gap-0.5 px-1.5 py-1 border-b border-panel-border bg-panel-input/60 flex-wrap">
        {BTNS.map(b => (
          <button key={b.cmd} type="button" title={b.title}
            onMouseDown={e => { e.preventDefault(); exec(b.cmd) }}
            className={`w-7 h-7 rounded-lg text-xs hover:bg-panel-card ${b.cls}`}>
            {b.label}
          </button>
        ))}
        <span className="w-px h-4 bg-panel-border mx-1" />
        <button type="button" title="Büyük başlık"
          onMouseDown={e => { e.preventDefault(); exec('formatBlock', '<h2>') }}
          className="px-1.5 h-7 rounded-lg text-xs font-semibold hover:bg-panel-card">H2</button>
        <button type="button" title="Küçük başlık"
          onMouseDown={e => { e.preventDefault(); exec('formatBlock', '<h3>') }}
          className="px-1.5 h-7 rounded-lg text-xs font-semibold hover:bg-panel-card">H3</button>
        <button type="button" title="Normal metin"
          onMouseDown={e => { e.preventDefault(); exec('formatBlock', '<p>') }}
          className="px-1.5 h-7 rounded-lg text-xs hover:bg-panel-card">¶</button>
        <span className="w-px h-4 bg-panel-border mx-1" />
        <button type="button" title="Madde listesi"
          onMouseDown={e => { e.preventDefault(); exec('insertUnorderedList') }}
          className="px-1.5 h-7 rounded-lg text-xs hover:bg-panel-card">• Liste</button>
        <button type="button" title="Numaralı liste"
          onMouseDown={e => { e.preventDefault(); exec('insertOrderedList') }}
          className="px-1.5 h-7 rounded-lg text-xs hover:bg-panel-card">1. Liste</button>
        <span className="w-px h-4 bg-panel-border mx-1" />
        <button type="button" title="Bağlantı ekle"
          onMouseDown={e => { e.preventDefault(); link() }}
          className="px-1.5 h-7 rounded-lg text-xs hover:bg-panel-card">🔗 Link</button>
        <button type="button" title="Biçimi temizle"
          onMouseDown={e => { e.preventDefault(); exec('removeFormat'); exec('unlink') }}
          className="px-1.5 h-7 rounded-lg text-xs hover:bg-panel-card ml-auto text-panel-muted">⌫ Temizle</button>
      </div>
      <div ref={ref} contentEditable suppressContentEditableWarning
        onInput={emit} onBlur={emit}
        data-placeholder={placeholder || 'Ürün açıklaması…'}
        className="rte-alan min-h-32 max-h-80 overflow-y-auto px-3 py-2 text-sm outline-none
          [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:text-base [&_h3]:font-semibold
          [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_a]:text-emerald-300 [&_a]:underline
          empty:before:content-[attr(data-placeholder)] before:text-panel-muted/60" />
    </div>
  )
}
