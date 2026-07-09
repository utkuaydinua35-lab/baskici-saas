"use client";

// Footer bülten kayıt formu — KVKK açık rızalı e-posta aboneliği.
import { useState } from "react";
import Link from "next/link";

export default function NewsletterForm() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setState("busy");
    try {
      const res = await fetch("/api/newsletter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), kvkk_accept: true }),
      });
      setState(res.ok ? "done" : "error");
    } catch {
      setState("error");
    }
  };

  if (state === "done") {
    return (
      <p className="text-sm text-emerald-600">
        🎉 Aboneliğiniz alındı — kampanyalardan ilk siz haberdar olacaksınız.
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex gap-2">
        <input
          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="E-posta adresiniz"
          className="flex-1 min-w-0 rounded-xl border border-zinc-300 px-3 py-2 text-sm bg-white"
        />
        <button
          disabled={state === "busy"}
          className="rounded-xl text-white text-sm font-medium px-4 py-2 disabled:opacity-50 hover:opacity-90 transition whitespace-nowrap"
          style={{ background: "var(--c-primary)" }}
        >
          {state === "busy" ? "…" : "Abone Ol"}
        </button>
      </div>
      <p className="text-[11px] text-zinc-400">
        Abone olarak kampanya e-postaları için{" "}
        <Link href="/gizlilik" className="underline">açık rıza</Link> vermiş olursunuz.
        İstediğiniz an ayrılabilirsiniz.
      </p>
      {state === "error" && (
        <p className="text-xs text-red-600">Kayıt alınamadı — lütfen tekrar deneyin.</p>
      )}
    </form>
  );
}
