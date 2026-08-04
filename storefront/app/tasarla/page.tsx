"use client";

// Tasarım Stüdyosu — müşteri kendi kılıfını tasarlar.
//
// Akış: kılıf seç → görsel yükle / yazı ekle → düzenle → kaydet.
// Hesabı olan kaldığı yerden devam eder (tasarım sunucuda saklanır);
// girişi olmayan da tasarlayabilir, kaydederken giriş istenir.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useCart } from "@/lib/cart";
import Link from "next/link";
import Canvas from "@/components/studio/Canvas";
import { FONTS, FONT_GRUPLARI, fontCss, trUyarisi } from "@/components/studio/fonts";
import { BASKI_BEYAZ, PALET, basilabilirRenk, cmykYazi, hexNormalize } from "@/components/studio/renk";
import { onizlemeUret } from "@/components/studio/preview";
import type {
  CaseTemplate, ImageLayer, Layer, LayerPatch, OverlayLayer, SavedDesign,
  StudioOverlay, TextLayer,
} from "@/components/studio/types";

const TASLAK_ANAHTAR = "bernz_studyo_taslak";

interface StudioUrun {
  slug: string;
  title: string;
  price: string;
  images: { url: string }[];
  variants: { id: string; model_display: string; price: string; in_stock: boolean }[];
}
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
  const { addItem, setDrawerOpen } = useCart();
  // Stüdyo ürünü: fiyat ve telefon modelleri panelde secilen bu urunden gelir
  const [overlays, setOverlays] = useState<StudioOverlay[]>([]);
  const [urun, setUrun] = useState<StudioUrun | null>(null);
  const [modelId, setModelId] = useState("");
  const [sepetAcik, setSepetAcik] = useState(false);

  // ── Yükleme ──
  useEffect(() => {
    // Ürün sayfasındaki modülden gelindiyse o kılıf ve ürün seçili açılır
    const q = new URLSearchParams(window.location.search);
    const kilifKey = q.get("kilif");
    const urunSlug = q.get("urun");

    fetch("/api/studio/templates")
      .then((r) => r.json())
      .then((d: CaseTemplate[]) => {
        setTemplates(Array.isArray(d) ? d : []);
        if (Array.isArray(d) && d.length) {
          setTpl(d.find((t) => t.key === kilifKey) || d[0]);
        }
      })
      .catch(() => setDurum("Kılıflar yüklenemedi"));
    fetch("/api/shop-config")
      .then((r) => (r.ok ? r.json() : null))
      .then((c) => {
        const slug = urunSlug || c?.settings?.studio_product_slug;
        if (!slug) return;
        return fetch(`/api/product/${slug}`).then((r) => (r.ok ? r.json() : null))
          .then((p) => { if (p) setUrun(p); });
      })
      .catch(() => {});
    fetch("/api/studio/overlays")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setOverlays(Array.isArray(d) ? d : []))
      .catch(() => {});
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
  // Mobilde sabit alt eylem çubuğu var — yüzen destek balonları yukarı çıksın
  useEffect(() => {
    document.body.classList.add("alt-cubuk-var");
    return () => document.body.classList.remove("alt-cubuk-var");
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
      size: 0.1, color: BASKI_BEYAZ, x: 0.1, y: 0.42, w: 0.8, rot: 0, align: "center",
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

  // ── Hizalama (Illustrator mantığı) ──
  // Görselin yüksekliği katmanda yazılı; YAZININ yüksekliği ise metnin
  // kendisinden doğar, o yüzden tuvaldeki gerçek kutusu ölçülür.
  const katmanYuksekligi = (l: Layer): number => {
    if (l.type === "image") return (l as ImageLayer).h;
    const alan = document.querySelector("[data-baski-alani]") as HTMLElement | null;
    const el = document.querySelector(`[data-katman="${l.id}"]`) as HTMLElement | null;
    if (!alan || !el || !alan.clientHeight) return (l as TextLayer).size * 1.15;
    return el.offsetHeight / alan.clientHeight;
  };

  type Hiza = "sol" | "yatay-orta" | "sag" | "ust" | "dikey-orta" | "alt" | "orta";
  const hizala = (yon: Hiza) => {
    if (!seciliKatman) return;
    const l = seciliKatman;
    const w = l.type === "image" ? (l as ImageLayer).w : (l as TextLayer).w;
    const h = katmanYuksekligi(l);
    const yama: LayerPatch = {};
    if (yon === "sol" || yon === "orta" || yon === "yatay-orta" || yon === "sag") {
      yama.x = yon === "sol" ? 0 : yon === "sag" ? 1 - w : (1 - w) / 2;
    }
    if (yon === "ust" || yon === "orta" || yon === "dikey-orta" || yon === "alt") {
      yama.y = yon === "ust" ? 0 : yon === "alt" ? 1 - h : (1 - h) / 2;
    }
    guncelle(l.id, yama);
  };

  // ── Hazır şablonlar (overlay) ──
  // Seçili kılıfa ait olanlar + tüm kılıflarda geçerli olanlar listelenir.
  const uygunOverlaylar = useMemo(
    () => overlays.filter((o) => !o.template_key || o.template_key === tpl?.key),
    [overlays, tpl],
  );
  const seciliOverlay = layers.find((l) => l.type === "overlay") as OverlayLayer | undefined;

  const overlaySec = (o: StudioOverlay) => {
    setLayers((ls) => {
      const digerleri = ls.filter((l) => l.type !== "overlay");   // tek şablon
      if (seciliOverlay?.overlay_id === o.id) return digerleri;   // aynısına basınca kaldır
      const yeni: OverlayLayer = {
        id: yeniId(), type: "overlay", overlay_id: o.id, url: o.image_url, label: o.label,
      };
      return [...digerleri, yeni];
    });
  };

  // Kırpma modu: görsel tutamakları ölçekleme yerine kenardan kırpar
  const [kirpmaModu, setKirpmaModu] = useState(false);

  // Renk seçimi — saf beyaz (CMYK 0,0,0,0) baskıda görünmez, otomatik düzeltilir
  const [hexGiris, setHexGiris] = useState("");
  const [renkUyari, setRenkUyari] = useState("");
  const renkUygula = (ham: string) => {
    if (!seciliKatman) return;
    const { renk, duzeltildi } = basilabilirRenk(ham);
    guncelle(seciliKatman.id, { color: renk });
    setRenkUyari(duzeltildi
      ? "Saf beyaz (CMYK 0,0,0,0) baskı makinesinde görünmez — basılabilir beyaza (CMYK 0,0,0,5) çevrildi."
      : "");
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

  const sepeteEkle = async () => {
    if (!tpl || !urun) return;
    const model = urun.variants.find((v) => v.id === modelId);
    if (!model) { setDurum("Telefon modelini seç"); return; }
    if (!girisli) {
      setDurum("Sipariş için giriş yap — tasarımın hesabına kaydedilecek.");
      return;
    }
    // Sepete eklenen tasarım SUNUCUDA kayıtlı olmalı; önce kaydet
    setYukleniyor(true); setDurum("");
    try {
      const onizleme = await onizlemeUret(tpl, layers);
      const res = await fetch("/api/account/designs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: designId, name: ad, template_key: tpl.key, layers,
          status: "ready", preview_data_url: onizleme,
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d?.detail || "Kaydedilemedi");
      setDesignId(d.id);
      addItem({
        variantId: model.id,
        productSlug: urun.slug,
        title: urun.title,
        modelDisplay: model.model_display,
        variation: null,
        price: model.price || urun.price,
        image: d.preview_url || urun.images?.[0]?.url || null,
        designId: d.id,
        designName: d.name,
        designPreview: d.preview_url || null,
      });
      setSepetAcik(false);
      setDrawerOpen(true);
      setDurum("Tasarımın sepete eklendi ✓");
      try { localStorage.removeItem(TASLAK_ANAHTAR); } catch { /* yok */ }
    } catch (e) {
      setDurum(e instanceof Error ? e.message : "Sepete eklenemedi");
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
    <main className="max-w-6xl mx-auto px-3 sm:px-4 py-4 sm:py-6 pb-24 lg:pb-6">
      <style>{fontCss}</style>

      <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
        <h1 className="text-lg sm:text-xl font-semibold">Kendi Kılıfını Tasarla</h1>
        <input value={ad} onChange={(e) => setAd(e.target.value)} maxLength={120}
          className="text-sm border border-zinc-300 rounded-lg px-2 py-1 flex-1 min-w-[8rem] sm:flex-none sm:w-44" />
        {/* Mobilde ana eylemler ALT ÇUBUKTA (aşağıda) — burada gizlenir */}
        <div className="ml-auto hidden lg:flex gap-2">
          <button onClick={() => kaydet("draft")} disabled={yukleniyor}
            className="px-3 py-2 rounded-xl border border-zinc-300 text-sm disabled:opacity-40">
            Kaydet
          </button>
          <button onClick={() => setSepetAcik(true)}
            disabled={yukleniyor || layers.length === 0 || !urun}
            title={!urun ? "Stüdyo ürünü henüz ayarlanmadı" : ""}
            className="px-4 py-2 rounded-xl bg-zinc-900 text-white text-sm font-medium disabled:opacity-40">
            🛒 Sepete Ekle
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
        <div className="flex justify-center bg-zinc-100 rounded-2xl p-2 sm:p-4">
          <Canvas template={tpl} layers={layers} selected={secili}
            onSelect={setSecili} onChange={guncelle} kirpma={kirpmaModu}
            maxHeight={typeof window !== "undefined" && window.innerWidth < 640 ? 380 : 560} />
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

          {/* Hazır şablonlar — müşterinin görselinin ÜSTÜNE binen çerçeveler.
              Yüklenen görseller çerçevenin altında, yazılar üstünde kalır. */}
          {uygunOverlaylar.length > 0 && (
            <div>
              <div className="text-xs text-zinc-500 mb-1.5">
                Hazır şablonlardan seç
                {seciliOverlay && (
                  <button onClick={() => setLayers((ls) => ls.filter((l) => l.type !== "overlay"))}
                    className="ml-2 text-[11px] underline text-zinc-600">kaldır</button>
                )}
              </div>
              <div className="grid grid-cols-4 gap-2">
                {uygunOverlaylar.map((o) => (
                  <button key={o.id} onClick={() => overlaySec(o)} title={o.label}
                    className={`relative rounded-xl border-2 overflow-hidden bg-zinc-50
                      aspect-[9/16] transition ${
                        seciliOverlay?.overlay_id === o.id
                          ? "border-zinc-900" : "border-zinc-200 hover:border-zinc-400"}`}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={o.thumb_url} alt={o.label}
                      className="w-full h-full object-contain" />
                    {seciliOverlay?.overlay_id === o.id && (
                      <span className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-zinc-900
                        text-white text-[10px] flex items-center justify-center">✓</span>
                    )}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-zinc-400 mt-1.5 leading-snug">
                Şablon en üst katmandır: yüklediğin görseller altında kalır, yazılar
                şablonun üstüne yazılır.
              </p>
            </div>
          )}

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

              {/* Otomatik yaslama — baskı alanına göre (Illustrator mantığı) */}
              <div>
                <div className="text-[11px] text-zinc-500 mb-1">Yasla</div>
                <div className="grid grid-cols-3 gap-1">
                  {([
                    ["sol", "⇤", "Sola"],
                    ["yatay-orta", "↔", "Yatay ortala"],
                    ["sag", "⇥", "Sağa"],
                    ["ust", "⇡", "Üste"],
                    ["dikey-orta", "↕", "Dikey ortala"],
                    ["alt", "⇣", "Alta"],
                  ] as const).map(([yon, ikon, baslik]) => (
                    <button key={yon} onClick={() => hizala(yon)} title={`${baslik} yasla`}
                      className="flex items-center justify-center gap-1 text-[11px] py-1.5
                        rounded-lg border border-zinc-200 hover:border-zinc-900
                        hover:bg-zinc-50 transition">
                      <span className="text-sm leading-none">{ikon}</span> {baslik}
                    </button>
                  ))}
                  <button onClick={() => hizala("orta")} title="Tam ortala"
                    className="col-span-3 flex items-center justify-center gap-1 text-[11px] py-1.5
                      rounded-lg border border-zinc-200 hover:border-zinc-900
                      hover:bg-zinc-50 transition">
                    <span className="text-sm leading-none">✛</span> Tam ortala
                  </button>
                </div>
              </div>

              {seciliKatman.type === "text" && (
                <>
                  <textarea value={(seciliKatman as TextLayer).text} rows={2} maxLength={200}
                    onChange={(e) => guncelle(seciliKatman.id, { text: e.target.value })}
                    className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm" />
                  <select value={(seciliKatman as TextLayer).font}
                    onChange={(e) => guncelle(seciliKatman.id, { font: e.target.value })}
                    className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm">
                    {FONT_GRUPLARI.map((g) => (
                      <optgroup key={g} label={g}>
                        {FONTS.filter((f) => f.grup === g).map((f) => (
                          <option key={f.key} value={f.key}>{f.label}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  {(() => {
                    const uyari = trUyarisi((seciliKatman as TextLayer).font,
                      (seciliKatman as TextLayer).text || "");
                    return uyari ? (
                      <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200
                        rounded-lg px-2 py-1.5">⚠️ {uyari}</p>
                    ) : null;
                  })()}
                  <div>
                    <div className="flex gap-1.5 flex-wrap">
                      {PALET.map((c) => (
                        <button key={c.hex} onClick={() => renkUygula(c.hex)}
                          className={`w-7 h-7 rounded-full border-2 ${
                            (seciliKatman as TextLayer).color === c.hex
                              ? "border-zinc-900" : "border-zinc-200"}`}
                          style={{ background: c.hex }} title={c.ad} aria-label={c.ad} />
                      ))}
                    </div>
                    <div className="flex items-center gap-1.5 mt-2">
                      <input type="color"
                        value={hexNormalize((seciliKatman as TextLayer).color) || "#000000"}
                        onChange={(e) => renkUygula(e.target.value)}
                        className="w-9 h-9 rounded-lg border border-zinc-300 bg-white p-0.5 cursor-pointer"
                        aria-label="Renk seçici" />
                      <input value={hexGiris} placeholder="#RRGGBB"
                        onChange={(e) => setHexGiris(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key !== "Enter") return;
                          const n = hexNormalize(hexGiris);
                          if (!n) { setRenkUyari("Geçerli bir renk kodu gir (örn. #1a2b3c)."); return; }
                          renkUygula(n); setHexGiris("");
                        }}
                        className="flex-1 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm font-mono"
                        maxLength={7} />
                      <button
                        onClick={() => {
                          const n = hexNormalize(hexGiris);
                          if (!n) { setRenkUyari("Geçerli bir renk kodu gir (örn. #1a2b3c)."); return; }
                          renkUygula(n); setHexGiris("");
                        }}
                        className="text-xs px-2.5 py-2 rounded-lg border border-zinc-300">Uygula</button>
                    </div>
                    <p className="text-[11px] text-zinc-400 mt-1">
                      Baskı değeri: {cmykYazi((seciliKatman as TextLayer).color)}
                    </p>
                    {renkUyari && (
                      <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200
                        rounded-lg px-2 py-1.5 mt-1">⚠️ {renkUyari}</p>
                    )}
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

                  {/* Kırpma modu — tutamaklar görseli ezmeden kenardan kırpar */}
                  <div className={`rounded-xl border p-2.5 ${
                    kirpmaModu ? "border-zinc-900 bg-zinc-50" : "border-zinc-200"}`}>
                    <button onClick={() => setKirpmaModu((k) => !k)}
                      className="w-full flex items-center gap-2 text-sm font-medium">
                      <span>✂️ Kırpma modu</span>
                      <span className={`ml-auto text-[11px] px-2 py-0.5 rounded-full ${
                        kirpmaModu ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-500"}`}>
                        {kirpmaModu ? "Açık" : "Kapalı"}
                      </span>
                    </button>
                    <p className="text-[11px] text-zinc-500 mt-1.5 leading-snug">
                      {kirpmaModu
                        ? "Kenar ve köşelerden çekerek görselin istemediğin kısmını kırp — görsel ezilmez, oran korunur."
                        : "Aç, sonra tutamaklardan çekerek görseli kenarlardan kırp (oranı bozulmadan)."}
                    </p>
                    {(seciliKatman as ImageLayer).crop && (
                      <button
                        onClick={() => guncelle(seciliKatman.id, {
                          crop: { x: 0, y: 0, w: 1, h: 1 },
                        })}
                        className="mt-2 w-full text-xs py-1.5 rounded-lg border border-zinc-300">
                        Kırpmayı sıfırla
                      </button>
                    )}
                  </div>
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

      {sepetAcik && urun && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={(e) => e.target === e.currentTarget && setSepetAcik(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-white rounded-2xl w-full max-w-sm p-4 space-y-3">
            <h3 className="font-semibold">Telefon modelini seç</h3>
            <p className="text-xs text-zinc-500 -mt-2">
              Tasarımın bu modele göre basılacak.
            </p>
            <select value={modelId} onChange={(e) => setModelId(e.target.value)}
              className="w-full border border-zinc-300 rounded-xl px-3 py-2 text-sm">
              <option value="">Model seçin…</option>
              {urun.variants.filter((v) => v.in_stock).map((v) => (
                <option key={v.id} value={v.id}>{v.model_display}</option>
              ))}
            </select>
            <div className="text-sm">
              Fiyat:{" "}
              <b>{urun.variants.find((v) => v.id === modelId)?.price || urun.price} ₺</b>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setSepetAcik(false)}
                className="px-3 py-2 rounded-xl border border-zinc-300 text-sm">Vazgeç</button>
              <button onClick={sepeteEkle} disabled={!modelId || yukleniyor}
                className="px-4 py-2 rounded-xl bg-zinc-900 text-white text-sm disabled:opacity-40">
                {yukleniyor ? "Ekleniyor…" : "Sepete ekle"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mobil alt çubuk: ana eylemler parmak erişiminde sabit dursun */}
      <div className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur
        border-t border-zinc-200 px-3 py-2 flex gap-2">
        <button onClick={() => kaydet("draft")} disabled={yukleniyor}
          className="flex-1 py-3 rounded-xl border border-zinc-300 text-sm disabled:opacity-40">
          Kaydet
        </button>
        <button onClick={() => setSepetAcik(true)}
          disabled={yukleniyor || layers.length === 0 || !urun}
          className="flex-[2] py-3 rounded-xl bg-zinc-900 text-white text-sm font-medium disabled:opacity-40">
          🛒 Sepete Ekle
        </button>
      </div>
    </main>
  );
}
