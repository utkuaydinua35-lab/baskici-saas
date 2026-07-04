"use client";

// Sipariş sayfasından yorum bırakma — doğrulanmış alıcı (lookup_token).
import { useState } from "react";

export default function ReviewForm({
  lookupToken,
  productSlug,
  productTitle,
}: {
  lookupToken: string;
  productSlug: string;
  productTitle: string;
}) {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [name, setName] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rating) { setError("Lütfen yıldız seçin"); return; }
    setBusy(true); setError("");
    try {
      const res = await fetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lookup_token: lookupToken,
          product_slug: productSlug,
          rating,
          author_name: name.trim(),
          comment: comment.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Gönderilemedi");
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Beklenmeyen hata");
    } finally { setBusy(false); }
  };

  if (done) {
    return (
      <p className="text-xs text-emerald-700 mt-1">
        ✓ Yorumunuz alındı — onaylandıktan sonra yayınlanır. Teşekkürler!
      </p>
    );
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)}
        className="text-xs underline text-zinc-500 hover:text-zinc-800 mt-1">
        ⭐ Bu ürünü değerlendir
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="mt-2 p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-2">
      <div className="text-xs font-medium">{productTitle} için değerlendirmeniz</div>
      <div className="flex gap-1 text-2xl">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button"
            onClick={() => setRating(n)}
            onMouseEnter={() => setHover(n)}
            onMouseLeave={() => setHover(0)}
            className={(hover || rating) >= n ? "text-amber-400" : "text-zinc-300"}
            aria-label={`${n} yıldız`}>
            ★
          </button>
        ))}
      </div>
      <input value={name} onChange={(e) => setName(e.target.value)} required
        minLength={2} maxLength={60} placeholder="Adınız (vitrinde kısaltılır)"
        className="w-full rounded-lg border border-zinc-300 px-2.5 py-1.5 text-sm bg-white" />
      <textarea value={comment} onChange={(e) => setComment(e.target.value)}
        maxLength={2000} rows={3} placeholder="Deneyiminizi paylaşın (isteğe bağlı)"
        className="w-full rounded-lg border border-zinc-300 px-2.5 py-1.5 text-sm bg-white" />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button disabled={busy}
          className="px-4 py-1.5 rounded-lg text-white text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--c-primary)" }}>
          {busy ? "Gönderiliyor…" : "Gönder"}
        </button>
        <button type="button" onClick={() => setOpen(false)}
          className="px-3 py-1.5 text-sm text-zinc-500">Vazgeç</button>
      </div>
    </form>
  );
}
