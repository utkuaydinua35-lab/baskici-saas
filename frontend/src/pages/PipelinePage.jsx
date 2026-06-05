import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function PipelinePage() {
  const [stores, setStores] = useState([])
  const [storesLoading, setStoresLoading] = useState(true)
  const [form, setForm] = useState({
    store_id: '',
    order_numbers_input: '',
    letters: '',
  })
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api.get('/api/stores')
      .then(s => {
        if (cancelled) return
        const list = Array.isArray(s) ? s : []
        setStores(list)
        if (list.length > 0) {
          setForm(f => ({ ...f, store_id: list[0].id }))
        }
      })
      .catch(e => !cancelled && setError('Mağazalar yüklenemedi: ' + (e.detail || e.message)))
      .finally(() => !cancelled && setStoresLoading(false))
    return () => { cancelled = true }
  }, [])

  const selectedStore = stores.find(s => s.id === form.store_id)
  const expectedLetters = selectedStore?.matching_strategy === 'simple' ? 2 : 3

  const handleRun = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setRunning(true)
    try {
      const r = await api.post('/api/pipeline/process', form)
      setResult(r)
    } catch (e) {
      setError(e.detail || 'Pipeline çalıştırılamadı')
    } finally {
      setRunning(false)
    }
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
      .then(() => alert('Panoya kopyalandı'))
      .catch(() => alert('Kopyalama başarısız'))
  }

  return (
    <div className="max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-100">Pipeline</h1>
        <p className="text-sm text-gray-500 mt-1">
          Sipariş numaralarını gir, kısayolları uygula, kalıp listesini al
        </p>
      </div>

      {storesLoading && (
        <div className="card text-center py-8 text-gray-500">⏳ Yükleniyor...</div>
      )}

      {!storesLoading && stores.length === 0 && (
        <div className="card text-center py-8">
          <div className="text-3xl mb-2">🏪</div>
          <p className="text-gray-400">
            Henüz mağaza yok. Önce <a href="/stores" className="text-accent hover:underline">Mağazalar</a> sayfasından bağlanmak gerek.
          </p>
        </div>
      )}

      {!storesLoading && stores.length > 0 && (
        <>
          {/* Form */}
          <form onSubmit={handleRun} className="card mb-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Mağaza</label>
                <select
                  value={form.store_id}
                  onChange={e => setForm(f => ({ ...f, store_id: e.target.value }))}
                  className="input w-full !text-sm"
                  required
                >
                  {stores.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.matching_strategy})
                    </option>
                  ))}
                </select>
                {selectedStore && (
                  <p className="text-[10px] text-gray-500 mt-1">
                    {expectedLetters} harf gerekir
                  </p>
                )}
              </div>

              <div>
                <label className="text-xs text-gray-400 block mb-1">
                  Kalıp Harfleri ({expectedLetters})
                </label>
                <input
                  type="text"
                  required
                  value={form.letters}
                  onChange={e => setForm(f => ({ ...f, letters: e.target.value.toUpperCase() }))}
                  className="input w-full font-mono uppercase"
                  placeholder={expectedLetters === 3 ? 'ABC' : 'AB'}
                  maxLength={10}
                />
                <p className="text-[10px] text-gray-500 mt-1">
                  Sırayla harf, örn: <code>{expectedLetters === 3 ? 'MNP' : 'AB'}</code>
                </p>
              </div>

              <div>
                <label className="text-xs text-gray-400 block mb-1">Sipariş No</label>
                <input
                  type="text"
                  required
                  value={form.order_numbers_input}
                  onChange={e => setForm(f => ({ ...f, order_numbers_input: e.target.value }))}
                  className="input w-full font-mono !text-sm"
                  placeholder="11078, 11082-11085"
                />
                <p className="text-[10px] text-gray-500 mt-1">
                  Aralık (-) veya virgül ile ayır
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-brand-border">
              <div className="text-xs text-gray-500">
                Önce siparişler <a href="/orders" className="text-accent hover:underline">Siparişler</a> sayfasından çekilmiş olmalı
              </div>
              <button type="submit" disabled={running} className="btn-primary">
                {running ? 'İşleniyor...' : '⚡ Çalıştır'}
              </button>
            </div>
          </form>

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
              ✗ {error}
            </div>
          )}

          {result && <PipelineResult result={result} onCopy={copyToClipboard} />}
        </>
      )}
    </div>
  )
}


