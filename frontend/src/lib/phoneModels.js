// Telefon modeli listesi (baseline katalog dahil) — datalist/dropdown için.
// Tek seferlik çekilip modül düzeyinde cache'lenir.
import { useEffect, useState } from 'react'
import { api } from './api'

let _cache = null

export function usePhoneModels() {
  const [models, setModels] = useState(_cache || [])
  useEffect(() => {
    if (_cache) return
    api.get('/api/phone-models?include_baseline=true')
      .then(r => {
        const names = (r.items || []).map(m => m.display_name).filter(Boolean)
        _cache = [...new Set(names)].sort((a, b) => a.localeCompare(b, 'tr'))
        setModels(_cache)
      })
      .catch(() => {})
  }, [])
  return models
}
