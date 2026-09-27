// Platform → kiralama işletimi (Faz 3): planlar, tahsilat, havale bilgileri,
// kiracı başına abonelik penceresi. Hesap kuralları backend'de
// (services/abonelik.py); burası yalnız gösterir ve onaylatır.
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from './Toast'

const hata = e => (typeof e?.detail === 'string' ? e.detail : 'İşlem başarısız')

export function fmtTL(v) {
  const n = Number(v || 0)
  return n.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' TL'
}

function fmtGun(d) {
  if (!d) return '—'
  try { return new Date(d + (d.length === 10 ? 'T00:00:00' : '')).toLocaleDateString('tr-TR') } catch { return d }
}

const ASAMA = {
  aktif: ['aktif', 'bg-emerald-500/15 text-emerald-300'],
  ek_sure: ['ek süre', 'bg-amber-500/15 text-amber-300'],
  salt_okunur: ['salt okunur', 'bg-orange-500/15 text-orange-300'],
  askida: ['askıda', 'bg-red-500/15 text-red-300'],
}

export function DurumRozeti({ durum }) {
  if (!durum) return null
  const [ad, cls] = ASAMA[durum.asama] || [durum.asama, 'bg-gray-500/15 text-gray-300']
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap ${cls}`}
      title={durum.mesaj || ''}>
      {ad}{durum.kalan_gun != null && durum.asama !== 'aktif' ? ` · ${durum.kalan_gun} gün` : ''}
    </span>
  )
}

// ─── Planlar ────────────────────────────────────────────────────────────────
export function usePlanlar() {
  const [data, setData] = useState({ items: [], moduller: [] })
  const yukle = () => api.get('/api/platform/plans').then(setData).catch(() => {})
  useEffect(() => { yukle() }, [])
  return [data, yukle]
}

export function PlanlarKarti({ planlar, yenile }) {
  const toast = useToast()
  const [duzen, setDuzen] = useState({})     // plan id → taslak
  const [yeni, setYeni] = useState(null)

  const taslak = p => duzen[p.id] || p
  const degistir = (p, alan, deger) => setDuzen(d => ({ ...d, [p.id]: { ...taslak(p), [alan]: deger } }))
  const kirli = p => !!duzen[p.id]

  const kaydet = async p => {
    const t = taslak(p)
    try {
      await api.patch(`/api/platform/plans/${p.id}`, {
        ad: t.ad, aylik_ucret: String(t.aylik_ucret || 0), komisyon_orani: String(t.komisyon_orani || 0),
        ...(p.kod === 'sahip' ? {} : { moduller: t.moduller, aktif: t.aktif }),
      })
      setDuzen(d => { const n = { ...d }; delete n[p.id]; return n })
      toast.success(`${t.ad} kaydedildi`)
      yenile()
    } catch (e) { toast.error(hata(e)) }
  }

  const olustur = async () => {
    try {
      await api.post('/api/platform/plans', {
        kod: yeni.kod.trim().toLowerCase(), ad: yeni.ad.trim(),
        aylik_ucret: String(yeni.aylik_ucret || 0), komisyon_orani: String(yeni.komisyon_orani || 0),
        moduller: ['magaza'],
      })
      setYeni(null); toast.success('Plan eklendi'); yenile()
    } catch (e) { toast.error(hata(e)) }
  }

  return (
    <div className="card mt-6">
      <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
        <h2 className="text-base font-semibold text-gray-100">💳 Planlar</h2>
        {!yeni && <button onClick={() => setYeni({ kod: '', ad: '', aylik_ucret: '', komisyon_orani: '' })}
          className="btn-secondary !text-xs">+ Plan ekle</button>}
      </div>
      <p className="text-xs text-gray-500 mb-3">
        Fiyat değişikliği <b>sonraki ödemelerden</b> itibaren geçer; alınmış ödemelerin tutarı değişmez.
        Komisyon yalnız vitrin satışından, sipariş toplamı (indirim düşülmüş, KDV + kargo dahil) üzerinden
        alınır; iptal ve iade edilen sipariş düşülür.
      </p>
      <div className="overflow-x-auto">
        <table className="tbl text-sm">
          <thead><tr>
            <th>Plan</th><th>Aylık ücret (TL)</th><th>Komisyon %</th><th>Modüller</th>
            <th className="!text-center">Kiracı</th><th className="!text-center">Satışta</th><th></th>
          </tr></thead>
          <tbody>
            {planlar.items.map(p => {
              const t = taslak(p)
              const sahip = p.kod === 'sahip'
              return (
                <tr key={p.id}>
                  <td className="px-3 py-2">
                    <input className="input !py-1 w-36" value={t.ad} onChange={e => degistir(p, 'ad', e.target.value)} />
                    <div className="text-[10px] text-gray-500 font-mono mt-0.5">{p.kod}</div>
                  </td>
                  <td className="px-3 py-2"><input className="input !py-1 w-28" type="number" min="0" step="0.01"
                    value={t.aylik_ucret} onChange={e => degistir(p, 'aylik_ucret', e.target.value)} /></td>
                  <td className="px-3 py-2"><input className="input !py-1 w-20" type="number" min="0" max="100" step="0.01"
                    value={t.komisyon_orani} onChange={e => degistir(p, 'komisyon_orani', e.target.value)} /></td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {planlar.moduller.map(m => {
                        const acik = t.moduller.includes(m.kod)
                        const kilitli = sahip || m.kod === 'magaza'
                        return (
                          <button key={m.kod} disabled={kilitli}
                            title={m.kod === 'magaza' ? 'Her planda zorunlu' : sahip ? 'Sahip planı sabit' : ''}
                            onClick={() => degistir(p, 'moduller', acik ? t.moduller.filter(x => x !== m.kod) : [...t.moduller, m.kod])}
                            className={`text-[10px] px-2 py-0.5 rounded-full border transition ${acik
                              ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300'
                              : 'border-brand-border text-gray-500'} ${kilitli ? 'opacity-70 cursor-default' : 'hover:border-gray-400'}`}>
                            {m.ad}
                          </button>
                        )
                      })}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-center text-gray-300">{p.kiraci_sayisi}</td>
                  <td className="px-3 py-2 text-center">
                    <input type="checkbox" checked={t.aktif} disabled={sahip}
                      onChange={e => degistir(p, 'aktif', e.target.checked)} className="accent-accent" />
                  </td>
                  <td className="px-3 py-2 text-right">
                    {kirli(p) && (
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => setDuzen(d => { const n = { ...d }; delete n[p.id]; return n })}
                          className="btn-secondary !text-xs">Vazgeç</button>
                        <button onClick={() => kaydet(p)} className="btn-primary !text-xs">Kaydet</button>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
            {yeni && (
              <tr>
                <td className="px-3 py-2">
                  <input className="input !py-1 w-36" placeholder="Ad" value={yeni.ad} onChange={e => setYeni({ ...yeni, ad: e.target.value })} />
                  <input className="input !py-1 w-36 mt-1 font-mono text-xs" placeholder="kod (ör. kurumsal)" value={yeni.kod}
                    onChange={e => setYeni({ ...yeni, kod: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '') })} />
                </td>
                <td className="px-3 py-2"><input className="input !py-1 w-28" type="number" min="0" value={yeni.aylik_ucret}
                  onChange={e => setYeni({ ...yeni, aylik_ucret: e.target.value })} /></td>
                <td className="px-3 py-2"><input className="input !py-1 w-20" type="number" min="0" max="100" value={yeni.komisyon_orani}
                  onChange={e => setYeni({ ...yeni, komisyon_orani: e.target.value })} /></td>
                <td className="px-3 py-2 text-[11px] text-gray-500" colSpan={3}>Modülleri ekledikten sonra seçin.</td>
                <td className="px-3 py-2 text-right">
                  <div className="flex gap-1 justify-end">
                    <button onClick={() => setYeni(null)} className="btn-secondary !text-xs">Vazgeç</button>
                    <button onClick={olustur} disabled={!yeni.ad.trim() || yeni.kod.length < 2}
                      className="btn-primary !text-xs disabled:opacity-50">Ekle</button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Tahsilat özeti: kim ne ödeyecek ────────────────────────────────────────
export function TahsilatKarti({ tazele, onAc }) {
  const [items, setItems] = useState(null)
  useEffect(() => { api.get('/api/platform/tahakkuklar').then(r => setItems(r.items || [])).catch(() => setItems([])) }, [tazele])
  if (items === null) return null
  const ucretli = items.filter(i => Number(i.toplam || 0) > 0)
  const toplam = ucretli.reduce((a, i) => a + Number(i.toplam || 0), 0)
  return (
    <div className="card mt-6">
      <div className="flex items-baseline justify-between mb-1 flex-wrap gap-2">
        <h2 className="text-base font-semibold text-gray-100">🧾 Tahsilat</h2>
        <span className="text-xs text-gray-400">Şimdi tahsil edilecek toplam: <b className="text-gray-100">{fmtTL(toplam)}</b></span>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        Her satır: kiracı şimdi öderse sıradaki ayın sabit ücreti + geçen dönemin vitrin satışının komisyonu.
        Bitiş tarihine göre sıralı; en acil üstte.
      </p>
      {ucretli.length === 0 ? (
        <p className="text-sm text-gray-500 py-4 text-center">Ücretli planda kiracı yok.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="tbl text-sm">
            <thead><tr>
              <th>Kiracı</th><th>Plan</th><th>Bitiş</th><th>Durum</th>
              <th className="!text-right">Sabit</th><th className="!text-right">Komisyon</th><th className="!text-right">Toplam</th><th></th>
            </tr></thead>
            <tbody>
              {ucretli.map(i => (
                <tr key={i.tenant_id}>
                  <td className="px-3 py-2 text-gray-100">{i.ad}<div className="text-[10px] text-gray-500 font-mono">{i.slug}</div></td>
                  <td className="px-3 py-2 text-gray-300">{i.plan_ad}</td>
                  <td className="px-3 py-2 text-xs text-gray-400">{fmtGun(i.active_until)}</td>
                  <td className="px-3 py-2"><DurumRozeti durum={i.durum} /></td>
                  <td className="px-3 py-2 text-right text-gray-300">{fmtTL(i.sabit_ucret)}</td>
                  <td className="px-3 py-2 text-right text-gray-300" title={`Vitrin cirosu ${fmtTL(i.ciro)}`}>{fmtTL(i.komisyon)}</td>
                  <td className="px-3 py-2 text-right text-gray-100 font-medium">{fmtTL(i.toplam)}</td>
                  <td className="px-3 py-2 text-right"><button onClick={() => onAc(i.tenant_id)} className="btn-secondary !text-xs">Aç</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ─── Havale bilgileri (kiracının abonelik sayfasında görünür) ──────────────
export function HavaleKarti() {
  const toast = useToast()
  const [f, setF] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.get('/api/platform/ayarlar/havale').then(setF).catch(() => setF({})) }, [])
  if (!f) return null
  const set = (k, v) => setF(s => ({ ...s, [k]: v }))
  const kaydet = async () => {
    setBusy(true)
    try { setF(await api.put('/api/platform/ayarlar/havale', f)); toast.success('Havale bilgileri kaydedildi') }
    catch (e) { toast.error(hata(e)) } finally { setBusy(false) }
  }
  return (
    <div className="card mt-6">
      <h2 className="text-base font-semibold text-gray-100 mb-1">🏦 Havale bilgileri</h2>
      <p className="text-xs text-gray-500 mb-3">Ücretli plandaki kiracılar abonelik sayfasında bunu görür. Açıklamaya kendi mağaza kodlarını yazmaları istenir.</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="block"><span className="block text-xs text-gray-400 mb-1">Alıcı adı</span>
          <input className="input w-full" maxLength={120} value={f.alici || ''} onChange={e => set('alici', e.target.value)} /></label>
        <label className="block"><span className="block text-xs text-gray-400 mb-1">Banka</span>
          <input className="input w-full" maxLength={80} value={f.banka || ''} onChange={e => set('banka', e.target.value)} /></label>
        <label className="block sm:col-span-2"><span className="block text-xs text-gray-400 mb-1">IBAN</span>
          <input className="input w-full font-mono" maxLength={40} placeholder="TR00 0000 0000 0000 0000 0000 00"
            value={f.iban || ''} onChange={e => set('iban', e.target.value)} /></label>
        <label className="block sm:col-span-2"><span className="block text-xs text-gray-400 mb-1">Ek not (ops.)</span>
          <input className="input w-full" maxLength={300} value={f.aciklama || ''} onChange={e => set('aciklama', e.target.value)}
            placeholder="ör. Ödemeniz 1 iş günü içinde işlenir." /></label>
      </div>
      <button onClick={kaydet} disabled={busy} className="btn-primary !text-sm mt-3 disabled:opacity-50">{busy ? 'Kaydediliyor…' : 'Kaydet'}</button>
    </div>
  )
}

// ─── Kiracı abonelik penceresi: tahakkuk + ödeme alındı + geçmiş ────────────
export function AbonelikModal({ tenantId, onClose, onDegisti }) {
  const toast = useToast()
  const [ay, setAy] = useState(1)
  const [data, setData] = useState(null)
  const [form, setForm] = useState({ yontem: 'havale', referans: '', not: '', fatura_no: '' })
  const [busy, setBusy] = useState(false)

  const yukle = () => api.get(`/api/platform/tenants/${tenantId}/abonelik?ay_sayisi=${ay}`)
    .then(setData).catch(e => toast.error(hata(e)))
  useEffect(() => { yukle() }, [tenantId, ay])

  const th = data?.tahakkuk
  const kaydet = async () => {
    if (!th) return
    const onay = window.confirm(
      `${data.tenant.app_name || data.tenant.name} için ${fmtTL(th.toplam)} ödeme kaydedilecek.\n` +
      `Abonelik ${fmtGun(th.yeni_bitis)} tarihine uzayacak. Onaylıyor musunuz?`)
    if (!onay) return
    setBusy(true)
    try {
      await api.post(`/api/platform/tenants/${tenantId}/odemeler`, {
        yontem: form.yontem, ay_sayisi: ay, beklenen_toplam: th.toplam,
        referans: form.referans || null, not: form.not || null, fatura_no: form.fatura_no || null,
      })
      toast.success('Ödeme kaydedildi, abonelik uzatıldı')
      setForm({ yontem: 'havale', referans: '', not: '', fatura_no: '' })
      await yukle(); onDegisti?.()
    } catch (e) { toast.error(hata(e)); yukle() } finally { setBusy(false) }
  }

  // Fatura çoğu zaman ödemeden sonra kesilir — numara sonradan girilir/düzeltilir
  const faturaGir = async o => {
    const no = window.prompt('Fatura numarası (boş bırakılırsa silinir):', o.fatura_no || '')
    if (no === null) return
    try { await api.patch(`/api/platform/odemeler/${o.id}/fatura`, { fatura_no: no.trim() || null }); await yukle() }
    catch (e) { toast.error(hata(e)) }
  }

  const iptal = async o => {
    if (!window.confirm(`${fmtTL(o.toplam)} tutarındaki ödeme iptal edilecek; abonelik bitişi ${fmtGun(o.onceki_bitis)} tarihine geri dönecek. Emin misiniz?`)) return
    try { await api.post(`/api/platform/odemeler/${o.id}/iptal`); toast.success('Ödeme iptal edildi'); await yukle(); onDegisti?.() }
    catch (e) { toast.error(hata(e)) }
  }

  // Yalnız en son geçerli ödeme iptal edilebilir (backend de zorlar)
  const sonGecerli = data?.odemeler?.filter(o => o.durum === 'odendi')
    .sort((a, b) => (b.yeni_bitis || '').localeCompare(a.yeni_bitis || ''))[0]

  return (
    <div className="fixed inset-0 z-[120] flex items-start justify-center bg-black/60 p-4 overflow-y-auto"
      onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-100">
            Abonelik — {data ? (data.tenant.app_name || data.tenant.name) : '…'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {!data ? <div className="skeleton h-5 w-48 rounded" /> : (<>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm mb-4">
            <span className="text-gray-400">Plan: <b className="text-gray-100">{data.tenant.plan_ad || 'atanmamış'}</b></span>
            <span className="text-gray-400">Bitiş: <b className="text-gray-100">{fmtGun(data.tenant.active_until)}</b></span>
            <DurumRozeti durum={data.tenant.abonelik} />
          </div>

          {data.tahakkuk_hata ? (
            <p className="text-sm text-amber-300 mb-4">{data.tahakkuk_hata}</p>
          ) : th && (
            <div className="rounded-xl border border-brand-border p-4 mb-5">
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <div className="text-xs uppercase tracking-wide text-gray-500">Şimdi ödeme alınırsa</div>
                <label className="text-xs text-gray-400 flex items-center gap-2">Peşin
                  <select className="input !py-1 !w-auto" value={ay} onChange={e => setAy(Number(e.target.value))}>
                    {[1, 2, 3, 6, 12].map(n => <option key={n} value={n}>{n} ay</option>)}
                  </select>
                </label>
              </div>
              <table className="w-full text-sm">
                <tbody>
                  <tr><td className="py-1 text-gray-400">Sabit ücret ({th.ay_sayisi} ay · {fmtGun(th.donem_bas)} – {fmtGun(th.donem_bit)})</td>
                    <td className="py-1 pl-3 text-right text-gray-100 whitespace-nowrap align-top">{fmtTL(th.sabit_ucret)}</td></tr>
                  <tr><td className="py-1 text-gray-400">
                    Komisyon %{Number(th.komisyon_orani)} ·{' '}
                    {th.ciro_bas ? <>vitrin satışı {fmtGun(th.ciro_bas)} – {fmtGun(th.ciro_bit)}: {fmtTL(th.ciro)} ({th.siparis_sayisi} sipariş)</>
                      : <>komisyon dönemi yok (ilk ücretli dönem)</>}
                  </td><td className="py-1 pl-3 text-right text-gray-100 whitespace-nowrap align-top">{fmtTL(th.komisyon)}</td></tr>
                  <tr className="border-t border-brand-border"><td className="pt-2 font-medium text-gray-100">Toplam</td>
                    <td className="pt-2 pl-3 text-right text-lg font-semibold text-gray-100 whitespace-nowrap">{fmtTL(th.toplam)}</td></tr>
                </tbody>
              </table>
              <p className="text-[11px] text-gray-500 mt-2">
                Ödeme alındığında abonelik <b>{fmtGun(th.yeni_bitis)}</b> tarihine uzar.
              </p>
              <div className="grid sm:grid-cols-3 gap-2 mt-4">
                <select className="input" value={form.yontem} onChange={e => setForm({ ...form, yontem: e.target.value })}>
                  <option value="havale">Havale / EFT</option>
                  <option value="kart">Kart</option>
                </select>
                <input className="input sm:col-span-2" maxLength={200} placeholder="Dekont / referans no (ops.)"
                  value={form.referans} onChange={e => setForm({ ...form, referans: e.target.value })} />
                <input className="input" maxLength={60} placeholder="Fatura no (ops.)"
                  value={form.fatura_no} onChange={e => setForm({ ...form, fatura_no: e.target.value })} />
                <input className="input sm:col-span-2" maxLength={2000} placeholder="Not (ops.)"
                  value={form.not} onChange={e => setForm({ ...form, not: e.target.value })} />
              </div>
              <button onClick={kaydet} disabled={busy}
                className="btn-primary !text-sm w-full mt-3 disabled:opacity-50">
                {busy ? 'Kaydediliyor…' : `✓ Ödeme alındı — ${fmtTL(th.toplam)}`}
              </button>
            </div>
          )}

          <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">Ödeme geçmişi</div>
          {data.odemeler.length === 0 ? (
            <p className="text-sm text-gray-500">Henüz ödeme yok.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="tbl text-xs">
                <thead><tr><th>Tarih</th><th>Dönem</th><th className="!text-right">Sabit</th><th className="!text-right">Komisyon</th><th className="!text-right">Toplam</th><th>Yöntem</th><th>Fatura</th><th></th></tr></thead>
                <tbody>
                  {data.odemeler.map(o => (
                    <tr key={o.id} className={o.durum === 'iptal' ? 'opacity-50 line-through' : ''}>
                      <td className="px-2 py-1.5 text-gray-300">{fmtGun(o.odendi_at?.slice(0, 10))}</td>
                      <td className="px-2 py-1.5 text-gray-400">{fmtGun(o.donem_bas)} – {fmtGun(o.donem_bit)}</td>
                      <td className="px-2 py-1.5 text-right text-gray-300">{fmtTL(o.sabit_ucret)}</td>
                      <td className="px-2 py-1.5 text-right text-gray-300" title={`Ciro ${fmtTL(o.ciro)} · ${o.siparis_sayisi} sipariş`}>{fmtTL(o.komisyon)}</td>
                      <td className="px-2 py-1.5 text-right text-gray-100">{fmtTL(o.toplam)}</td>
                      <td className="px-2 py-1.5 text-gray-400" title={[o.referans, o.not].filter(Boolean).join(' · ')}>
                        {o.yontem === 'havale' ? 'Havale' : 'Kart'}{o.referans ? ' · ' + o.referans : ''}
                      </td>
                      <td className="px-2 py-1.5 no-underline">
                        <button onClick={() => faturaGir(o)} title="Fatura numarasını gir / düzelt"
                          className={o.fatura_no ? 'text-gray-200 hover:underline' : 'text-amber-300/80 hover:text-amber-200'}>
                          {o.fatura_no || '+ ekle'}
                        </button>
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        {o.durum === 'iptal' ? <span className="text-gray-500 no-underline">iptal</span>
                          : sonGecerli?.id === o.id && (
                            <button onClick={() => iptal(o)} className="text-red-300 hover:text-red-200">Geri al</button>)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>)}
      </div>
    </div>
  )
}

// Atölye oluştur/düzenle formlarında plan seçici
export function PlanSecici({ planlar, value, onChange }) {
  const secenekler = planlar.items.filter(p => p.aktif || p.id === value)
  return (
    <select className="input w-full" value={value || ''} onChange={e => onChange(e.target.value || null)}>
      {!value && <option value="">— Plan seçin —</option>}
      {secenekler.map(p => (
        <option key={p.id} value={p.id}>
          {p.ad}{Number(p.aylik_ucret) ? ` · ${fmtTL(p.aylik_ucret)}/ay` : ''}{Number(p.komisyon_orani) ? ` + %${Number(p.komisyon_orani)}` : ''}
        </option>
      ))}
    </select>
  )
}
