"use client";

// Sipariş takip sayfası: iade/değişim/sorun talebi — Shopify self-servis iade hissi.
import { useState } from "react";

const TYPES = [
  ["iade", "İade talebi"],
  ["degisim", "Değişim talebi"],
  ["sorun", "Sorun bildir"],
] as const;

export default function OrderRequestForm({ token }: { token: string }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<string>("iade");
  const [message, setMessage] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setState("busy"); setError("");
    try {
      const res = await fetch("/api/order-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, request_type: type, message: message.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Gönderilemedi");
      setState("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Beklenmeyen hata");
      setState("error");
    }
  };

  if (state === "done") {
    return (
      <div className="mt-4 bg-emerald-50 border border-emerald-200 rounded-2xl p-4 text-sm text-emerald-700">
        ✓ Talebiniz alındı — sipariş e-postanız üzerinden dönüş yapacağız.
      </div>
    );
  }

  return (
    <div className="mt-4 bg-white border border-zinc-200 rounded-2xl p-5">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-sm font-semibold"
      >
        İade / Değişim / Sorun Bildir
        <span className="text-zinc-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <form onSubmit={submit} className="mt-3 space-y-3">
          <div className="flex gap-2 flex-wrap">
            {TYPES.map(([key, label]) => (
              <button
                key={key} type="button" onClick={() => setType(key)}
                className={`px-3 py-1.5 rounded-full border text-xs transition ${
                  type === key
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-300 hover:border-zinc-500"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <textarea
            required minLength={10} maxLength={2000} rows={3}
            value={message} onChange={(e) => setMessage(e.target.value)}
            placeholder={type === "sorun"
              ? "Yaşadığınız sorunu kısaca anlatın…"
              : "Hangi ürünü, neden iade/değişim etmek istiyorsunuz?"}
            className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-sm bg-white"
          />
          <p className="text-[11px] text-zinc-400">
            İade ve değişim koşulları için “İade ve Değişim” sayfasına göz atın.
          </p>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            disabled={state === "busy" || message.trim().length < 10}
            className="rounded-xl text-white text-sm font-medium px-4 py-2.5 disabled:opacity-50 hover:opacity-90 transition"
            style={{ background: "var(--c-primary)" }}
          >
            {state === "busy" ? "Gönderiliyor…" : "Talebi Gönder"}
          </button>
        </form>
      )}
    </div>
  );
}
