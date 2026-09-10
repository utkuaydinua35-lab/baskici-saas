import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import MoldTabs from '../components/MoldTabs'
import DeleteMoldDialog from '../components/DeleteMoldDialog'
import EmptyState from '../components/EmptyState'
import PdfHazirlikPaneli, { PDF_KUYRUK_OLAYI, pdfKuyrugunuYenile }
  from '../components/PdfHazirlikPaneli'
import SlotAssignDialog from '../components/SlotAssignDialog'
import KalipSlotLabels from '../components/KalipSlotLabels'
import KalipAyarlari from '../components/KalipAyarlari'
import { loadLabelSettings } from '../lib/kalipLabel'
import BayiBekleyenUyari from '../components/BayiBekleyenUyari'
import TopluKalipSilDialog from '../components/TopluKalipSilDialog'

const VAR_COLORS = {
  'SİYAH': 'bg-gray-700 text-gray-100 border-gray-600',
  'BEYAZ': 'bg-gray-100 text-gray-800 border-gray-300',
  'ŞEFFAF': 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  'PARLAK': 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  'MAGSAFE': 'bg-purple-500/15 text-purple-300 border-purple-500/30',
}
const REASON_LABELS = {
  urun_tasarima_baglanmamis: 'Ürün tasarıma bağlanmamış',
  kisiye_ozel_tasarim_eksik: 'Kişiye özel tasarımı eksik',
  model_belirsiz: 'Telefon modeli belirsiz',
  model_taninmadi: 'Model tanınmadı',
  baski_dosyasi_yok: 'Baskı dosyası yüklenmemiş (hazır mockup)',
  varyasyon_eksik: 'Varyasyon eksik — kalıp oluşturmadan önce tamamlanmalı',
}

