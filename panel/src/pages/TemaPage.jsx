import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'

// Tema Kütüphanesi (Shopify tarzı) — yayındaki tema + taslak temalar.
// Özelleştir → /tema/duzenle tam ekran editörü açar (taslaklar ?taslak=key ile).
// Taslaklar yayını etkilemeden düzenlenir; Yayınla ile takas edilir
// (eski yayın "Önceki yayın" taslağı olarak saklanır — geri dönülebilir).
export default function TemaPage() {
  const { storeId } = useStore()
  const navigate = useNavigate()
  const toast = useToast()
  const [live, setLive] = useState(null)
  const [drafts, setDrafts] = useState([])
  const [presets, setPresets] = useState([])
  const [busy, setBusy] = useState(false)
  const [renaming, setRenaming] = useState(null)  // {key, name}

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const [t, d] = await Promise.all([
        api.get(`/api/store-settings/${storeId}/theme`),
        api.get(`/api/store-settings/${storeId}/theme/drafts`),
      ])
      setLive(t)
      setDrafts(d.drafts.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')))
      api.get(`/api/store-settings/${storeId}/theme/presets`)
        .then(setPresets).catch(() => {})
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Temalar yüklenemedi')
    }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const newDraft = async (name, theme) => {
    setBusy(true)
    try {
      const key = `taslak-${Date.now().toString(36)}`
      await api.put(`/api/store-settings/${storeId}/theme/drafts/${key}`, { name, theme })
      toast.success(`"${name}" taslağı oluşturuldu`)
      navigate(`/tema/duzenle?taslak=${key}`)
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Taslak oluşturulamadı')
    } finally { setBusy(false) }
  }

  const publish = async (d) => {
    if (!window.confirm(`"${d.name}" yayına alınacak — vitrindeki tema değişir. `
        + `Şu anki yayın, taslak olarak saklanır. Devam?`)) return
    setBusy(true)
    try {
      await api.post(`/api/store-settings/${storeId}/theme/drafts/${d.key}/publish`)
      toast.success('Tema yayında ✓')
      await load()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Yayınlanamadı')
    } finally { setBusy(false) }
  }

  const remove = async (d) => {
    if (!window.confirm(`"${d.name}" taslağı kalıcı olarak silinecek. Emin misiniz?`)) return
    setBusy(true)
    try {
      await api.del(`/api/store-settings/${storeId}/theme/drafts/${d.key}`)
      await load()
    } catch { toast.error('Silinemedi') }
    finally { setBusy(false) }
  }

  const rename = async () => {
    if (!renaming) return
    setBusy(true)
    try {
      await api.put(`/api/store-settings/${storeId}/theme/drafts/${renaming.key}`,
        { name: renaming.name, theme: drafts.find(x => x.key === renaming.key)?.theme })
      setRenaming(null)
      await load()
    } catch { toast.error('Ad değiştirilemedi') }
    finally { setBusy(false) }
  }

  if (!live) return <p className="text-sm text-panel-muted">Yükleniyor…</p>

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Tema</h1>
        <p className="text-xs text-panel-muted mt-1">
          Yayındaki temayı özelleştirin veya taslak temalar üzerinde çalışın —
          taslaklar siz yayınlayana kadar vitrini etkilemez.
        </p>
      </div>

      {/* Yayındaki tema */}
      <section>
        <h2 className="text-sm font-semibold mb-2">Yayındaki tema</h2>
        <div className="card !p-4 flex items-center gap-4 border-emerald-200">
          <ThemeSwatch theme={live} size="lg" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">Mağaza Teması</span>
              <span className="text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-medium">
                ● Yayında
              </span>
            </div>
            <p className="text-xs text-panel-muted mt-0.5">
              {live.sections?.length ?? 0} anasayfa bölümü · {live.font}
            </p>
          </div>
          <button onClick={() => navigate('/tema/duzenle')}
            className="px-4 py-2 rounded-xl text-xs font-medium bg-panel-accent text-white">
            Özelleştir
          </button>
        </div>
      </section>

      {/* Taslaklar */}
      <section>
        <div className="flex items-center mb-2">
          <h2 className="text-sm font-semibold">Taslak temalar ({drafts.length})</h2>
        </div>
        <div className="space-y-2">
          {drafts.map(d => (
            <div key={d.key} className="card !p-4 flex items-center gap-4">
              <ThemeSwatch theme={d.theme} />
              <div className="flex-1 min-w-0">
                {renaming?.key === d.key ? (
                  <div className="flex gap-1.5">
                    <input className="input !py-1 text-xs" value={renaming.name} maxLength={80} autoFocus
                      onChange={e => setRenaming(r => ({ ...r, name: e.target.value }))}
                      onKeyDown={e => e.key === 'Enter' && rename()} />
                    <button onClick={rename} disabled={busy} className="btn-ghost !py-1 text-xs">✓</button>
                    <button onClick={() => setRenaming(null)} className="btn-ghost !py-1 text-xs">×</button>
                  </div>
                ) : (
                  <button onClick={() => setRenaming({ key: d.key, name: d.name })}
                    className="font-medium text-sm truncate hover:underline text-left"
                    title="Adı değiştirmek için tıklayın">
                    {d.name} ✏️
                  </button>
                )}
                <p className="text-xs text-panel-muted mt-0.5">
                  {d.theme.sections?.length ?? 0} bölüm
                  {d.updated_at && ` · ${new Date(d.updated_at).toLocaleString('tr-TR')}`}
                </p>
              </div>
              <button onClick={() => navigate(`/tema/duzenle?taslak=${d.key}`)}
                className="btn-ghost !py-1.5 text-xs">Düzenle</button>
              <button onClick={() => publish(d)} disabled={busy}
                className="px-3 py-1.5 rounded-xl text-xs font-medium bg-emerald-600 text-white disabled:opacity-40">
                🚀 Yayınla
              </button>
              <button onClick={() => remove(d)} disabled={busy}
                className="text-red-400 hover:text-red-600 text-xs px-1">Sil</button>
            </div>
          ))}
          {drafts.length === 0 && (
            <div className="card text-center !p-6 text-xs text-panel-muted">
              Taslak yok — aşağıdan yayındaki temanın kopyasıyla veya bir şablonla başlayın.
            </div>
          )}
        </div>
      </section>

      {/* Yeni taslak */}
      <section>
        <h2 className="text-sm font-semibold mb-2">Yeni taslak oluştur</h2>
        <div className="flex gap-2 flex-wrap">
          <button disabled={busy}
            onClick={() => newDraft(`Kopya — ${new Date().toLocaleDateString('tr-TR')}`, live)}
            className="card !p-3 text-left hover:border-panel-accent transition disabled:opacity-50">
            <div className="text-sm font-medium">📋 Yayındaki temanın kopyası</div>
            <p className="text-[11px] text-panel-muted mt-0.5">
              Mevcut temayı bozmadan üzerinde deneme yapın.
            </p>
          </button>
          {presets.map(pr => (
            <button key={pr.key} disabled={busy}
              onClick={() => newDraft(pr.label, { ...pr.theme, logo_url: live.logo_url, favicon_url: live.favicon_url, logo_width: live.logo_width, whatsapp: live.whatsapp, footer: live.footer })}
              className="card !p-3 text-left hover:border-panel-accent transition disabled:opacity-50">
              <div className="flex items-center gap-2 text-sm font-medium">
                <span className="flex gap-1">
                  {[pr.colors.primary, pr.colors.accent, pr.colors.bg].map((c2, i) => (
                    <span key={i} className="w-3.5 h-3.5 rounded-full border border-panel-border"
                      style={{ background: c2 }} />
                  ))}
                </span>
                {pr.label} şablonu
              </div>
              <p className="text-[11px] text-panel-muted mt-0.5 max-w-56">{pr.description}</p>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-panel-muted mt-2">
          Şablondan oluşturulan taslakta logo, WhatsApp ve footer bilgileriniz korunur.
        </p>
      </section>
    </div>
  )
}

// Tema renklerinden mini kart önizlemesi.
function ThemeSwatch({ theme, size = 'md' }) {
  const c = theme.colors || {}
  return (
    <div className={`${size === 'lg' ? 'w-20 h-14' : 'w-16 h-12'} rounded-xl border border-panel-border overflow-hidden shrink-0 flex flex-col`}
      style={{ background: c.bg || '#fff' }}>
      <div className="h-2.5" style={{ background: c.primary || '#111' }} />
      <div className="flex-1 flex items-center justify-center gap-1 px-1.5">
        <span className="w-3 h-3 rounded-full" style={{ background: c.accent || '#999' }} />
        <span className="flex-1 h-1.5 rounded-full opacity-30" style={{ background: c.primary || '#111' }} />
      </div>
    </div>
  )
}
