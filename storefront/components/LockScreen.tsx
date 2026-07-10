"use client";

// Yayın öncesi kilit ekranı (Shopify password page) — doğru şifrede çerez
// yazılır ve sayfa yenilenir.
import { useState } from "react";

export default function LockScreen({ storeName }: { storeName: string }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const res = await fetch("/api/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data?.detail === "string" ? data.detail : "Şifre hatalı");
      }
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Beklenmeyen hata");
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4"
      style={{ background: "var(--c-bg)" }}>
      <div className="w-full max-w-sm text-center">
        <div className="text-5xl mb-4">🔒</div>
        <h1 className="text-2xl font-bold">{storeName}</h1>
        <p className="mt-2 text-sm text-zinc-500">
          Mağazamız çok yakında açılıyor. Şifreniz varsa giriş yapabilirsiniz.
        </p>
        <form onSubmit={submit} className="mt-6 space-y-3">
          <input
            type="password" required value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Mağaza şifresi"
            className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white text-center"
          />
          <button
            disabled={busy}
            className="w-full rounded-xl text-white font-medium py-3 disabled:opacity-50 hover:opacity-90 transition"
            style={{ background: "var(--c-primary)" }}
          >
            {busy ? "Kontrol ediliyor…" : "Giriş"}
          </button>
        </form>
        {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}
