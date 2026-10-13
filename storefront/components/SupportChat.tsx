"use client";

// Destek asistanı — kurallı 7/24 yardım (AI değildir). Sistem verisiyle çalışır.
// MARKA ADI mağazadan gelir (magaza prop'u): aynı kurulumda birden fazla mağaza
// olabilir, hiçbiri diğerinin markasını göstermemeli.
// sipariş durumu (e-posta ile), model uygunluğu (katalog araması), kargo/iade
// bilgisi ve panelden tanımlanan SSS yanıtları. Sağ altta sohbet balonu.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const DAVET_ANAHTARI = "support-davet-kapandi";
const DAVET_SUSKUN_GUN = 7;
import { useTexts } from "@/lib/texts";

interface Faq { q: string; a: string }

interface ModelRow { model: string; product_count: number; sample_title: string; sample_slug: string }

type Msg =
  | { from: "bot" | "user"; text: string }
  | { from: "bot"; models: ModelRow[] };

type Mode = "menu" | "order_email" | "model";

export default function SupportChat({
  faq = [],
  whatsappVisible = false,
  magaza = "Destek",
}: {
  faq?: Faq[];
  whatsappVisible?: boolean;
  /** Mağazanın adı — asistanın kendini tanıttığı marka */
  magaza?: string;
}) {
  const asistanAdi = `${magaza} Destek`;
  const t = useTexts();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("menu");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    { from: "bot", text: `Merhaba! 👋 Ben ${asistanAdi}. Siparişiniz, ürünlerimiz ya da kargo hakkında 7/24 yardımcı olurum. Aşağıdan bir konu seçin ya da yazın.` },
  ]);
  const bottomRef = useRef<HTMLDivElement>(null);
  // Karşılama baloncuğu: müşteri desteğin orada olduğunu fark etsin.
  // Kapatılınca 7 gün çıkmaz (rahatsız etmemek için). Eskiden yalnız o sekme
  // için hatırlanıyordu VE kaydırma dinleyicisi kapatıldıktan sonra da
  // çalışmaya devam ettiği için ilk kaydırmada balon yeniden açılıyordu.
  const [davet, setDavet] = useState(false);
  const davetKapali = useRef(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, open]);

  // Karşılama baloncuğu NE ZAMAN çıkar:
  //   2,5 saniye çok erkendi — telefonda ürün başlığının üstüne biniyordu ve
  //   müşteri daha ürünü görmeden iki katmanla karşılaşıyordu (canlı ölçüldü).
  //   Artık İKİ koşul birden gerekir: 18 saniye geçmiş olmalı VE müşteri
  //   sayfayı kaydırmış olmalı. Kaydırma "ilgileniyorum" sinyalidir; hiç
  //   kaydırmadan ayrılan ziyaretçiyi rahatsız etmenin bir karşılığı yok.
  useEffect(() => {
    try {
      const son = Number(localStorage.getItem(DAVET_ANAHTARI) || 0);
      if (son && Date.now() - son < DAVET_SUSKUN_GUN * 864e5) return;
      // Kapatılmasa da bir ziyarette (sekme oturumu) yalnız BİR kez gösterilir
      if (sessionStorage.getItem("support-davet-gosterildi")) return;
    } catch { /* yok */ }

    let sureDoldu = false;
    let kaydirdi = false;
    const belki = () => {
      if (!sureDoldu || !kaydirdi || davetKapali.current) return;
      davetKapali.current = true;   // bu sayfada bir kez
      setDavet(true);
      try { sessionStorage.setItem("support-davet-gosterildi", "1"); } catch { /* yok */ }
      window.removeEventListener("scroll", kaydirma);
    };
    const z = setTimeout(() => { sureDoldu = true; belki(); }, 18000);
    const kaydirma = () => {
      if (window.scrollY > 240) { kaydirdi = true; belki(); }
    };
    window.addEventListener("scroll", kaydirma, { passive: true });
    return () => { clearTimeout(z); window.removeEventListener("scroll", kaydirma); };
  }, []);

  const davetiKapat = () => {
    davetKapali.current = true;
    setDavet(false);
    try { localStorage.setItem(DAVET_ANAHTARI, String(Date.now())); } catch { /* yok */ }
  };

  const push = (...m: Msg[]) => setMsgs((prev) => [...prev, ...m]);

  const askOrder = () => {
    setMode("order_email");
    push({ from: "user", text: "📦 Siparişim nerede?" },
      { from: "bot", text: "Sipariş verirken kullandığınız e-posta adresini yazar mısınız? (İsterseniz sonuna sipariş numaranızı da ekleyin, örn. \"ornek@mail.com #1005\")" });
  };

  const askModel = () => {
    setMode("model");
    push({ from: "user", text: "📱 Telefonuma uygun kılıf var mı?" },
      { from: "bot", text: "Telefon modelinizi yazın — örn. \"iPhone 15 Pro\" ya da \"Samsung S24\"." });
  };

  const answerShipping = () => {
    push({ from: "user", text: "🚚 Kargo süresi" },
      { from: "bot", text: `${t.trust_shipping}. Siparişiniz kargoya verildiğinde takip bağlantısı e-postanıza gönderilir. "Siparişim nerede?" seçeneğiyle güncel durumu anında görebilirsiniz.` });
    setMode("menu");
  };

  const answerReturns = () => {
    push({ from: "user", text: "↩️ İade & değişim" },
      { from: "bot", text: `${t.trust_return} sunuyoruz. Ürün elinize ulaştıktan sonra 14 gün içinde iade/değişim talebi oluşturabilirsiniz. Ayrıntılar: /iade sayfası. Sipariş takip sayfanızdaki "Sorun bildir" bağlantısından da talep açabilirsiniz.` });
    setMode("menu");
  };

  const answerFaq = (f: Faq) => {
    push({ from: "user", text: f.q }, { from: "bot", text: f.a });
    setMode("menu");
  };

  const lookupOrders = async (raw: string) => {
    const orderNo = raw.match(/#?\s?(\d{2,})\s*$/)?.[1];
    const email = raw.replace(/#?\s?\d{2,}\s*$/, "").trim();
    if (!/.+@.+\..+/.test(email)) {
      push({ from: "bot", text: "Bu bir e-posta adresine benzemiyor — lütfen \"ornek@mail.com\" biçiminde yazın." });
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/support/order-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, order_no: orderNo || null }),
      });
      if (!res.ok) {
        push({ from: "bot", text: "Şu an sisteme ulaşamadım — birkaç dakika sonra tekrar dener misiniz?" });
        return;
      }
      const data = await res.json();
      push({
        from: "bot",
        text: data?.mesaj || "Sipariş takip bağlantısını e-posta adresine gönderdim. Gelen kutunu (ve spam klasörünü) kontrol et.",
      }, { from: "bot", text: "Başka bir konuda yardımcı olabilir miyim?" });
      setMode("menu");
    } catch {
      push({ from: "bot", text: "Şu an sisteme ulaşamadım — birkaç dakika sonra tekrar dener misiniz?" });
    } finally { setBusy(false); }
  };

  const lookupModel = async (raw: string) => {
    setBusy(true);
    try {
      const res = await fetch(`/api/support/model-check?q=${encodeURIComponent(raw)}`);
      const data = res.ok ? await res.json() : { models: [] };
      if ((data.models || []).length === 0) {
        // "Yok" deyip bırakmak yerine tekrar denemeye ve tüm modellere yönlendir:
        // müşteri burada çıkarsa satış kaybedilir. Mod "model"de kalır.
        push({ from: "bot", text: `"${raw}" adında bir model bulamadım. Marka ve modeli birlikte yazar mısınız? Örn. "iPhone 15 Pro Max", "Samsung S24 Ultra", "Redmi Note 13". Listede yoksa WhatsApp'tan yazın, üretim ekibimiz hemen kontrol etsin.` });
      } else if (data.tahmini) {
        // Birebir tutmadı (yazım farkı olabilir): yakın modelleri öner
        push({ from: "bot", text: "Şunlardan biri mi? Modelinize tıklayın:" },
          { from: "bot", models: data.models },
          { from: "bot", text: "Listede yoksa modeli tekrar yazabilirsiniz." });
      } else {
        push({ from: "bot", models: data.models },
          { from: "bot", text: "Modelinize tıklayarak ürünleri inceleyebilirsiniz. Başka bir sorunuz var mı?" });
        setMode("menu");
      }
    } catch {
      push({ from: "bot", text: "Şu an sisteme ulaşamadım — birkaç dakika sonra tekrar dener misiniz?" });
    } finally { setBusy(false); }
  };

  const send = () => {
    const raw = input.trim();
    if (!raw || busy) return;
    setInput("");
    push({ from: "user", text: raw });
    if (mode === "order_email") { lookupOrders(raw); return; }
    if (mode === "model") { lookupModel(raw); return; }
    // Menü modunda serbest metin — anahtar kelime eşleştirme (kurallı)
    const low = raw.toLowerCase();
    const hit = faq.find((f) => {
      const words = f.q.toLowerCase().split(/\s+/).filter((w) => w.length > 3);
      return words.some((w) => low.includes(w));
    });
    if (/sipariş|siparis|nerede|kargom/.test(low)) {
      setMode("order_email");
      push({ from: "bot", text: "Sipariş durumunuza bakayım — e-posta adresinizi yazar mısınız?" });
    } else if (/model|uyumlu|kılıf var|kilif var|telefon/.test(low)) {
      setMode("model");
      push({ from: "bot", text: "Telefon modelinizi yazın, katalogda kontrol edeyim." });
    } else if (/kargo|teslim/.test(low)) {
      push({ from: "bot", text: `${t.trust_shipping}. Takip bağlantısı kargoya verilince e-postanıza gelir.` });
    } else if (/iade|değişim|degisim/.test(low)) {
      answerReturns();
    } else if (hit) {
      push({ from: "bot", text: hit.a });
    } else {
      push({ from: "bot", text: "Bunu tam anlayamadım 🙈 Aşağıdaki konulardan seçebilir ya da WhatsApp butonundan ekibimize yazabilirsiniz." });
    }
  };

  const quickBtn = "text-left text-xs border border-zinc-200 rounded-xl px-3 py-2 hover:border-zinc-400 transition bg-white";

  return (
    <>
      {/* Karşılama baloncuğu — balonun hemen üstünde, sohbet kapalıyken */}
      {davet && !open && (
        <div className={`vitrin-yuzen-panel fixed right-4 z-40 max-w-[min(80vw,260px)] ${
          whatsappVisible ? "bottom-40" : "bottom-[5.5rem]"}`}>
          <div className="relative bg-white border border-zinc-200 rounded-2xl shadow-xl px-3.5 py-3 pr-7">
            <button onClick={davetiKapat} aria-label="Kapat"
              className="absolute top-0 right-0 p-2.5 text-zinc-400 hover:text-zinc-700
                         text-sm leading-none">×</button>
            <button onClick={() => { setOpen(true); davetiKapat(); }} className="text-left">
              <div className="text-xs font-semibold text-zinc-900">👋 Ben {asistanAdi}</div>
              <div className="text-[11px] text-zinc-600 mt-0.5 leading-snug">
                Size nasıl yardımcı olabilirim? Sipariş durumu, model uygunluğu ve kargo
                sorularınızı 7/24 yanıtlıyorum.
              </div>
            </button>
          </div>
        </div>
      )}

      {/* Balon — WhatsApp görünüyorsa üstüne biner */}
      <button
        onClick={() => { setOpen((o) => !o); davetiKapat(); }}
        aria-label={asistanAdi}
        className={`vitrin-yuzen fixed right-5 z-40 w-14 h-14 rounded-full shadow-lg flex items-center justify-center
          text-2xl text-white hover:scale-105 transition-transform ${whatsappVisible ? "bottom-24" : "bottom-5"}`}
        style={{ background: "var(--c-primary)" }}
      >
        {open ? "×" : "🎧"}
        {davet && !open && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white
            text-[11px] font-bold flex items-center justify-center animate-pulse">!</span>
        )}
      </button>

      {open && (
        <div className={`vitrin-yuzen-panel fixed right-4 z-40 w-[min(94vw,360px)] bg-white border border-zinc-200 rounded-2xl
          shadow-2xl flex flex-col overflow-hidden ${whatsappVisible ? "bottom-40" : "bottom-[5.5rem]"}`}
          style={{ maxHeight: "min(70vh, 560px)" }}>
          <div className="px-4 py-3 text-white flex items-center gap-2"
            style={{ background: "var(--c-primary)" }}>
            <span className="text-lg">🎧</span>
            <div>
              <div className="text-sm font-semibold leading-tight">{asistanAdi}</div>
              <div className="text-[11px] opacity-80">7/24 otomatik yardım</div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-zinc-50">
            {msgs.map((m, i) => {
              if ("models" in m) {
                return (
                  <div key={i} className="space-y-1.5">
                    {m.models.map((mo) => (
                      <Link key={mo.model} prefetch
                        href={`/urunler?model=${encodeURIComponent(mo.model)}`}
                        onClick={() => setOpen(false)}
                        className="block bg-white border border-zinc-200 rounded-xl px-3 py-2 text-xs hover:border-zinc-400">
                        ✅ <b>{mo.model}</b> — {mo.product_count} üründe mevcut
                      </Link>
                    ))}
                  </div>
                );
              }
              return (
                <div key={i}
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs whitespace-pre-line ${
                    m.from === "bot"
                      ? "bg-white border border-zinc-200 text-zinc-700"
                      : "ml-auto text-white"}`}
                  style={m.from === "user" ? { background: "var(--c-primary)" } : undefined}>
                  {m.text}
                </div>
              );
            })}
            {busy && <div className="text-xs text-zinc-400 px-2">yazıyor…</div>}

            {mode === "menu" && !busy && (
              <div className="grid gap-1.5 pt-1">
                <button onClick={askOrder} className={quickBtn}>📦 Siparişim nerede?</button>
                <button onClick={askModel} className={quickBtn}>📱 Telefonuma uygun kılıf var mı?</button>
                <button onClick={answerShipping} className={quickBtn}>🚚 Kargo süresi</button>
                <button onClick={answerReturns} className={quickBtn}>↩️ İade & değişim</button>
                {faq.map((f) => (
                  <button key={f.q} onClick={() => answerFaq(f)} className={quickBtn}>💬 {f.q}</button>
                ))}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="border-t border-zinc-200 p-2 flex gap-2 bg-white">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder={mode === "order_email" ? "E-posta adresiniz…"
                : mode === "model" ? "Telefon modeliniz…" : "Mesajınızı yazın…"}
              className="flex-1 text-xs border border-zinc-200 rounded-xl px-3 py-2 outline-none focus:border-zinc-400"
            />
            <button onClick={send} disabled={busy || !input.trim()}
              className="text-white text-xs rounded-xl px-3.5 disabled:opacity-40"
              style={{ background: "var(--c-primary)" }}>
              Gönder
            </button>
          </div>
        </div>
      )}
    </>
  );
}