export default function MoldGeneratorPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [plan, setPlan] = useState(null)
  const [molds, setMolds] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [assignTarget, setAssignTarget] = useState(null)  // { mold, kalip_kodu }
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState(null)
  const [searchParams] = useSearchParams()
  const _qtab = searchParams.get('tab')
  const _urlTab = (_qtab === 'existing' || _qtab === 'old') ? _qtab : 'plan'
  const [tab, setTab] = useState(_urlTab)
  useEffect(() => { setTab(_urlTab) }, [_urlTab])
  const [skipMissing, setSkipMissing] = useState(false)

  useEffect(() => {
    // include_bayii: bayi siparişlerini ayrı seçip plan/kalıp doğrulayabilmek için
    api.get('/api/stores?include_bayii=true').then(s => {
      const list = Array.isArray(s) ? s : []
      setStores(list)
      // Varsayılan: 'Tüm Mağazalar' (storeId="") — multi-store birleşik plan
    }).catch(() => {})
  }, [])

  const loadPlan = async (sid = storeId) => {
    setLoading(true); setError(''); setMsg(null)
    try {
      const url = sid ? `/api/molds/plan?store_id=${sid}` : `/api/molds/plan`
      const r = await api.get(url)
      setPlan(r)
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Plan hesaplanamadı')
    } finally { setLoading(false) }
  }
  const loadExisting = async (sid = storeId) => {
    try {
      const p = new URLSearchParams({ archived: 'false' })
      if (sid) p.set('store_id', sid)
      const r = await api.get(`/api/molds?${p}`)
      setMolds(r.items || [])
    } catch { setMolds([]) }
  }

  const [oldMolds, setOldMolds] = useState([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const loadOld = async (sid = storeId) => {
    try {
      const p = new URLSearchParams({ archived: 'true' })
      if (sid) p.set('store_id', sid)
      if (dateFrom) p.set('date_from', dateFrom)
      if (dateTo) p.set('date_to', dateTo)
      const r = await api.get(`/api/molds?${p}`)
      setOldMolds(r.items || [])
    } catch { setOldMolds([]) }
  }
  useEffect(() => { loadPlan(storeId); loadExisting(storeId) }, [storeId])
  useEffect(() => { if (tab === 'old') loadOld(storeId) }, [tab, storeId, dateFrom, dateTo])

  const [harfler, setHarfler] = useState('GHJ')
  const handleCreateEmpty = async () => {
    try {
      const r = await api.post(`/api/molds/create-empty${storeId ? `?store_id=${storeId}` : ''}`)
      if (r?.id) navigate(`/kalip/${r.id}`)
    } catch (e) {
      toast.error('Boş kalıp oluşturulamadı: ' + (e?.detail || e?.message || ''))
    }
  }

  const [recovering, setRecovering] = useState(false)
  const [labelSettings, setLabelSettings] = useState(loadLabelSettings)
  const [showLabelCfg, setShowLabelCfg] = useState(false)
  const handleRecover = async () => {
    setRecovering(true)
    try {
      const r = await api.post('/api/molds/_resync-flags', {})
      const parts = []
      if (r?.fixed > 0) parts.push(`${r.fixed} ürün hiçbir kalıpta değildi → plana döndü (artık basılacak)`)
      if (r?.restored > 0) parts.push(`${r.restored} ürün kalıpta olduğu halde plana düşmüştü → düzeltildi`)
      if (r?.relinked > 0) parts.push(`${r.relinked} kalıp–ürün bağı kalıcı olarak onarıldı`)
      toast.success(parts.length ? parts.join(' · ') : 'Her şey güncel — düzeltme gerekmedi')
      loadPlan(storeId); loadExisting(storeId)
    } catch (e) { toast.error(e?.detail || 'Tarama başarısız') }
    finally { setRecovering(false) }
  }

  // Hangi kalıplar oluşturulacak — boş küme = TÜMÜ (varsayılan davranış korunur).
  const [secili, setSecili] = useState(null)   // null = hepsi, Set = seçilenler
  const planImzalar = (plan?.molds || []).map(m => m.imza)
  const seciliSet = secili === null ? new Set(planImzalar) : secili
  const toggleSecim = (imza) => {
    const n = new Set(seciliSet)
    if (n.has(imza)) n.delete(imza); else n.add(imza)
    setSecili(n)
  }
  const hepsiSecili = planImzalar.length > 0 && planImzalar.every(i => seciliSet.has(i))
  const toggleHepsi = () => setSecili(hepsiSecili ? new Set() : new Set(planImzalar))

  const handleCreate = async () => {
    const kismi = seciliSet.size > 0 && seciliSet.size < planImzalar.length
    const canGo = (plan?.can_create || (skipMissing && plan?.mold_count > 0) || kismi)
      && seciliSet.size > 0
    if (!canGo) return
    const secKilif = (plan?.molds || [])
      .filter(m => seciliSet.has(m.imza))
      .reduce((t, m) => t + (m.count || 0), 0)
    const cm = kismi
      ? `Seçtiğin ${seciliSet.size} kalıp oluşturulacak (${secKilif} kılıf).\n\n` +
        `Seçmediğin ${planImzalar.length - seciliSet.size} kalıp BEKLEMEDE kalacak — ` +
        `kalemleri serbest kalır, sonraki planda yine çıkar.\n\nOnaylıyor musun?`
      : (skipMissing && plan.eksik_count > 0)
        ? `${plan.eksik_count} eksik kalem ATLANACAK. Sadece çözülen ${plan.mold_count} kalıp (${plan.total_units} kılıf) oluşturulacak. Onaylıyor musun?`
        : `${plan.mold_count} kalıp oluşturulacak (${plan.total_units} kılıf). Onaylıyor musun?`
    if (!confirm(cm)) return
    setCreating(true); setError(''); setMsg(null)
    try {
      const kismiSecim = seciliSet.size > 0 && seciliSet.size < planImzalar.length
      const sq = kismiSecim
        ? `&secili=${encodeURIComponent([...seciliSet].join(','))}` : ''
      const hq = `&harfler=${encodeURIComponent((harfler || 'GHJ').toUpperCase())}${sq}`
      const url = storeId
        ? `/api/molds/create?store_id=${storeId}&skip_missing=${skipMissing}${hq}`
        : `/api/molds/create?skip_missing=${skipMissing}${hq}`
      const r = await api.post(url, {})
      if (r.success) {
        setMsg({ ok: true, text: r.message })
        setSecili(null)   // yeni planda yine hepsi seçili başlasın
        loadPlan(storeId); loadExisting(storeId)
        setTab('existing')
      } else {
        setMsg({ ok: false, text: r.message })
      }
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Oluşturma hatası')
    } finally { setCreating(false) }
  }

  // SlotAssignDialog için uygun mold objesi (id + kod + variation + kalip_kodlari)
  const assignMoldObj = assignTarget ? {
    id: assignTarget.mold.id,
    kod: assignTarget.mold.kod,
    variation: assignTarget.mold.variation,
    kalip_kodlari: assignTarget.mold.kalip_kodlari || [],
  } : null

  return (
    <div className="mx-auto max-w-6xl">
      <MoldTabs />
      {/* Onay bekleyen bayi siparisi kaliba GIRMEZ — plan uretmeden once uyar */}
      <BayiBekleyenUyari />
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">{tab === 'old' ? '🗄️ Eski Kalıplar' : tab === 'existing' ? '📦 Oluşturulan Kalıplar' : '🎯 Kalıp Oluşturucu'}</h1>
          <p className="text-sm text-gray-500 mt-1">{tab === 'old' ? 'Tamamlanıp 24 saat geçmiş kalıplar (arşiv)' : tab === 'existing' ? 'Daha önce oluşturulan kalıplar' : 'Bekleyen siparişleri otomatik kalıplara böler'}</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={storeId} onChange={e => setStoreId(e.target.value)} className="input !text-sm !py-1.5 w-full sm:w-auto sm:min-w-[200px]">
            <option value="">Tümü (Mağaza + Bayi)</option>
            <optgroup label="Mağazalar">
              {stores.filter(s => s.platform !== 'bayii').map(s => <option key={s.id} value={s.id}>🏪 {s.name}</option>)}
            </optgroup>
            <optgroup label="Bayiler">
              {stores.filter(s => s.platform === 'bayii').map(s => <option key={s.id} value={s.id}>🤝 {s.name.replace(/^Bayii:\s*/, '')}</option>)}
            </optgroup>
          </select>
          <button onClick={handleRecover} disabled={recovering} className="btn-secondary !text-sm whitespace-nowrap disabled:opacity-50" title="Kalıptan çıkarılıp plana dönmeyen kayıp siparişleri tara ve geri döndür">{recovering ? '…' : '🔧 Kayıp siparişleri tara'}</button>
          <button onClick={() => setShowLabelCfg(true)} className="btn-secondary !text-sm whitespace-nowrap" title="Etiket yazı boyutu + renkleri">⚙️ Kalıp Ayarları</button>
          <button onClick={handleCreateEmpty} className="btn-secondary !text-sm whitespace-nowrap" title="Boş kalıp oluştur, + ile doldur">➕ Boş Kalıp</button>
        </div>
      </div>

      {error && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">{error}</div>}
      {msg && <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${msg.ok ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' : 'bg-amber-500/10 border-amber-500/20 text-amber-300'}`}>{msg.ok ? '✓ ' : '⚠ '}{msg.text}</div>}

      {tab === 'plan' && (
        <>
          {loading && <div className="text-gray-500 text-sm text-center py-10">Plan hesaplanıyor...</div>}
          {!loading && plan && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <Kpi label="OLUŞACAK KALIP" value={plan.mold_count} color="accent" />
                <Kpi label="TOPLAM KILIF" value={plan.total_units} />
                <Kpi label="EKSİK KALEM" value={plan.eksik_count} color={plan.eksik_count ? 'red' : 'emerald'} />
                <div className="bg-brand-card border border-brand-border rounded-lg p-3 flex flex-col justify-center gap-2">
                  <label className="flex items-center gap-2 text-[11px] text-gray-400">
                    <span className="whitespace-nowrap">Kalıp harfleri:</span>
                    <input
                      type="text"
                      value={harfler}
                      onChange={e => setHarfler(e.target.value.replace(/[^a-zA-Z]/g, '').toUpperCase().slice(0, 3))}
                      maxLength={3}
                      placeholder="GHJ"
                      className="w-16 px-2 py-1 bg-brand-input border border-brand-border rounded text-center font-mono text-gray-100 uppercase"
                    />
                  </label>
                  <button onClick={handleCreate}
                    disabled={creating || !(plan.can_create || (skipMissing && plan.mold_count > 0)) || (harfler || '').length < 3}
                    className="btn-primary w-full disabled:opacity-40 disabled:cursor-not-allowed">
                    {creating ? 'Oluşturuluyor...' : '🎯 Kalıpları Oluştur'}
                  </button>
                  {plan.eksik_count > 0 && (
                    <label className="flex items-center gap-1.5 text-[11px] text-gray-400 cursor-pointer">
                      <input type="checkbox" checked={skipMissing} onChange={e => setSkipMissing(e.target.checked)} className="accent-accent" />
                      Eksikleri atla, çözülenleri oluştur
                    </label>
                  )}
                </div>
              </div>

              {plan.eksik_count > 0 && (
                <div className="card mb-4 border-amber-500/30 bg-amber-500/5">
                  <h2 className="text-sm font-medium text-amber-300 mb-2">
                    ⚠ {plan.eksik_count} kalem için tasarım eksik — kalıp oluşturmadan önce tamamlanmalı
                  </h2>
                  <div className="space-y-1 max-h-60 overflow-y-auto">
                    {plan.eksikler.slice(0, 50).map((e, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs bg-brand-input/40 rounded px-2 py-1.5">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 shrink-0">
                          {REASON_LABELS[e.reason] || e.reason}
                        </span>
                        <span className="text-gray-300 truncate flex-1">{e.title || '(başlıksız)'}</span>
                        {e.model && <span className="text-gray-500 shrink-0">{e.model}</span>}
                        <span className="text-gray-600 shrink-0">×{e.count}</span>
                      </div>
                    ))}
                    {plan.eksikler.length > 50 && <div className="text-[11px] text-gray-500 px-2">+{plan.eksikler.length - 50} daha...</div>}
                  </div>
                  <p className="text-[11px] text-gray-500 mt-2">
                    Tasarıma bağlanmamış ürünleri <a href="/designs" className="text-accent hover:underline">Tasarımlar</a> sayfasından,
                    kişiye özelleri <a href="/kisiye-ozel" className="text-accent hover:underline">Kişiye Özel</a> sayfasından tamamla.
                  </p>
                </div>
              )}

              {/* ⚠ Stok eksikliği bugüne kadar ancak BASKI ANINDA fark ediliyordu:
                  kalem kalıptan çıkarılıyor, müşteriye "ürününüz yok" mesajı
                  gidiyor. Stok verisi zaten vardı, plan ona bakmıyordu.
                  UYARIDIR, ENGEL DEĞİL — sayım güncel olmayabilir. */}
              {plan.stok_uyarilar?.length > 0 && (
                <div className="card mb-4 border-amber-500/40 bg-amber-500/5">
                  <h2 className="text-sm font-medium text-amber-300 mb-1">
                    📦 {plan.stok_eksik_toplam} kılıf için boş kılıf stoğu yetmiyor
                  </h2>
                  <p className="text-[11px] text-gray-500 mb-2">
                    Bu kalıbı basarsan aşağıdaki kalemler yarıda kalabilir. Stok sayımı
                    güncel değilse yok sayabilirsin — <a href="/stok" className="text-accent hover:underline">Stok</a>'tan
                    kontrol et.
                  </p>
                  <div className="space-y-1 max-h-60 overflow-y-auto">
                    {plan.stok_uyarilar.map((u, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs bg-brand-input/40 rounded px-2 py-1.5">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 shrink-0 font-mono">
                          {u.variation || '—'}
                        </span>
                        <span className="text-gray-300 shrink-0">{u.model}</span>
                        <span className="text-gray-500 truncate flex-1">
                          {u.siparisler?.length ? `Sipariş: ${u.siparisler.slice(0, 6).join(', ')}${u.siparisler.length > 6 ? '…' : ''}` : ''}
                        </span>
                        <span className="text-amber-300 shrink-0" title="gerekli / mevcut">
                          {u.gerekli} gerekli · {u.mevcut} var
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {plan.aski_uyarilar?.length > 0 && (
                <div className="card mb-4 border-sky-500/30 bg-sky-500/5">
                  <h2 className="text-sm font-medium text-sky-300 mb-1">
                    🪝 {plan.aski_uyari_count} kılıf askıda hazır bekliyor olabilir — basmadan önce kontrol et
                  </h2>
                  <p className="text-[11px] text-gray-500 mb-2">
                    Aşağıdaki tasarım/model kombinasyonları dükkanda <a href="/aski" className="text-accent hover:underline">Askı</a> stoğunda mevcut.
                    Bu siparişleri askıdan gönderip kalıba eklememen gereksiz baskıyı önler.
                  </p>
                  <div className="space-y-1 max-h-60 overflow-y-auto">
                    {plan.aski_uyarilar.map((a, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs bg-brand-input/40 rounded px-2 py-1.5">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-300 shrink-0 font-mono">
                          {a.design_code || '—'}
                        </span>
                        <span className="text-gray-300 shrink-0">{a.model}</span>
                        <span className="text-gray-500 truncate flex-1">
                          {a.siparisler?.length ? `Sipariş: ${a.siparisler.slice(0, 6).join(', ')}${a.siparisler.length > 6 ? '…' : ''}` : ''}
                        </span>
                        <span className="text-emerald-300 shrink-0" title="Askıdan karşılanabilir">
                          {a.karsilanabilir}/{a.plandaki_adet} askıda
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {plan.molds.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <h2 className="text-sm font-medium text-gray-300">
                      Kalıp Önizlemesi ({plan.mold_count})
                      {seciliSet.size !== planImzalar.length && (
                        <span className="ml-2 text-[11px] text-amber-300">
                          {seciliSet.size} seçili · {planImzalar.length - seciliSet.size} beklemede kalacak
                        </span>
                      )}
                    </h2>
                    <button onClick={toggleHepsi}
                            className="text-[11px] text-accent hover:underline shrink-0">
                      {hepsiSecili ? 'Hiçbirini seçme' : 'Hepsini seç'}
                    </button>
                  </div>
                  {plan.molds.map(m => {
                    const sec = seciliSet.has(m.imza)
                    return (
                      <div key={m.imza || m.sira}
                           className={`rounded-xl transition-opacity ${sec ? '' : 'opacity-45'}`}>
                        <label className="flex items-center gap-2 mb-1 cursor-pointer w-fit">
                          <input type="checkbox" checked={sec}
                                 onChange={() => toggleSecim(m.imza)}
                                 className="w-4 h-4 accent-emerald-400" />
                          <span className="text-[11px] text-gray-400">
                            {sec ? 'Bu kalıp oluşturulacak' : 'Beklemede kalacak (kalemler serbest)'}
                          </span>
                        </label>
                        <MoldCard mold={m} preview harfler={harfler} labelSettings={labelSettings} />
                      </div>
                    )
                  })}
                </div>
              )}

              {plan.mold_count === 0 && plan.eksik_count === 0 && (
                <div className="card text-center py-12 text-gray-500">
                  <div className="text-3xl mb-2">✓</div>
                  Bekleyen kalıp yok — tüm siparişler kalıba eklenmiş.
                </div>
              )}
            </>
          )}
        </>
      )}

      {tab === 'old' && (
        <>
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <span className="text-xs text-gray-500">Tarih aralığı:</span>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="input !text-sm !py-1" />
            <span className="text-gray-600">–</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="input !text-sm !py-1" />
            {(dateFrom || dateTo) && <button onClick={() => { setDateFrom(''); setDateTo('') }} className="text-xs text-gray-500 hover:text-gray-300">temizle</button>}
          </div>
          {oldMolds.length === 0 ? (
            <div className="card text-center py-12 text-gray-500"><div className="text-4xl mb-2">🗄️</div>Bu aralıkta eski kalıp yok.</div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {oldMolds.map(m => (
                <div key={m.id} className="card !p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-sm text-gray-200">{m.kod}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-input text-gray-400">{m.variation}</span>
                  </div>
                  <div className="text-xs text-gray-500">{m.kilif_sayisi} kılıf</div>
                  <div className="text-[10px] text-gray-600 mt-1">Tamamlandı: {m.tamamlandi_at ? new Date(m.tamamlandi_at).toLocaleString('tr-TR') : '—'}</div>
                  <button onClick={() => navigate(`/kalip/${m.id}`)} className="btn-secondary !text-xs mt-2 w-full">📋 Detay</button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'existing' && (
        <ExistingMolds
          molds={molds}
          onOpen={(id) => navigate(`/kalip/${id}`)}
          onDelete={(m) => setDeleteTarget({ id: m.id, kod: m.kod })}
          onBulkDeleted={() => { loadExisting(); loadPlan() }}
        />
      )}

      <DeleteMoldDialog
        open={!!deleteTarget}
        mold={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={() => { setDeleteTarget(null); loadExisting(); loadPlan() }}
      />

      {showLabelCfg && <KalipAyarlari onClose={() => setShowLabelCfg(false)} onChange={setLabelSettings} />}

      <SlotAssignDialog
        open={!!assignTarget}
        mold={assignMoldObj}
        kalipKodu={assignTarget?.kalip_kodu}
        onClose={() => setAssignTarget(null)}
        onAssigned={() => { setAssignTarget(null); loadExisting(); loadPlan() }}
      />
    </div>
  )
}


// Oluşturulan kalıplar: bekleyen / basılmış ayrımı + toplu "PDF Hazırla".
//
// PDF üretimi karmaşık vektör tasarımlarda dakikalar sürüyor ve vektör
// KORUNUYOR (rasterleştirme kalite kaybı yapardı). Bu yüzden baskıdan ÖNCE
// hazırlanır; baskı sırasında beklenmez. Kalıp değişirse sunucu hazır PDF'i
// siler ve durum "yok"a döner — o kalıp yeniden hazırlanmalıdır.

/** Kalıp listesi — ExistingMolds'un İÇİNDE tanımlıydı.
 *
 * İç içe tanımlanan bileşen her render'da YENİ bir tip oluyor; React eskisini
 * söküp yenisini kuruyordu. Yani her onay kutusu tıklamasında listenin TÜM
 * DOM'u yeniden yaratılıyor, kaydırma ve odak kayboluyordu (onlarca kalıpta
 * gözle görülür takılma). Dışarı alınınca tip sabit kalır, React yalnız
 * değişen satırı günceller.
 *
 * Seçim iki liste arasında PAYLAŞILIR; eylemler yalnız KENDİ satırlarına
 * uygulanır — "Bekleyen"de seçip "Basılmış"ta silmek gibi sürpriz olmasın.
 */
function KalipListesi({ baslik, veri, pdfVar, secili, setSecili, sec, durumlar,
                        busy, hazirla, basildiMi, onOpen, onDelete, onTopluSil }) {
  const buListedeSecili = veri.filter(m => secili.has(m.id))
  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div className="text-sm font-medium text-gray-200">
          {baslik} <span className="text-gray-500">({veri.length})</span>
        </div>
        {veri.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <button onClick={() => setSecili(s => new Set([...s, ...veri.map(m => m.id)]))}
                      className="text-[11px] text-gray-400 hover:text-gray-200 underline">tümünü seç</button>
              {buListedeSecili.length > 0 && (
                <button onClick={() => setSecili(s => {
                          const n = new Set(s); veri.forEach(m => n.delete(m.id)); return n })}
                        className="text-[11px] text-gray-500 hover:text-gray-300 underline">temizle</button>
              )}
              {pdfVar && (
                <button onClick={() => hazirla(buListedeSecili.length
                          ? buListedeSecili.map(m => m.id) : veri.map(m => m.id))}
                        disabled={busy} className="btn-primary !text-xs disabled:opacity-50">
                  {busy ? '…' : buListedeSecili.length
                    ? `📄 ${buListedeSecili.length} kalıbın PDF'ini hazırla`
                    : "📄 Tümünün PDF'ini hazırla"}
                </button>
              )}
              <button
                onClick={() => onTopluSil(
                  (buListedeSecili.length ? buListedeSecili : veri)
                    .map(m => ({ id: m.id, kod: m.kod, variation: m.variation,
                                 kilif_sayisi: m.kilif_sayisi, basildi: basildiMi(m) })))}
                className="text-xs px-2.5 py-1 rounded border border-red-500/25 text-red-400/85
                           hover:text-red-300 hover:border-red-500/50 hover:bg-red-500/10 transition-colors">
                🗑 {buListedeSecili.length ? `${buListedeSecili.length} kalıbı sil` : 'Tümünü sil'}
              </button>
            </div>
        )}
      </div>
      {veri.length === 0 ? (
        <div className="card !p-0"><EmptyState dar ikon="—" baslik={`${baslik} yok`} /></div>
      ) : (
        <div className="card divide-y divide-brand-border/60 !p-0 overflow-hidden">
          {veri.map(m => (
            <div key={m.id} className="flex items-center gap-2 pl-3">
              <input type="checkbox" checked={secili.has(m.id)} onChange={() => sec(m.id)}
                     onClick={e => e.stopPropagation()} className="w-4 h-4 accent-accent shrink-0" />
              <PdfRozet d={durumlar[m.id]} />
              <div className="flex-1 min-w-0">
                <MoldRow mold={m} onClick={() => onOpen(m.id)} onDelete={() => onDelete(m)} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  
  )
}

function ExistingMolds({ molds, onOpen, onDelete, onBulkDeleted }) {
  const toast = useToast()
  const [secili, setSecili] = useState(() => new Set())
  const [silinecek, setSilinecek] = useState(null)   // toplu silme onayı
  const [durumlar, setDurumlar] = useState({})   // {mold_id: {durum}}
  const [busy, setBusy] = useState(false)

  // "Basılmış" ÜÇ ayrı alandan gelebiliyor ve yalnız birine bakmak yanlıştı:
  //   status       : olusturuldu | basildi | tamamlandi | iptal
  //   print_status : bekliyor | basildi | eksik_var | hatali_basildi
  //   current_stage: 5 = tamamlandı
  // 'tamamlandi' olan kalıplar bu yüzden bekleyende görünüyordu.
  const basildiMi = (m) => (
    m.print_status === 'basildi'
    || m.status === 'basildi'
    || m.status === 'tamamlandi'
    || (m.current_stage || 0) >= 5
  )
  const yeni = (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
  const bekleyen = useMemo(() => molds.filter(m => !basildiMi(m)).sort(yeni), [molds])
  const basilmis = useMemo(() => molds.filter(basildiMi).sort(yeni), [molds])

  const durumSor = async (ids) => {
    if (!ids.length) return
    try {
      const r = await api.get(`/api/molds/pdf/durum?ids=${ids.join(',')}`)
      setDurumlar(d => ({ ...d, ...(r.items || {}) }))
    } catch { /* sessiz */ }
  }
  useEffect(() => { durumSor(bekleyen.map(m => m.id)) }, [molds])

  // Rozetleri sunucu KUYRUGUNA göre tazele (PdfHazirlikPaneli yayınlıyor).
  // Eskiden yalnız rozeti "hazırlanıyor" olanlar yoklanıyordu; bir kalıbın
  // durumu araya girip "yok"a dönerse izlenmeyi bırakıyor ve iş bitince rozet
  // güncellenmiyordu (F5 gerekiyordu).
  const doluyduRef = useRef(false)
  useEffect(() => {
    const dinle = (e) => {
      const dolu = (e.detail?.isler || []).length > 0
      // Kuyruk doluyken sürekli, DOLUDAN BOŞA geçişte bir kez daha sor:
      // "yeni bitti" anı tam orasıdır.
      if (dolu || doluyduRef.current) durumSor(bekleyen.map(m => m.id))
      doluyduRef.current = dolu
    }
    window.addEventListener(PDF_KUYRUK_OLAYI, dinle)
    return () => window.removeEventListener(PDF_KUYRUK_OLAYI, dinle)
  }, [bekleyen])

  const hazirla = async (ids) => {
    if (!ids.length) { toast.info('Önce kalıp seç'); return }
    setBusy(true)
    try {
      const r = await api.post('/api/molds/pdf/hazirla', { mold_ids: ids })
      const n = r.kuyruga_alinan || 0
      const hazir = (r.items || []).filter(x => x.durum === 'hazir').length
      const hata = (r.items || []).filter(x => x.durum === 'hata')
      toast.success(
        n ? `${n} kalıp hazırlanıyor${hazir ? ` · ${hazir} zaten hazırdı` : ''}`
          : (hazir ? `${hazir} kalıbın PDF'i zaten hazır` : 'İşlem yapılmadı'))
      if (hata.length) toast.error(`${hata.length} kalıpta sorun: ${hata[0].mesaj || ''}`)
      setSecili(new Set())
      durumSor(ids)
      pdfKuyrugunuYenile()   // panel 3 sn beklemeden açılsın
    } catch (e) { toast.error(e?.detail || 'Hazırlanamadı') }
    finally { setBusy(false) }
  }

  const sec = (id) => setSecili(s => {
    const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n
  })

  if (!molds.length) {
    return (
      <div className="card !p-0">
        <EmptyState ikon="🧩" baslik="Henüz kalıp oluşturulmamış"
          aciklama="Bekleyen siparişlerden kalıp üretmek için Kalıp Oluşturucu sekmesini kullan." />
      </div>
    )
  }

  return (
    <div>
      <KalipListesi baslik="⏳ Bekleyen Kalıplar" veri={bekleyen} pdfVar
                    secili={secili} setSecili={setSecili} sec={sec} durumlar={durumlar}
                    busy={busy} hazirla={hazirla} basildiMi={basildiMi}
                    onOpen={onOpen} onDelete={onDelete} onTopluSil={setSilinecek} />
      <KalipListesi baslik="✓ Basılmış Kalıplar" veri={basilmis}
                    secili={secili} setSecili={setSecili} sec={sec} durumlar={durumlar}
                    busy={busy} hazirla={hazirla} basildiMi={basildiMi}
                    onOpen={onOpen} onDelete={onDelete} onTopluSil={setSilinecek} />
      <PdfHazirlikPaneli />

      <TopluKalipSilDialog
        open={!!silinecek}
        kaliplar={silinecek}
        onClose={() => setSilinecek(null)}
        onDeleted={(d) => {
          setSilinecek(null)
          setSecili(new Set())
          toast.success(`${d?.deleted_count ?? 0} kalıp silindi`)
          onBulkDeleted?.()
        }} />
    </div>
  )
}

// Kalıp satırındaki PDF hazırlık rozeti: PDF yok / hazırlanıyor / hazır.
function PdfRozet({ d }) {
  const map = {
    hazir:        { m: 'PDF hazır',    c: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30' },
    hazirlaniyor: { m: 'hazırlanıyor', c: 'text-amber-300 bg-amber-500/10 border-amber-500/30' },
    hata:         { m: 'hata',         c: 'text-red-300 bg-red-500/10 border-red-500/30' },
  }
  const v = map[d?.durum]
  if (!v) return <span className="text-[10px] text-gray-600 w-[76px] shrink-0 text-center">PDF yok</span>
  return (
    <span title={d?.mesaj || (d?.durum === 'hazirlaniyor' ? `${d?.gecen_sn || 0} sn` : '')}
          className={`text-[10px] px-1.5 py-0.5 rounded border shrink-0 w-[76px] text-center ${v.c}`}>
      {v.m}
    </span>
  )
}


function MoldRow({ mold, onClick, onDelete }) {
  const vc = VAR_COLORS[mold.variation] || 'bg-gray-700 text-gray-200 border-gray-600'
  const statusColors = {
    olusturuldu: 'bg-blue-500/15 text-blue-300',
    basildi: 'bg-emerald-500/15 text-emerald-300',
    iptal: 'bg-red-500/15 text-red-300',
  }
  const sc = statusColors[mold.status] || 'bg-gray-600/30 text-gray-300'
  const tarih = mold.created_at ? new Date(mold.created_at).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric' }) : ''
  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 px-4 py-3 hover:bg-brand-input/40 cursor-pointer transition-colors">
      <span className="text-sm font-mono font-semibold text-gray-100 min-w-[90px]">{mold.kod}</span>
      <span className={`text-[10px] px-2 py-0.5 rounded-full border ${vc}`}>{mold.variation}</span>
      <span className="text-xs text-gray-400">{mold.kilif_sayisi}/27 kılıf · {mold.rows_used} satır</span>
      {mold.is_multi_store && <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300">🏪 Çoklu</span>}
      <span className={`text-[10px] px-2 py-0.5 rounded-full ${sc}`}>{mold.status}</span>
      <span className="text-xs text-gray-500 ml-auto">{tarih}</span>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete() }}
        className="text-xs text-red-400/70 hover:text-red-300 hover:bg-red-500/10 rounded px-2 py-1 border border-red-500/20"
        title="Kalıbı sil">🗑</button>
      <span className="text-gray-600 text-lg">›</span>
    </div>
  )
}

function MoldCard({ mold, preview, status, kod, onClick, onDelete, onAssignSlot, harfler, labelSettings }) {
  const vc = VAR_COLORS[mold.variation] || 'bg-gray-700 text-gray-200 border-gray-600'
  return (
    <div className={`card ${onClick ? 'cursor-pointer hover:border-accent/40 transition-colors' : ''}`} onClick={onClick}>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-100">
            {kod ? kod : (mold.kodlar && mold.kodlar.length ? kisaKodlar(mold.kodlar, harfler).join('-') : `Kalıp ${mold.sira}`)}
          </span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${vc}`}>{mold.variation}</span>
          {mold.is_multi_store && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border bg-blue-500/15 text-blue-300 border-blue-500/30" title="Birden çok mağazadan kalemler">
              🏪 Çoklu Mağaza
            </span>
          )}
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="ml-auto text-xs text-red-400/80 hover:text-red-300 hover:bg-red-500/10 rounded px-2 py-1 border border-red-500/20 hover:border-red-500/40 flex items-center gap-1"
              title="Kalıbı sil"
              aria-label="Kalıbı sil">
              🗑 Kalıbı Sil
            </button>
          )}
          {status && <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">{status}</span>}
          {preview && <span className="text-[10px] text-gray-500">önizleme</span>}
        </div>
        <div className="text-xs text-gray-500">
          {mold.count}/27 kılıf · {mold.rows_used} satır · kodlar: {kisaKodlar(mold.kodlar, harfler).join(', ')}
        </div>
      </div>
      <MoldGrid items={mold.items} onAssignSlot={onAssignSlot} harfler={harfler} labelSettings={labelSettings} />
    </div>
  )
}

const _KISA_SLOT = {
  'IPHONE-11-GROUP|SIYAH': [0,1], 'IPHONE-11-GROUP|BEYAZ': [0,2],
  'IPHONE-13-GROUP|SIYAH': [0,3], 'IPHONE-13-GROUP|BEYAZ': [0,4],
  'IPHONE-15-GROUP|SIYAH': [0,5], 'IPHONE-15-GROUP|BEYAZ': [0,6],
  'IPHONE-13-PROMAX-GROUP|SIYAH': [0,7], 'IPHONE-13-PROMAX-GROUP|BEYAZ': [0,8],
  'IPHONE-14-PLUS-GROUP|SIYAH': [0,7], 'IPHONE-14-PLUS-GROUP|BEYAZ': [0,8],
  'IPHONE-16-PLUS-GROUP|SIYAH': [0,7], 'IPHONE-16-PLUS-GROUP|BEYAZ': [0,8],
  'IPHONE-15-PRO-GROUP|SIYAH': [0,9], 'IPHONE-15-PRO-GROUP|BEYAZ': [1,1],
  'IPHONE-16-PRO-GROUP|SIYAH': [0,9], 'IPHONE-16-PRO-GROUP|BEYAZ': [1,1],
  'IPHONE-17-PRO-GROUP|SIYAH': [0,9], 'IPHONE-17-PRO-GROUP|BEYAZ': [1,1],
  'IPHONE-15-PROMAX-GROUP|SIYAH': [1,2], 'IPHONE-15-PROMAX-GROUP|BEYAZ': [1,3],
  'IPHONE-16-PROMAX-GROUP|SIYAH': [1,2], 'IPHONE-16-PROMAX-GROUP|BEYAZ': [1,3],
  'IPHONE-17-PROMAX-GROUP|SIYAH': [1,2], 'IPHONE-17-PROMAX-GROUP|BEYAZ': [1,3],
  'SEFFAF': [1,4], 'PARLAK': [1,5], 'MAGSAFE': [2,3],
  'REDMI-GROUP|SIYAH': [1,6], 'XIAOMI-GROUP|SIYAH': [1,7],
  'SAMSUNG-A-GROUP|SIYAH': [1,8], 'SAMSUNG-M-GROUP|SIYAH': [1,8],
  'SAMSUNG-S-GROUP|SIYAH': [1,9], 'SAMSUNG-ULTRA-GROUP|SIYAH': [2,1],
  'POCO-GROUP|SIYAH': [2,2], 'OPPO-GROUP|SIYAH': [2,2], 'VIVO-GROUP|SIYAH': [2,2],
  'REALME-GROUP|SIYAH': [2,2], 'TECNO-GROUP|SIYAH': [2,2], 'HUAWEI-GROUP|SIYAH': [2,2],
  'OMIX-GROUP|SIYAH': [2,2], 'SAMSUNG-OTHER-GROUP|SIYAH': [2,2],
}
function kisaKod(grupKodu, harfler) {
  if (!grupKodu) return '?'
  let h = (harfler || 'GHJ').toUpperCase()
  if (h.length < 3) h = (h + 'GHJ').slice(0, 3)
  h = h.slice(0, 3)
  let slot = _KISA_SLOT[grupKodu]
  if (!slot && grupKodu.indexOf('|BEYAZ') >= 0) slot = _KISA_SLOT[grupKodu.replace('|BEYAZ', '|SIYAH')]
  if (!slot) return grupKodu.split('|')[0].replace('-GROUP', '').slice(0, 4)
  return `${h[slot[0]]}${slot[1]}`
}
function kisaKodlar(grupKodlari, harfler) {
  const seen = []
  for (const gk of (grupKodlari || [])) {
    const kk = kisaKod(gk, harfler)
    if (seen.indexOf(kk) < 0) seen.push(kk)
  }
  return seen
}

function shortModel(m) {
  if (!m) return ''
  return m.replace(/i\s*phone/i, '').replace(/apple/i, '').replace(/galaxy/i, '').replace(/samsung/i, '').trim().toUpperCase()
}
function kilifLabel(it) {
  // Kalibin GERCEK rengi (android beyaz->siyah sonrasi)
  if (it.kilif_rengi) return `Kılıf: ${String(it.kilif_rengi).toUpperCase()}`
  if (it.variation) return `Kılıf: ${String(it.variation).toUpperCase()}`
  return ''
}

// Grup baski-sirasi onceligi (backend GROUP_PRIORITY ile ayni — dusuk=alt satir)
const _GROUP_PRIORITY = {
  'IPHONE-11-GROUP': 1, 'IPHONE-13-GROUP': 2, 'IPHONE-15-GROUP': 3,
  'IPHONE-13-PROMAX-GROUP': 4, 'IPHONE-14-PLUS-GROUP': 5, 'IPHONE-16-PLUS-GROUP': 6,
  'IPHONE-15-PRO-GROUP': 7, 'IPHONE-16-PRO-GROUP': 8, 'IPHONE-17-PRO-GROUP': 9,
  'IPHONE-15-PROMAX-GROUP': 10, 'IPHONE-16-PROMAX-GROUP': 11, 'IPHONE-17-PROMAX-GROUP': 12,
  'SAMSUNG-A-GROUP': 100, 'SAMSUNG-S-GROUP': 101, 'SAMSUNG-ULTRA-GROUP': 102,
  'SAMSUNG-M-GROUP': 103, 'SAMSUNG-OTHER-GROUP': 104,
  'REDMI-GROUP': 110, 'XIAOMI-GROUP': 111, 'POCO-GROUP': 112, 'OPPO-GROUP': 113,
  'VIVO-GROUP': 114, 'REALME-GROUP': 115, 'TECNO-GROUP': 116,
  'HUAWEI-GROUP': 117, 'OMIX-GROUP': 118, 'SEFFAF': 200, 'PARLAK': 201, 'MAGSAFE': 202,
  'IPHONE-UNKNOWN': 50, 'UNKNOWN-GROUP': 999,
}
function _kodPriority(kod) {
  if (!kod) return 999
  let grp
  if (kod.indexOf('@') >= 0) grp = kod.split('@')[1]            // SEFFAF@IPHONE-11-GROUP
  else grp = (kod.indexOf('|') >= 0) ? kod.split('|')[0] : kod  // IPHONE-15-GROUP|SIYAH
  return _GROUP_PRIORITY[grp] != null ? _GROUP_PRIORITY[grp] : 999
}

function MoldGrid({ items, onAssignSlot, harfler, labelSettings }) {
  // slot_index varsa onu kullan (kaydedilmis kalip); yoksa (plan onizleme) priority'ye gore diz.
  const hasSlots = items.some(it => typeof it.slot_index === 'number')
  const bySlot = {}
  if (hasSlots) {
    for (const it of items) {
      const sn = (typeof it.slot_index === 'number') ? it.slot_index + 1 : null
      if (sn) bySlot[sn] = it
    }
  } else {
    // onizleme: satir kovalarini priority'ye gore sirala, dusuk->alt satir (row 0 = slot 1-9).
    // Ozel varyasyonlar (SEFFAF/PARLAK/MAGSAFE) satir_kod ile gruba bolunur -> ayri satir.
    const byKod = {}
    const kods = []
    for (const it of items) {
      const rk = it.satir_kod || it.kod
      if (!byKod[rk]) { byKod[rk] = []; kods.push(rk) }
      byKod[rk].push(it)
    }
    kods.sort((a, b) => _kodPriority(a) - _kodPriority(b))
    let rowCursor = 0
    for (const kod of kods) {
      const g = byKod[kod]
      const rowsNeeded = Math.ceil(g.length / 9)
      for (let r = 0; r < rowsNeeded; r++) {
        if (rowCursor >= 3) break
        const chunk = g.slice(r * 9, r * 9 + 9)
        // row 0 -> slot 1-9, row 1 -> 10-18, row 2 -> 19-27
        for (let i = 0; i < chunk.length; i++) {
          bySlot[rowCursor * 9 + i + 1] = chunk[i]
        }
        rowCursor++
      }
    }
  }
  const rowKodOf = (ri) => {
    for (let ci = 0; ci < 9; ci++) {
      const sn = 27 - (ri * 9 + ci)
      if (bySlot[sn]) return bySlot[sn].kod
    }
    return null
  }
  return (
    <div className="overflow-x-auto -mx-1 px-1">
    <div className="space-y-1.5 min-w-[520px]">
      {[0, 1, 2].map((ri) => {
        const rowKod = rowKodOf(ri)
        return (
          <div key={ri} className="grid grid-cols-9 gap-1.5">
            {Array.from({ length: 9 }).map((_, ci) => {
              const slotNo = 27 - (ri * 9 + ci)
              const cell = bySlot[slotNo] || null
              const canAssign = !cell && rowKod && onAssignSlot
              return <Slot
                key={ci}
                item={cell}
                no={slotNo}
                harfler={harfler}
                labelSettings={labelSettings}
                onAssign={canAssign ? (e) => { e.stopPropagation(); onAssignSlot(rowKod) } : null}
                assignKod={canAssign ? rowKod : null}
              />
            })}
          </div>
        )
      })}
    </div>
    </div>
  )
}

function Slot({ item, no, onAssign, assignKod, harfler, labelSettings }) {
  if (!item) {
    if (onAssign) {
      return (
        <button
          onClick={onAssign}
          title={`${assignKod} satırına slot ata`}
          className="aspect-[9/16] rounded-lg border border-dashed border-accent/40 hover:border-accent hover:bg-accent/10 flex flex-col items-center justify-center text-gray-500 hover:text-accent transition-colors group">
          <span className="text-2xl leading-none group-hover:scale-110 transition-transform">+</span>
          <span className="text-[9px] mt-0.5 font-mono opacity-60">{kisaKod(assignKod, harfler)}</span>
          <span className="text-[8px] mt-0.5">#{no}</span>
        </button>
      )
    }
    return (
      <div className="aspect-[9/16] rounded-lg border border-dashed border-brand-border/40 flex flex-col items-center justify-center text-gray-700">
        <span className="text-xs font-medium">{no}</span>
        <span className="text-[8px]">Boş</span>
      </div>
    )
  }
  return (
    <div className="aspect-[9/16] rounded-lg border border-accent/40 overflow-hidden relative bg-brand-input"
      title={`${item.kod} · ${item.design_code || ''} · ${item.model || ''} · #${item.order_number}`}>
      {item.thumbnail_url && (
        <img src={item.thumbnail_url} alt="" className="absolute inset-0 w-full h-full object-cover opacity-55"
          onError={e => { e.target.style.display = 'none' }} />
      )}
      <span className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/30" />
      <div className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 flex items-center justify-center text-white text-[7px]">✓</div>
      <div className="absolute top-1 left-1 text-[9px] font-mono text-accent bg-black/40 rounded px-1">{kisaKod(item.kod, harfler)}</div>
      {item.is_telafi && (
        <div className="absolute bottom-1 left-1 z-20 text-[7px] font-bold text-amber-200 bg-amber-600/80 rounded px-1 leading-tight">TELAFİ</div>
      )}
      <KalipSlotLabels item={item} no={no} settings={labelSettings} />
    </div>
  )
}

function Kpi({ label, value, color = 'gray' }) {
  const colors = { gray: 'text-gray-100', accent: 'text-accent', red: 'text-red-400', emerald: 'text-emerald-400' }
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-3">
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold ${colors[color]}`}>{value}</div>
    </div>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-sm transition-colors ${active ? 'bg-accent/15 text-accent font-medium' : 'text-gray-400 hover:text-gray-200 hover:bg-brand-input/60'}`}>
      {children}
    </button>
  )
}