function PipelineResult({ result, onCopy }) {
  const [activeTab, setActiveTab] = useState('output')
  const { stats, illustrator_output, raw_output, missing, kisiye_ozel, kalips, not_found, errors } = result

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
        <StatCard label="Sipariş" value={stats.total_orders} hint={stats.not_found_orders > 0 ? `${stats.not_found_orders} bulunamadı` : null} />
        <StatCard label="Toplam Ürün" value={stats.total_items} />
        <StatCard label="Kalıplı" value={stats.kodlu_items} color="emerald" />
        <StatCard label="Kalıpsız" value={stats.kodsuz_items} color={stats.kodsuz_items > 0 ? 'amber' : 'gray'} />
        <StatCard label="Kalıp Sayısı" value={stats.kalip_count} color="accent" />
        <StatCard label="Eksik Kısayol" value={stats.missing_shortcuts} color={stats.missing_shortcuts > 0 ? 'red' : 'gray'} />
        <StatCard label="Kişiye Özel" value={stats.kisiye_ozel} color={stats.kisiye_ozel > 0 ? 'pink' : 'gray'} />
      </div>

      {/* Not-found warning */}
      {not_found && not_found.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-xs text-amber-300">
          <strong>⚠ Bulunamayan siparişler ({not_found.length}):</strong> Bu siparişler DB'de yok. Önce <a href="/orders" className="underline">Siparişler</a> sayfasından çek.
          <div className="mt-1 font-mono">{not_found.join(', ')}</div>
        </div>
      )}

      {/* Errors */}
      {errors && errors.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-300">
          <strong>Hatalar:</strong>
          <ul className="mt-1 space-y-0.5">
            {errors.map((e, i) => <li key={i}>• {e}</li>)}
          </ul>
        </div>
      )}

      {/* Tabs */}
      <div className="card !p-0">
        <div className="flex border-b border-brand-border text-sm">
          <TabButton active={activeTab === 'output'} onClick={() => setActiveTab('output')}>
            Kalıp Çıktısı
          </TabButton>
          <TabButton active={activeTab === 'raw'} onClick={() => setActiveTab('raw')}>
            Raw (Birleştirilmemiş)
          </TabButton>
          <TabButton active={activeTab === 'kalips'} onClick={() => setActiveTab('kalips')}>
            Kalıplar ({kalips.length})
          </TabButton>
          {missing.length > 0 && (
            <TabButton active={activeTab === 'missing'} onClick={() => setActiveTab('missing')}>
              <span className="text-red-400">⚠ Eksik ({missing.length})</span>
            </TabButton>
          )}
          {kisiye_ozel.length > 0 && (
            <TabButton active={activeTab === 'kisiye'} onClick={() => setActiveTab('kisiye')}>
              <span className="text-pink-400">Kişiye Özel ({kisiye_ozel.length})</span>
            </TabButton>
          )}
        </div>

        <div className="p-4">
          {activeTab === 'output' && (
            <div>
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm font-medium text-gray-300">Illustrator için yapıştırılacak metin</h3>
                <button onClick={() => onCopy(illustrator_output)} className="btn-secondary !text-xs">
                  📋 Kopyala
                </button>
              </div>
              <pre className="bg-brand-input border border-brand-border rounded-lg p-3 text-xs text-gray-300 whitespace-pre-wrap max-h-[60vh] overflow-y-auto font-mono">
                {illustrator_output || '(boş)'}
              </pre>
            </div>
          )}

          {activeTab === 'raw' && (
            <div>
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm font-medium text-gray-300">Birleştirilmemiş çıktı (her kod ayrı)</h3>
                <button onClick={() => onCopy(raw_output)} className="btn-secondary !text-xs">
                  📋 Kopyala
                </button>
              </div>
              <pre className="bg-brand-input border border-brand-border rounded-lg p-3 text-xs text-gray-300 whitespace-pre-wrap max-h-[60vh] overflow-y-auto font-mono">
                {raw_output || '(boş)'}
              </pre>
            </div>
          )}

          {activeTab === 'kalips' && (
            <div className="space-y-3">
              {kalips.map((k, i) => (
                <div key={i} className="bg-brand-input border border-brand-border rounded-lg p-3">
                  <div className="flex justify-between items-center mb-2">
                    <div>
                      <span className="font-mono text-accent text-sm">{k.name}</span>
                      <span className="text-xs text-gray-500 ml-2">
                        {k.count} adet · {k.variation}
                      </span>
                      {k.is_merged && (
                        <span className="text-[10px] bg-purple-500/15 text-purple-300 px-1.5 py-0.5 rounded ml-2">
                          birleşik
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-xs space-y-0.5 max-h-40 overflow-y-auto">
                    {k.items.map((it, j) => (
                      <div key={j} className="text-gray-400 font-mono">
                        <span className="text-gray-600">[{it.order_num}]</span>{' '}
                        {it.phone} <span className="text-gray-500">"</span>
                        <span className="text-gray-300">{it.design}</span>
                        <span className="text-gray-500">"</span>
                        {it.yurtici && ' 🔵'}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'missing' && (
            <div>
              <p className="text-xs text-gray-500 mb-2">
                Bu tasarımlar için kısayol yok. <a href="/shortcuts" className="text-accent hover:underline">Kısayollar</a> sayfasından ekle, sonra pipeline'ı tekrar çalıştır.
              </p>
              <div className="space-y-1">
                {missing.map((m, i) => (
                  <div key={i} className="bg-brand-input border border-brand-border rounded-lg p-2 text-xs">
                    <div className="font-mono text-gray-300">{m.design}</div>
                    <div className="text-gray-500 mt-0.5">
                      {m.phone || '?'} · Sipariş #{m.order_num}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'kisiye' && (
            <div>
              <p className="text-xs text-gray-500 mb-2">
                Kişiye özel tasarımlar pipeline'a girmez; ayrıca işlenir.
              </p>
              <div className="space-y-2">
                {kisiye_ozel.map((k, i) => (
                  <div key={i} className="bg-brand-input border border-brand-border rounded-lg p-2 text-xs flex gap-2">
                    {k.image_url && (
                      <img
                        src={k.image_url}
                        alt=""
                        className="w-16 h-16 object-cover rounded border border-brand-border"
                        onError={e => e.target.style.display = 'none'}
                      />
                    )}
                    <div className="flex-1">
                      <div className="font-mono text-gray-300">#{k.order_num} — {k.customer}</div>
                      <div className="text-gray-500 mt-0.5">{k.title}</div>
                      {k.image_url && (
                        <a href={k.image_url} target="_blank" rel="noreferrer" className="text-[10px] text-accent hover:underline">
                          Görseli yeni sekmede aç
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


function StatCard({ label, value, hint, color = 'gray' }) {
  const colors = {
    gray: 'text-gray-200',
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
    red: 'text-red-400',
    pink: 'text-pink-400',
    accent: 'text-accent',
  }
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-3">
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`text-xl font-semibold ${colors[color]}`}>{value}</div>
      {hint && <div className="text-[10px] text-gray-600 mt-0.5">{hint}</div>}
    </div>
  )
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 border-b-2 transition-colors ${
        active
          ? 'border-accent text-accent'
          : 'border-transparent text-gray-400 hover:text-gray-200'
      }`}
    >
      {children}
    </button>
  )
}
