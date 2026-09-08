"use client";

// Ürün soru-cevap — müşteri soru sorar (satın alma şartı yok), mağaza
// yanıtlayınca soru+yanıt burada yayınlanır. Yanıtsız sorular görünmez.
import { useEffect, useState } from "react";

interface QA {
  author: string;
  question: string;
  answer: string;
  answered_at: string | null;
}

export default function ProductQuestions({ productSlug }: { productSlug: string }) {
  const [items, setItems] = useState<QA[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`/api/questions?slug=${encodeURIComponent(productSlug)}`)
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setItems(d.items || []))
      .catch(() => {});
  }, [productSlug]);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true); setErr("");
    try {
      const res = await fetch("/api/questions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_slug: productSlug,
          author_name: fd.get("author_name"),
          question: fd.get("question"),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Gönderilemedi");
      setSent(data.message || "Sorunuz iletildi");
      setOpen(false);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Gönderilemedi");
    } finally { setBusy(false); }
  };

  return (
    <section className="mt-10 border-t border-zinc-200 pt-6">
      <div className="flex items-center gap-3">
        <h2 className="text-base font-semibold">Sorular ve Cevaplar</h2>
        {!open && (
          <button onClick={() => setOpen(true)}
            className="ml-auto text-sm underline hover:no-underline py-2 -my-2 px-1">
            Soru sor
          </button>
        )}
      </div>

      {sent && <p className="mt-3 text-sm text-emerald-700">✓ {sent}</p>}

      {open && (
        <form onSubmit={submit} className="mt-4 space-y-2 max-w-lg">
          <input name="author_name" required minLength={2} maxLength={60}
            placeholder="Adınız"
            className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-sm" />
          <textarea name="question" required minLength={5} maxLength={1000} rows={3}
            placeholder="Ürünle ilgili sorunuz…"
            className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-sm" />
          {err && <p className="text-xs text-red-600">{err}</p>}
          <div className="flex gap-2">
            <button disabled={busy}
              className="rounded-xl text-white px-4 py-2 text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--c-primary)" }}>
              {busy ? "Gönderiliyor…" : "Gönder"}
            </button>
            <button type="button" onClick={() => setOpen(false)}
              className="text-sm text-zinc-500">Vazgeç</button>
          </div>
          <p className="text-[11px] text-zinc-400">
            Sorunuz yanıtlandıktan sonra bu sayfada yayınlanır.
          </p>
        </form>
      )}

      {items.length === 0 ? (
        !open && <p className="mt-3 text-sm text-zinc-500">
          Henüz soru yok — merak ettiğiniz bir şey varsa ilk soran siz olun.
        </p>
      ) : (
        <div className="mt-4 space-y-4">
          {items.map((q, i) => (
            <div key={i} className="text-sm">
              <div className="font-medium">
                <span className="text-zinc-400 mr-1.5">S:</span>{q.question}
                <span className="ml-2 text-xs font-normal text-zinc-400">— {q.author}</span>
              </div>
              <div className="mt-1 text-zinc-600 pl-5">
                <span className="text-zinc-400 mr-1.5 -ml-5">C:</span>{q.answer}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
