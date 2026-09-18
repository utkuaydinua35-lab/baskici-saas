import { useEffect, useState } from 'react'
import { api, setToken, fetchYetkili } from '../lib/api'
import { useToast } from '../components/Toast'
import { mutlak, uygulamaYolu } from '../lib/taban'

function fmtDate(d) {
  if (!d) return '—'
  try { return new Date(d).toLocaleDateString('tr-TR') } catch { return d }
}

export default function PlatformPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = async () => {
    setLoading(true)
    try { const r = await api.get('/api/platform/tenants'); setItems(r.items || []) }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const approve = async (t) => {
    try { await api.patch(`/api/platform/tenants/${t.id}`, { is_approved: true }); toast.success('Atölye onaylandı'); load() }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Onaylanamadı') }
  }

  return (
    <div className="mx-auto max-w-[1100px]">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🏢 Platform — Atölyeler</h1>
          <p className="text-sm text-gray-500 mt-1">{items.length} atölye · white-label kiralama yönetimi</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary !text-sm">+ Yeni Atölye</button>
      </div>

      {loading ? (
        <div className="card"><div className="skeleton h-5 w-48 rounded" /></div>
      ) : (
        <div className="card !p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="tbl text-sm">
              <thead>
                <tr>
                  <th>Atölye</th>
                  <th>Plan</th>
                  <th>Abonelik</th>
                  <th className="!text-center">Kullanıcı</th>
                  <th className="!text-center">Sipariş</th>
                  <th className="!text-center">Durum</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map(t => {
                  const expired = t.active_until && new Date(t.active_until) < new Date()
                  return (
                    <tr key={t.id}>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full shrink-0" style={{ background: t.brand_color || '#14b8a6' }} />
                          <div className="min-w-0">
                            <div className="text-gray-100">{t.app_name || t.name}</div>
                            <div className="text-[10px] text-gray-500 font-mono">{t.slug}</div>
                            {!t.is_approved && (t.signup_ip || t.owner_email) && (
                              <div className="text-[10px] text-amber-300/70 mt-0.5">
                                {t.owner_email && <span>{t.owner_email}</span>}
                                {t.signup_ip && <span> · IP {t.signup_ip}</span>}
                                {t.signup_device && <span> · {t.signup_device}</span>}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-gray-300">{t.plan}</td>
                      <td className={`px-4 py-2.5 text-xs ${expired ? 'text-red-300' : 'text-gray-400'}`}>{fmtDate(t.active_until)}</td>
                      <td className="px-4 py-2.5 text-center text-gray-300">{t.user_count}</td>
                      <td className="px-4 py-2.5 text-center text-gray-400">{t.order_count}</td>
                      <td className="px-4 py-2.5 text-center">
                        <div className="flex items-center justify-center gap-1 flex-wrap">
                          {!t.is_approved && <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300">onay bekliyor</span>}
                          {t.is_active
                            ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">aktif</span>
                            : <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-300">pasif</span>}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-right whitespace-nowrap">
                        {!t.is_approved && (
                          <button onClick={() => approve(t)} className="!text-xs px-2 py-1 mr-1 rounded-lg border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10">✓ Onayla</button>
                        )}
                        <button onClick={() => setEditing(t)} className="btn-secondary !text-xs">Düzenle</button>
                      </td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-500 text-sm">Henüz atölye yok.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <TamYedek />
      <Backups />

      {showCreate && <CreateTenant onClose={() => setShowCreate(false)} onDone={() => { setShowCreate(false); load() }} />}
      {editing && <EditTenant tenant={editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); load() }} />}
    </div>
  )
}

function fmtSize(b) {
  if (!b) return '—'
  const mb = b / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(b / 1024)} KB`
}
function fmtDateTime(d) {
  if (!d) return '—'
  try { return new Date(d).toLocaleString('tr-TR') } catch { return d }
}

// Tam yedek = veritabani + tasarim dosyalari, tek arsivde, tek komutla geri
// yuklenebilir. ⚠ Gecelik yedek yalniz VERITABANINI aliyor ve AYNI DISKTE
// duruyor; disk olurse hem veri hem yedek gider ve 6+ GB tasarim dosyasi
// kalici olarak kaybolur. Bu arsiv disari (kendi diskine) indirilmek icindir.
function TamYedek() {
  const toast = useToast()
  const [d, setD] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try { setD(await api.get('/api/platform/tam-yedek')) } catch { setD({ items: [] }) }
  }
  useEffect(() => { load() }, [])

  const runNow = async () => {
    setBusy(true)
    toast.success('Yedek alınıyor — GB\'larca veri, birkaç dakika sürebilir.')
    try { await api.post('/api/platform/tam-yedek', {}); await load(); toast.success('Tam yedek hazır') }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Yedek alınamadı') }
    finally { setBusy(false) }
  }

  // ⚠ fetch+blob() KULLANILMIYOR: 5 GB'i bellege alip sekmeyi cokertir.
  // Kisa omurlu imzali jetonla dogrudan link — tarayici diske akitir.
  const download = async (name) => {
    try {
      const r = await api.post(`/api/platform/tam-yedek/${encodeURIComponent(name)}/indirme-jetonu`, {})
      const u = mutlak(`/api/platform/tam-yedek/${encodeURIComponent(name)}/download?jeton=${encodeURIComponent(r.jeton)}`)
      const a = document.createElement('a'); a.href = u; a.download = name
      document.body.appendChild(a); a.click(); a.remove()
    } catch { toast.error('İndirme bağlantısı alınamadı') }
  }

  if (!d) return null
  const items = d.items || []
  // Bayatlık İNDİRMEYE göre: sunucudaki arşiv disk ölünce onunla gider.
  const yas = d.disari_yas_gun

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">📦 Tam Yedek (veritabanı + dosyalar)</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Tek arşiv, tek komutla geri yüklenir · son {d.keep} tanesi saklanır
            {d.haric?.length ? ` · ${d.haric.join(', ')} hariç (yeniden üretilir)` : ''}
          </p>
        </div>
        <button onClick={runNow} disabled={busy} className="btn-primary !text-sm disabled:opacity-50">
          {busy ? 'Alınıyor…' : '+ Tam Yedek Al'}
        </button>
      </div>

      {d.bayat && (
        <div className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          <b>⚠ Kendi diskinde güncel bir kopyan yok.</b>{' '}
          {yas == null
            ? 'Tam yedek hiç indirilmemiş.'
            : `En son tam yedek ${Math.floor(yas)} gün önce indirildi.`}{' '}
          Sunucu diski ölürse sunucudaki arşiv de onunla gider — tasarım dosyaları
          kalıcı olarak kaybolur. Tam yedek alıp kendi diskine indir.
          {d.esik_gun ? ` (${d.esik_gun} günü geçince Telegram'dan da hatırlatılır.)` : ''}
        </div>
      )}

      <div className="card !p-0 overflow-hidden">
        {items.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            Henüz tam yedek yok. "Tam Yedek Al" ile ilkini oluştur.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-brand-border text-left text-[11px] text-gray-500 uppercase">
                <th className="px-4 py-2.5 font-medium">Dosya</th>
                <th className="px-4 py-2.5 font-medium">Boyut</th>
                <th className="px-4 py-2.5 font-medium">Tarih</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {items.map(b => (
                <tr key={b.name} className="border-b border-brand-border/40 hover:bg-brand-input/40">
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-300">
                    {b.name}
                    {b.sha256 && (
                      <div className="text-[10px] text-gray-600 mt-0.5">sha256 {b.sha256.slice(0, 16)}…</div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-gray-400">{fmtSize(b.size)}</td>
                  <td className="px-4 py-2.5 text-gray-400 text-xs">{fmtDateTime(b.created_at)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => download(b.name)} className="btn-secondary !text-xs">⬇ İndir</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="mt-3 text-[11px] text-gray-500 leading-relaxed">
        <b className="text-gray-400">Geri yükleme:</b> arşivin içinde <code>GERI-YUKLE.sh</code> ve
        <code> BENIOKU.txt</code> var. Sunucuda root olarak:{' '}
        <code className="text-gray-400">tar -xf dosya.tar GERI-YUKLE.sh &amp;&amp; sudo bash GERI-YUKLE.sh dosya.tar --onayliyorum</code>.
        Onay kelimesi yazılmazsa hiçbir şeye dokunmaz.
        <br />
        <b className="text-gray-400">Büyük dosya:</b> tarayıcı indirmesi yarıda kesilirse
        sunucudan doğrudan çekmek daha sağlam:{' '}
        <code className="text-gray-400">rsync -avP baskici:/srv/baskici/backups/DOSYA.tar .</code>
      </div>
    </div>
  )
}

function Backups() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [keep, setKeep] = useState(7)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try { const r = await api.get('/api/platform/backups'); setItems(r.items || []); setKeep(r.keep || 7) }
    catch {} finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const runNow = async () => {
    setBusy(true)
    try { await api.post('/api/platform/backups', {}); toast.success('Yedek alındı'); load() }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Yedek alınamadı') }
    finally { setBusy(false) }
  }

  const download = async (name) => {
    try {
      const res = await fetchYetkili(mutlak(`/api/platform/backups/${encodeURIComponent(name)}/download`))
      if (!res.ok) throw new Error()
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = name; a.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('İndirilemedi') }
  }

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">💾 Veritabanı Yedekleri</h2>
          <p className="text-xs text-gray-500 mt-0.5">Her gece 03:30 otomatik · son {keep} yedek saklanır</p>
        </div>
        <button onClick={runNow} disabled={busy} className="btn-secondary !text-sm disabled:opacity-50">
          {busy ? 'Alınıyor…' : '+ Yedek Al'}
        </button>
      </div>
      <div className="card !p-0 overflow-hidden">
        {loading ? (
          <div className="p-6"><div className="skeleton h-4 w-40 rounded" /></div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">Henüz yedek yok. "Yedek Al" ile ilkini oluştur.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-brand-border text-left text-[11px] text-gray-500 uppercase">
                <th className="px-4 py-2.5 font-medium">Dosya</th>
                <th className="px-4 py-2.5 font-medium">Boyut</th>
                <th className="px-4 py-2.5 font-medium">Tarih</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {items.map(b => (
                <tr key={b.name} className="border-b border-brand-border/40 hover:bg-brand-input/40">
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-300">{b.name}</td>
                  <td className="px-4 py-2.5 text-gray-400">{fmtSize(b.size)}</td>
                  <td className="px-4 py-2.5 text-gray-400 text-xs">{fmtDateTime(b.created_at)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => download(b.name)} className="btn-secondary !text-xs">⬇ İndir</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4 overflow-y-auto"
      onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-100">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{label}</span>{children}</label>
}

function CreateTenant({ onClose, onDone }) {
  const toast = useToast()
  const [f, setF] = useState({ tenant_name: '', owner_email: '', owner_password: '', owner_name: '', plan: 'trial', active_until: '', brand_color: '#14b8a6', app_name: '' })
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setF(s => ({ ...s, [k]: v }))

  const submit = async () => {
    if (!f.tenant_name.trim() || !f.owner_email.trim() || f.owner_password.length < 6) {
      toast.error('Atölye adı, e-posta ve en az 6 haneli şifre gerekli'); return
    }
    setBusy(true)
    try {
      await api.post('/api/platform/tenants', {
        ...f,
        active_until: f.active_until || null,
        brand_color: f.brand_color || null,
        app_name: f.app_name || null,
      })
      toast.success('Atölye oluşturuldu')
      onDone()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Oluşturulamadı')
    } finally { setBusy(false) }
  }

  return (
    <Modal title="Yeni Atölye" onClose={onClose}>
      <Field label="Atölye adı"><input className="input w-full" value={f.tenant_name} onChange={e => set('tenant_name', e.target.value)} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Plan"><input className="input w-full" value={f.plan} onChange={e => set('plan', e.target.value)} placeholder="trial / pro..." /></Field>
        <Field label="Abonelik bitiş"><input type="date" className="input w-full" value={f.active_until} onChange={e => set('active_until', e.target.value)} /></Field>
      </div>
      <div className="border-t border-brand-border my-2 pt-2 text-[11px] text-gray-500">Sahip (owner) kullanıcı</div>
      <Field label="Sahip e-posta"><input className="input w-full" value={f.owner_email} onChange={e => set('owner_email', e.target.value)} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Sahip adı"><input className="input w-full" value={f.owner_name} onChange={e => set('owner_name', e.target.value)} /></Field>
        <Field label="Şifre (min 6)"><input type="text" className="input w-full" value={f.owner_password} onChange={e => set('owner_password', e.target.value)} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Accent rengi"><input type="color" className="w-full h-9 rounded-lg bg-transparent border border-brand-border p-0.5" value={f.brand_color} onChange={e => set('brand_color', e.target.value)} /></Field>
        <Field label="Uygulama adı"><input className="input w-full" value={f.app_name} onChange={e => set('app_name', e.target.value)} /></Field>
      </div>
      <button onClick={submit} disabled={busy} className="btn-primary !text-sm w-full mt-1 disabled:opacity-50">{busy ? 'Oluşturuluyor…' : 'Oluştur'}</button>
    </Modal>
  )
}

function EditTenant({ tenant, onClose, onDone }) {
  const toast = useToast()
  const [f, setF] = useState({
    name: tenant.name || '', plan: tenant.plan || 'trial', is_active: tenant.is_active,
    is_approved: tenant.is_approved !== false,
    active_until: tenant.active_until ? tenant.active_until.slice(0, 10) : '',
    brand_color: tenant.brand_color || '#14b8a6', app_name: tenant.app_name || '',
  })
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setF(s => ({ ...s, [k]: v }))

  const removeTenant = async () => {
    const typed = window.prompt(`Bu atölyeyi ve TÜM verisini (profiller, siparişler, kalıplar, stok, dosyalar) kalıcı silmek üzeresin.\nOnaylamak için atölye adını yaz:\n\n${tenant.name}`)
    if (typed == null) return
    if (typed.trim() !== (tenant.name || '').trim()) { toast.error('Ad eşleşmedi — silme iptal edildi'); return }
    setBusy(true)
    try { await api.del(`/api/platform/tenants/${tenant.id}`); toast.success('Atölye silindi'); onDone() }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Silinemedi'); setBusy(false) }
  }

  const submit = async () => {
    setBusy(true)
    try {
      await api.patch(`/api/platform/tenants/${tenant.id}`, {
        name: f.name, plan: f.plan, is_active: f.is_active, is_approved: f.is_approved,
        active_until: f.active_until || null,
        clear_active_until: !f.active_until,
        brand_color: f.brand_color || null, app_name: f.app_name || null,
      })
      toast.success('Güncellendi')
      onDone()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  return (
    <Modal title={`Atölye — ${tenant.name}`} onClose={onClose}>
      <Field label="Atölye adı"><input className="input w-full" value={f.name} onChange={e => set('name', e.target.value)} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Plan"><input className="input w-full" value={f.plan} onChange={e => set('plan', e.target.value)} /></Field>
        <Field label="Abonelik bitiş"><input type="date" className="input w-full" value={f.active_until} onChange={e => set('active_until', e.target.value)} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Accent rengi"><input type="color" className="w-full h-9 rounded-lg bg-transparent border border-brand-border p-0.5" value={f.brand_color} onChange={e => set('brand_color', e.target.value)} /></Field>
        <Field label="Uygulama adı"><input className="input w-full" value={f.app_name} onChange={e => set('app_name', e.target.value)} /></Field>
      </div>
      <label className="flex items-center gap-2 mb-2 cursor-pointer">
        <input type="checkbox" checked={f.is_approved} onChange={e => set('is_approved', e.target.checked)} className="accent-accent" />
        <span className="text-sm text-gray-200">Onaylı (kapatılırsa giriş "onay aşamasında" olur)</span>
      </label>
      <label className="flex items-center gap-2 mb-4 cursor-pointer">
        <input type="checkbox" checked={f.is_active} onChange={e => set('is_active', e.target.checked)} className="accent-accent" />
        <span className="text-sm text-gray-200">Aktif (kapatılırsa giriş engellenir)</span>
      </label>
      <button onClick={submit} disabled={busy} className="btn-primary !text-sm w-full disabled:opacity-50">{busy ? 'Kaydediliyor…' : 'Kaydet'}</button>

      <div className="mt-5 pt-4 border-t border-brand-border">
        <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">Profiller</div>
        <TenantProfiles tenantId={tenant.id} />
      </div>

      <div className="mt-5 pt-4 border-t border-red-500/20">
        <div className="text-xs uppercase tracking-wide text-red-400/80 mb-2">Tehlikeli bölge</div>
        <button onClick={removeTenant} disabled={busy}
          className="w-full text-sm px-3 py-2 rounded-lg border border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50 transition-colors">
          🗑 Atölyeyi tamamen sil
        </button>
        <p className="text-[10px] text-gray-600 mt-1">Tüm profiller, siparişler, kalıplar, stok ve dosyalar kalıcı silinir. Geri alınamaz.</p>
      </div>
    </Modal>
  )
}

function TenantProfiles({ tenantId }) {
  const toast = useToast()
  const [users, setUsers] = useState(null)
  const load = () => api.get(`/api/platform/tenants/${tenantId}/users`)
    .then(r => setUsers(r.items || [])).catch(() => setUsers([]))
  useEffect(() => { load() }, [tenantId])

  const toggle = async (u) => {
    try { await api.patch(`/api/platform/users/${u.id}`, { is_active: !u.is_active }); load() }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Güncellenemedi') }
  }
  const del = async (u) => {
    if (!confirm(`"${u.full_name || u.email}" profili silinsin mi?\nBu işlem geri alınamaz.`)) return
    try { await api.del(`/api/platform/users/${u.id}`); toast.success('Profil silindi'); load() }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Silinemedi') }
  }
  const impersonate = async (u) => {
    if (!confirm(`"${u.full_name || u.email}" hesabına giriş yapılacak.\nKendi oturumun kapanır; geri dönmek için tekrar giriş yaparsın. Devam?`)) return
    try {
      const r = await api.post(`/api/platform/users/${u.id}/impersonate`, {})
      setToken(r.access_token)
      window.location.href = uygulamaYolu('/')
    } catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Giriş yapılamadı') }
  }

  if (users === null) return <p className="text-xs text-gray-500 py-2">Profiller yükleniyor…</p>
  if (users.length === 0) return <p className="text-xs text-gray-500 py-2">Profil yok.</p>
  return (
    <div className="space-y-1.5 max-h-72 overflow-y-auto">
      {users.map(u => (
        <div key={u.id} className="flex items-center gap-2 bg-brand-input/40 rounded-lg px-2.5 py-2">
          <div className="flex-1 min-w-0">
            <div className="text-sm text-gray-200 truncate flex items-center gap-1">
              {u.full_name || u.email}
              {u.is_platform_admin && <span className="text-[9px] px-1 rounded bg-purple-500/20 text-purple-300">platform</span>}
              {u.role === 'owner' && <span className="text-[9px] px-1 rounded bg-blue-500/20 text-blue-300">sahip</span>}
              {!u.is_active && <span className="text-[9px] px-1 rounded bg-red-500/20 text-red-300">engelli</span>}
            </div>
            <div className="text-[10px] text-gray-500 truncate">{u.email}</div>
            {(u.signup_ip || u.signup_device) && (
              <div className="text-[10px] text-gray-600 truncate" title={u.signup_user_agent || ''}>
                Kayıt: {u.signup_ip || '?'}{u.signup_device ? ` · ${u.signup_device}` : ''}
              </div>
            )}
          </div>
          {!u.is_platform_admin && (
            <>
              {u.is_active && (
                <button onClick={() => impersonate(u)}
                  className="text-[11px] px-2 py-1 rounded border border-accent/40 text-accent hover:bg-accent/10 whitespace-nowrap">
                  Bu hesaba gir
                </button>
              )}
              <button onClick={() => toggle(u)}
                className={`text-[11px] px-2 py-1 rounded border whitespace-nowrap ${u.is_active
                  ? 'border-amber-500/30 text-amber-300 hover:bg-amber-500/10'
                  : 'border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10'}`}>
                {u.is_active ? 'Girişi engelle' : 'Girişi aç'}
              </button>
              <button onClick={() => del(u)}
                className="text-[11px] px-2 py-1 rounded border border-red-500/30 text-red-400 hover:bg-red-500/10">Sil</button>
            </>
          )}
        </div>
      ))}
    </div>
  )
}
