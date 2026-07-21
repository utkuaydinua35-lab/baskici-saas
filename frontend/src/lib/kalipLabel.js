// Kalıp slot etiketi görünüm ayarları (yazı boyutu + her bilginin rengi).
// Tarayıcıda saklanır (localStorage) — cihaz bazlı görünüm tercihi.
const KEY = 'kalip_label_ayar'

export const DEFAULT_LABEL = {
  scale: 1,                 // yazı boyutu çarpanı (0.7 – 2.0)
  colors: {
    order: '#ffffff',       // Sipariş No — beyaz
    code:  '#f9a8d4',       // Tasarım kodu — pembe
    model: '#c4b5fd',       // Telefon modeli — mor
    kilif: '#93c5fd',       // Kılıf rengi — mavi
    slot:  '#9ca3af',       // Slot no — gri
  },
}

export function loadLabelSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (s && typeof s === 'object') {
      return { scale: s.scale || 1, colors: { ...DEFAULT_LABEL.colors, ...(s.colors || {}) } }
    }
  } catch { /* boş */ }
  return { ...DEFAULT_LABEL, colors: { ...DEFAULT_LABEL.colors } }
}

export function saveLabelSettings(s) {
  try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* boş */ }
}

// Telefon modelini kısalt (iPhone/Galaxy vb. atılır → "16 PRO")
export function shortModel(m) {
  if (!m) return ''
  return String(m).replace(/i\s*phone/i, '').replace(/apple/i, '')
    .replace(/galaxy/i, '').replace(/samsung/i, '').trim().toUpperCase()
}

export function kilifText(it) {
  if (it.kilif_rengi) return `Kılıf: ${String(it.kilif_rengi).toUpperCase()}`
  if (it.variation) return `Kılıf: ${String(it.variation).toUpperCase()}`
  return ''
}
