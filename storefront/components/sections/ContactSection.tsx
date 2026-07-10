"use client";

// İletişim formu bölümü (ShinePro contact-form) — mağaza e-postasına iletir.
import { useState } from "react";

export default function ContactSection({
  title,
  subtitle,
}: {
  title?: string;
  subtitle?: string;
}) {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setState("busy"); setError("");
    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Gönderilemedi");
      setState("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Beklenmeyen hata");
      setState("error");
    }
  };

  return (
    <section className="mx-auto max-w-xl px-4 py-8">
      <h2 className="text-lg font-semibold text-center">{title || "İletişim"}</h2>
      {subtitle && <p className="mt-1 text-sm text-zinc-500 text-center">{subtitle}</p>}

      {state === "done" ? (
        <div className="mt-6 bg-emerald-50 border border-emerald-200 rounded-2xl p-5 text-center text-sm text-emerald-700">
          ✓ Mesajınız iletildi — en kısa sürede dönüş yapacağız.
        </div>
      ) : (
        <form onSubmit={submit} className="mt-6 bg-white border border-zinc-200 rounded-2xl p-5 space-y-3">
          <div className="grid sm:grid-cols-2 gap-3">
            <input required minLength={2} maxLength={120} value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Adınız"
              className="rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white" />
            <input type="email" required value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              placeholder="E-posta adresiniz"
              className="rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white" />
          </div>
          <textarea required minLength={10} maxLength={3000} rows={4} value={form.message}
            onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
            placeholder="Mesajınız…"
            className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white" />
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button disabled={state === "busy"}
            className="w-full rounded-xl text-white font-medium py-3 disabled:opacity-50 hover:opacity-90 transition"
            style={{ background: "var(--c-primary)" }}>
            {state === "busy" ? "Gönderiliyor…" : "Mesaj Gönder"}
          </button>
        </form>
      )}
    </section>
  );
}
