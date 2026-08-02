"use client";

// Tasarım Stüdyosu — müşteri kendi kılıfını tasarlar.
//
// Akış: kılıf seç → görsel yükle / yazı ekle → düzenle → kaydet.
// Hesabı olan kaldığı yerden devam eder (tasarım sunucuda saklanır);
// girişi olmayan da tasarlayabilir, kaydederken giriş istenir.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import Canvas from "@/components/studio/Canvas";
import { FONTS, fontCss } from "@/components/studio/fonts";
import { onizlemeUret } from "@/components/studio/preview";
import type {
  CaseTemplate, ImageLayer, Layer, LayerPatch, SavedDesign, TextLayer,
} from "@/components/studio/types";

const RENKLER = ["#111111", "#ffffff", "#e11d48", "#f59e0b", "#10b981",
  "#3b82f6", "#8b5cf6", "#ec4899"];
const TASLAK_ANAHTAR = "bernz_studyo_taslak";
const yeniId = () => Math.random().toString(36).slice(2, 10);

export default function TasarlaPage() {
  const [templates, setTemplates] = useState<CaseTemplate[]>([]);
  const [tpl, setTpl] = useState<CaseTemplate | null>(null);
  const [layers, setLayers] = useState<Layer[]>([]);
  const [secili, setSecili] = useState<string | null>(null);
  const [ad, setAd] = useState("Tasarımım");
  const [designId, setDesignId] = useState<string | null>(null);
  const [girisli, setGirisli] = useState(false);
  const [kayitli, setKayitli] = useState<SavedDesign[]>([]);
  const [durum, setDurum] = useState("");
  const [yukleniyor, setYukleniyor] = useState(false);
  const dosyaRef = useRef<HTMLInputElement>(null);

  // ── Yükleme ──
  useEffect(() => {
    fetch("/api/studio/templates")
      .then((r) => r.json())
      .then((d: CaseTemplate[]) => {
        setTemplates(Array.isArray(d) ? d : []);
        if (Array.isArray(d) && d.length) setTpl(d[0]);
      })
      .catch(() => setDurum("Kılıflar yüklenemedi"));
    fetch("/api/account/designs")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (Array.isArray(d)) { setGirisli(true); setKayitli(d); } })
      .catch(() => {});
  }, []);

  // Giriş yapılmamışken tarayıcıda taslak tut — girişten sonra devam edilir
  useEffect(() => {
    try {
      const ham = localStorage.getItem(TASLAK_ANAHTAR);
      if (!ham) return;
      const t = JSON.parse(ham);
      if (t?.layers?.length) { setLayers(t.layers); setAd(t.ad || "Tasarımım"); }
    } catch { /* bozuk taslak yok sayılır */ }
  }, []);
  useEffect(() => {
    if (designId) return;   // sunucuda kayıtlıysa yerel taslağa gerek yok
    try {
      localStorage.setItem(TASLAK_ANAHTAR, JSON.stringify({ layers, ad }));
    } catch { /* kota dolabilir — kritik değil */ }
  }, [layers, ad, designId]);

  const seciliKatman = useMemo(
    () => layers.find((l) => l.id === secili) || null, [layers, secili]);

  const guncelle = useCallback((id: string, patch: LayerPatch) => {
    setLayers((ls) => ls.map((l) => (l.id === id ? ({ ...l, ...patch } as Layer) : l)));
  }, []);

  // ── Görsel ekleme ──
  const gorselEkle = async (file: File | undefined) => {
    if (!file || !tpl) return;
    setYukleniyor(true); setDurum("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/studio/assets", { method: "POST", body: fd });
      const d = await res.json();
      if (!res.ok) throw new Error(d?.detail || "Yüklenemedi");

      // Baskı alanına oranını koruyarak sığdır
      const alanOran = (tpl.area.w * 1) / (tpl.area.h * 1);
      const gorselOran = d.width / d.height;
      let w = 0.8, h = 0.8;
      if (gorselOran > alanOran) h = (0.8 * alanOran) / gorselOran;
      else w = (0.8 * gorselOran) / alanOran;

      const yeni: ImageLayer = {
        id: yeniId(), type: "image", asset_id: d.asset_id, url: d.preview_url,
        x: (1 - w) / 2, y: (1 - h) / 2, w, h, rot: 0,
        src_w: d.width, src_h: d.height,
      };
      setLayers((ls) => [...ls, yeni]);
      setSecili(yeni.id);
    } catch (e) {
      setDurum(e instanceof Error ? e.message : "Görsel yüklenemedi");
    } finally {
      setYukleniyor(false);
      if (dosyaRef.current) dosyaRef.current.value = "";
    }
  };

  const yaziEkle = () => {
    const yeni: TextLayer = {
      id: yeniId(), type: "text", text: "Yazınız", font: "poppins",
      size: 0.1, color: "#ffffff", x: 0.1, y: 0.42, w: 0.8, rot: 0, align: "center",
    };
    setLayers((ls) => [...ls, yeni]);
    setSecili(yeni.id);
  };

  const sil = () => {
    if (!secili) return;
    setLayers((ls) => ls.filter((l) => l.id !== secili));
    setSecili(null);
  };
  const sirala = (yon: 1 | -1) => {
    if (!secili) return;
    setLayers((ls) => {
      const i = ls.findIndex((l) => l.id === secili);
      const j = i + yon;
      if (i < 0 || j < 0 || j >= ls.length) return ls;
      const kopya = [...ls];
      [kopya[i], kopya[j]] = [kopya[j], kopya[i]];
      return kopya;
    });
  };

  // Kılıfı tamamen kapla — taşan kısım kırpılır (en sık istenen işlem)
  const doldur = () => {
    if (!seciliKatman || seciliKatman.type !== "image" || !tpl) return;
    const im = seciliKatman as ImageLayer;
    const alanOran = tpl.area.w / tpl.area.h;
    const gOran = im.src_w / im.src_h;
    const crop = gOran > alanOran
      ? { x: (1 - alanOran / gOran) / 2, y: 0, w: alanOran / gOran, h: 1 }
      : { x: 0, y: (1 - gOran / alanOran) / 2, w: 1, h: gOran / alanOran };
    guncelle(im.id, { x: 0, y: 0, w: 1, h: 1, rot: 0, crop });
  };

  // ── Kaydetme ──
  const kaydet = async (durumDeger: "draft" | "ready" = "draft") => {
    if (!tpl) return;
    if (!girisli) {
      setDurum("Tasarımını kaydetmek için giriş yap — tasarımın kaybolmaz.");
      return;
    }
    setYukleniyor(true); setDurum("");
    try {
      const onizleme = await onizlemeUret(tpl, layers);
      const res = await fetch("/api/account/designs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: designId, name: ad, template_key: tpl.key,
          layers, status: durumDeger, preview_data_url: onizleme,
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d?.detail || "Kaydedilemedi");
      setDesignId(d.id);
      setDurum(durumDeger === "ready" ? "Tasarımın hazır ✓" : "Kaydedildi ✓");
      try { localStorage.removeItem(TASLAK_ANAHTAR); } catch { /* yok */ }
      fetch("/api/account/designs").then((r) => r.json())
        .then((l) => Array.isArray(l) && setKayitli(l)).catch(() => {});
    } catch (e) {
      setDurum(e instanceof Error ? e.message : "Kaydedilemedi");
    } finally { setYukleniyor(false); }
  };

  const tasarimAc = (d: SavedDesign) => {
    setDesignId(d.id);
    setAd(d.name);
    setLayers(d.layers || []);
    setSecili(null);
    const t = templates.find((x) => x.key === d.template_key);
    if (t) setTpl(t);
    setDurum("");
  };

  const tasarimSil = async (id: string) => {
    if (!confirm("Bu tasarım silinsin mi?")) return;
    await fetch(`/api/account/designs/${id}`, { method: "DELETE" });
    setKayitli((k) => k.filter((x) => x.id !== id));
    if (designId === id) { setDesignId(null); setLayers([]); }
  };

  // Baskı kalitesi uyarısı — görsel, basılacağı boyuta göre yeterli mi
  const kaliteUyarisi = useMemo(() => {
    if (!tpl) return null;
    const kotu = layers.filter((l) => {
      if (l.type !== "image") return false;
      const im = l as ImageLayer;
      const hedefPx = (im.w * tpl.print.width_mm / 25.4) * tpl.print.dpi;
      const kullanilan = im.crop ? im.src_w * im.crop.w : im.src_w;
      return kullanilan < hedefPx * 0.7;
    });
    return kotu.length ? kotu.length : null;
  }, [layers, tpl]);

  if (!tpl) {
    return (
      <main className="max-w-3xl mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-semibold">Tasarım Stüdyosu</h1>
        <p className="mt-3 text-zinc-500">
          {templates.length === 0
            ? "Kılıf şablonları henüz hazırlanıyor. Çok yakında kendi tasarımını yapabileceksin."
            : "Yükleniyor…"}
        </p>
      </main>
    );
  }

  return (
    <main className="max-w-6xl mx-auto px-4 py-6">
      <style>{fontCss}</style>

      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Kendi Kılıfını Tasarla</h1>
        <input value={ad} onChange={(e) => setAd(e.target.value)} maxLength={120}
          className="text-sm border border-zinc-300 rounded-lg px-2 py-1 w-44" />
        <div className="ml-auto flex gap-2">
          <button onClick={() => kaydet("draft")} disabled={yukleniyor}
            className="px-3 py-2 rounded-xl border border-zinc-300 text-sm disabled:opacity-40">
            Kaydet
          </button>
          <button onClick={() => kaydet("ready")} disabled={yukleniyor || layers.length === 0}
            className="px-4 py-2 rounded-xl bg-zinc-900 text-white text-sm font-medium disabled:opacity-40">
            Tasarımım hazır
          </button>
        </div>
      </div>

      {durum && (
        <p className="mt-2 text-sm text-zinc-700 bg-zinc-100 rounded-lg px-3 py-2">
          {durum}
          {!girisli && (
            <Link href="/hesap" className="underline ml-2">Giriş yap →</Link>
          )}
        </p>
      )}

      <div className="mt-4 grid lg:grid-cols-[1fr_320px] gap-6 items-start">
        {/* Tuval */}
        <div className="flex justify-center bg-zinc-100 rounded-2xl p-4">
          <Canvas template={tpl} layers={layers} selected={secili}
            onSelect={setSecili} onChange={guncelle} />
        </div>

        {/* Araçlar */}
        <div className="space-y-4">
          <div>
            <div className="text-xs text-zinc-500 mb-1.5">Kılıf tipi</div>
            <div className="flex gap-2 flex-wrap">
              {templates.map((t) => (
                <button key={t.key} onClick={() => setTpl(t)}
                  className={`px-3 py-1.5 rounded-xl text-xs border transition ${t.key === tpl.key
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-300 hover:border-zinc-500"}`}>
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <button onClick={() => dosyaRef.current?.click()} disabled={yukleniyor}
              className="flex-1 px-3 py-2.5 rounded-xl border border-zinc-300 text-sm disabled:opacity-40">
              🖼️ {yukleniyor ? "Yükleniyor…" : "Görsel ekle"}
            </button>
            <button onClick={yaziEkle}
              className="flex-1 px-3 py-2.5 rounded-xl border border-zinc-300 text-sm">
              ✏️ Yazı ekle
            </button>
            <input ref={dosyaRef} type="file" accept="image/*" className="hidden"
              onChange={(e) => gorselEkle(e.target.files?.[0])} />
          </div>

          {kaliteUyarisi && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
              ⚠️ {kaliteUyarisi} görselin çözünürlüğü basılacağı boyut için düşük —
              baskıda bulanık çıkabilir. Daha büyük bir dosya yüklemeni öneririz.
            </p>
          )}

          {/* Seçili katman ayarları */}
          {seciliKatman ? (
            <div className="border border-zinc-200 rounded-2xl p-3 space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                {seciliKatman.type === "image" ? "Görsel" : "Yazı"}
                <button onClick={() => sirala(1)} title="Öne getir"
                  className="ml-auto text-xs px-2 py-1 rounded-lg border border-zinc-200">↑</button>
                <button onClick={() => sirala(-1)} title="Arkaya gönder"
                  className="text-xs px-2 py-1 rounded-lg border border-zinc-200">↓</button>
                <button onClick={sil} className="text-xs px-2 py-1 rounded-lg text-red-600">Sil</button>
              </div>

              {seciliKatman.type === "text" && (
                <>
                  <textarea value={(seciliKatman as TextLayer).text} rows={2} maxLength={200}
                    onChange={(e) => guncelle(seciliKatman.id, { text: e.target.value })}
                    className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm" />
                  <select value={(seciliKatman as TextLayer).font}
                    onChange={(e) => guncelle(seciliKatman.id, { font: e.target.value })}
                    className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm">
                    {FONTS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
                  </select>
                  <div className="flex gap-1.5 flex-wrap">
                    {RENKLER.map((c) => (
                      <button key={c} onClick={() => guncelle(seciliKatman.id, { color: c })}
                        className={`w-7 h-7 rounded-full border-2 ${
                          (seciliKatman as TextLayer).color === c ? "border-zinc-900" : "border-zinc-200"}`}
                        style={{ background: c }} aria-label={c} />
                    ))}
                  </div>
                  <label className="block text-xs text-zinc-500">
                    Yazı boyutu
                    <input type="range" min="0.03" max="0.3" step="0.005"
                      value={(seciliKatman as TextLayer).size}
                      onChange={(e) => guncelle(seciliKatman.id, { size: Number(e.target.value) })}
                      className="w-full" />
                  </label>
                  <div className="flex gap-1.5">
                    {(["left", "center", "right"] as const).map((h) => (
                      <button key={h} onClick={() => guncelle(seciliKatman.id, { align: h })}
                        className={`flex-1 text-xs py-1.5 rounded-lg border ${
                          (seciliKatman as TextLayer).align === h
                            ? "border-zinc-900" : "border-zinc-200"}`}>
                        {h === "left" ? "Sola" : h === "center" ? "Ortala" : "Sağa"}
                      </button>
                    ))}
                  </div>
                </>
              )}

              {seciliKatman.type === "image" && (
                <>
                  <button onClick={doldur}
                    className="w-full text-sm py-2 rounded-lg border border-zinc-300">
                    Kılıfı tamamen kapla
                  </button>
                  <label className="block text-xs text-zinc-500">
                    Yakınlaştır (kırpar)
                    <input type="range" min="0.3" max="1" step="0.02"
                      value={(seciliKatman as ImageLayer).crop?.w ?? 1}
                      onChange={(e) => {
                        const w = Number(e.target.value);
                        const im = seciliKatman as ImageLayer;
                        const eski = im.crop || { x: 0, y: 0, w: 1, h: 1 };
                        const h = Math.min(1, eski.h * (w / eski.w));
                        guncelle(im.id, {
                          crop: {
                            w, h,
                            x: Math.min(Math.max(0, eski.x + (eski.w - w) / 2), 1 - w),
                            y: Math.min(Math.max(0, eski.y + (eski.h - h) / 2), 1 - h),
                          },
                        });
                      }}
                      className="w-full" />
                  </label>
                  <label className="block text-xs text-zinc-500">
                    Döndür
                    <input type="range" min="-180" max="180" step="1"
                      value={(seciliKatman as ImageLayer).rot || 0}
                      onChange={(e) => guncelle(seciliKatman.id, { rot: Number(e.target.value) })}
                      className="w-full" />
                  </label>
                  <p className="text-[11px] text-zinc-400">
                    Orijinal: {(seciliKatman as ImageLayer).src_w}×{(seciliKatman as ImageLayer).src_h} px
                  </p>
                </>
              )}
            </div>
          ) : (
            <p className="text-xs text-zinc-500 border border-dashed border-zinc-300 rounded-2xl p-3">
              Düzenlemek için tuvaldeki bir öğeye dokun. Sürükleyerek taşı, köşedeki
              beyaz daireden boyutlandır, üstteki ↻ ile döndür.
            </p>
          )}

          {/* Kayıtlı tasarımlar */}
          <div>
            <div className="text-xs text-zinc-500 mb-1.5">
              Tasarımlarım {girisli ? "" : "(giriş yapınca burada saklanır)"}
            </div>
            {girisli && kayitli.length > 0 ? (
              <div className="grid grid-cols-3 gap-2">
                {kayitli.map((d) => (
                  <div key={d.id} className="relative group">
                    <button onClick={() => tasarimAc(d)}
                      className={`block w-full rounded-xl overflow-hidden border ${
                        d.id === designId ? "border-zinc-900" : "border-zinc-200"}`}>
                      {d.preview_url
                        ? <img src={d.preview_url} alt={d.name} className="w-full" />
                        : <div className="aspect-[1/2] bg-zinc-100" />}
                    </button>
                    <div className="text-[10px] truncate mt-0.5">{d.name}</div>
                    {d.status !== "ordered" && (
                      <button onClick={() => tasarimSil(d.id)}
                        className="absolute top-1 right-1 bg-white/90 rounded-full w-5 h-5 text-xs
                          opacity-0 group-hover:opacity-100 transition">×</button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-zinc-400">
                {girisli ? "Henüz kayıtlı tasarımın yok." : (
                  <>Hesap açınca tasarımların burada saklanır ve istediğin zaman
                    kaldığın yerden devam edersin. <Link href="/hesap" className="underline">Giriş yap</Link></>
                )}
              </p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
