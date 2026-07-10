"use client";

// Hesabım — şifresiz giriş (e-postaya kod) + sipariş geçmişi + kayıtlı adres.
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { formatPrice } from "@/lib/format";

interface Me {
  email: string;
  name: string | null;
  phone: string | null;
  orders_count: number;
  default_address: Record<string, string> | null;
  accepts_marketing?: boolean;
}
interface AccountOrder {
  order_number: string;
  name: string | null;
  created_at: string | null;
  total_price: string | null;
  durum: string;
  lookup_token: string | null;
}

export default function AccountPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/account");
      setMe(res.ok ? await res.json() : null);
    } catch {
      setMe(null);
    } finally {
      setChecked(true);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (!checked) {
    return <div className="mx-auto max-w-xl px-4 py-20 text-center text-sm text-zinc-400">Yükleniyor…</div>;
  }
  return me ? <AccountView me={me} onLogout={() => setMe(null)} /> : <LoginView onSuccess={load} />;
}

// ── Giriş: e-posta → kod ──
function LoginView({ onSuccess }: { onSuccess: () => void }) {
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const requestCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const res = await fetch("/api/account?action=login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (!res.ok) throw new Error((await res.json())?.detail || "Kod gönderilemedi");
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Beklenmeyen hata");
    } finally { setBusy(false); }
  };

  const verify = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const res = await fetch("/api/account?action=verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), code: code.trim() }),
      });
      if (!res.ok) throw new Error((await res.json())?.detail || "Kod doğrulanamadı");
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Beklenmeyen hata");
    } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="text-xl font-semibold text-center">Hesabım</h1>
      <p className="mt-1.5 text-sm text-zinc-500 text-center">
        Şifre yok — e-postanıza tek kullanımlık kod göndeririz.
      </p>
      {step === "email" ? (
        <form onSubmit={requestCode} className="mt-6 space-y-3">
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="E-posta adresiniz" autoComplete="email"
            className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white" />
          <button disabled={busy}
            className="w-full rounded-xl text-white font-medium py-3 disabled:opacity-50 hover:opacity-90 transition"
            style={{ background: "var(--c-primary)" }}>
            {busy ? "Gönderiliyor…" : "Giriş Kodu Gönder"}
          </button>
        </form>
      ) : (
        <form onSubmit={verify} className="mt-6 space-y-3">
          <p className="text-xs text-zinc-500 text-center">
            <b>{email}</b> adresine gönderilen 6 haneli kodu girin.
          </p>
          <input inputMode="numeric" pattern="[0-9]*" required minLength={6} maxLength={6}
            value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            placeholder="······" autoFocus
            className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-center text-2xl tracking-[0.5em] font-mono bg-white" />
          <button disabled={busy || code.length !== 6}
            className="w-full rounded-xl text-white font-medium py-3 disabled:opacity-50 hover:opacity-90 transition"
            style={{ background: "var(--c-primary)" }}>
            {busy ? "Doğrulanıyor…" : "Giriş Yap"}
          </button>
          <button type="button" onClick={() => { setStep("email"); setCode(""); setError(""); }}
            className="w-full text-xs text-zinc-500 hover:underline">
            Farklı e-posta kullan / kodu yeniden iste
          </button>
        </form>
      )}
      {error && <p className="mt-3 text-xs text-red-600 text-center">{error}</p>}
    </div>
  );
}

// ── Hesap görünümü: siparişler + adres ──
function AccountView({ me, onLogout }: { me: Me; onLogout: () => void }) {
  const [orders, setOrders] = useState<AccountOrder[]>([]);
  const [addr, setAddr] = useState<Record<string, string>>(me.default_address || {});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [marketing, setMarketing] = useState(!!me.accepts_marketing);

  const toggleMarketing = async (next: boolean) => {
    setMarketing(next); // iyimser güncelle
    const res = await fetch("/api/account?action=marketing", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subscribed: next }),
    }).catch(() => null);
    if (!res?.ok) setMarketing(!next);
  };

  useEffect(() => {
    fetch("/api/account/orders")
      .then((r) => (r.ok ? r.json() : { orders: [] }))
      .then((d) => setOrders(d.orders || []))
      .catch(() => {});
  }, []);

  const logout = async () => {
    await fetch("/api/account?action=logout", { method: "POST" });
    onLogout();
  };

  const saveAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setSaved(false);
    try {
      const res = await fetch("/api/account", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(addr),
      });
      if (res.ok) { setSaved(true); setTimeout(() => setSaved(false), 2500); }
    } finally { setSaving(false); }
  };

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setAddr((a) => ({ ...a, [k]: e.target.value }));

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Hesabım</h1>
          <p className="text-xs text-zinc-500">{me.email}</p>
        </div>
        <button onClick={logout} className="text-xs text-zinc-500 hover:text-red-600 underline">
          Çıkış yap
        </button>
      </div>

      <div className="mt-6 grid md:grid-cols-[1fr_280px] gap-6 items-start">
        {/* Siparişler */}
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden">
          <div className="px-4 py-3 border-b border-zinc-200 text-sm font-semibold">
            Siparişlerim ({orders.length})
          </div>
          {orders.length === 0 ? (
            <div className="p-6 text-center text-sm text-zinc-400">
              Henüz siparişiniz yok.{" "}
              <Link href="/urunler" className="underline">Alışverişe başlayın</Link>
            </div>
          ) : (
            <div className="divide-y divide-zinc-100">
              {orders.map((o, i) => (
                <div key={i} className="px-4 py-3 flex items-center gap-3 text-sm">
                  <div className="flex-1 min-w-0">
                    <div className="font-mono font-medium">{o.name || `#${o.order_number}`}</div>
                    <div className="text-xs text-zinc-500">
                      {o.created_at && new Date(o.created_at).toLocaleDateString("tr-TR")}
                      {" · "}{o.durum}
                    </div>
                  </div>
                  {o.total_price && (
                    <div className="font-medium whitespace-nowrap">{formatPrice(o.total_price)}</div>
                  )}
                  {o.lookup_token && (
                    <div className="flex gap-1.5">
                      <Link href={`/siparis/${o.lookup_token}`}
                        className="text-xs px-2.5 py-1.5 rounded-lg border border-zinc-300 hover:border-zinc-500 whitespace-nowrap">
                        Takip Et
                      </Link>
                      <Link href={`/sepet?restore=${o.lookup_token}`}
                        className="text-xs px-2.5 py-1.5 rounded-lg text-white whitespace-nowrap hover:opacity-90"
                        style={{ background: "var(--c-primary)" }}
                        title="Aynı ürünleri sepete ekle">
                        Tekrar Al
                      </Link>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Kayıtlı adres */}
        <form onSubmit={saveAddress} className="bg-white border border-zinc-200 rounded-2xl p-4 space-y-2.5">
          <div className="text-sm font-semibold">Kayıtlı Adres</div>
          <p className="text-[11px] text-zinc-400 -mt-1">Ödeme sayfasında otomatik doldurulur.</p>
          <div className="grid grid-cols-2 gap-2">
            <input value={addr.first_name || ""} onChange={set("first_name")} placeholder="Ad"
              className="rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
            <input value={addr.last_name || ""} onChange={set("last_name")} placeholder="Soyad"
              className="rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
          </div>
          <input value={addr.phone || ""} onChange={set("phone")} placeholder="Telefon"
            className="w-full rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
          <input value={addr.address1 || ""} onChange={set("address1")} placeholder="Adres"
            className="w-full rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
          <div className="grid grid-cols-3 gap-2">
            <input value={addr.city || ""} onChange={set("city")} placeholder="İl"
              className="rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
            <input value={addr.province || ""} onChange={set("province")} placeholder="İlçe"
              className="rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
            <input value={addr.zip || ""} onChange={set("zip")} placeholder="P. Kodu"
              className="rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
          </div>
          <button disabled={saving}
            className="w-full rounded-xl text-white text-sm font-medium py-2.5 disabled:opacity-50 hover:opacity-90 transition"
            style={{ background: "var(--c-primary)" }}>
            {saving ? "Kaydediliyor…" : saved ? "Kaydedildi ✓" : "Adresi Kaydet"}
          </button>

          <label className="flex items-start gap-2 text-xs text-zinc-600 pt-2 border-t border-zinc-100">
            <input type="checkbox" checked={marketing} className="mt-0.5"
              onChange={(e) => toggleMarketing(e.target.checked)} />
            <span>
              Kampanya ve indirim e-postaları almak istiyorum.
              <span className="block text-[10px] text-zinc-400 mt-0.5">
                Onayınızı dilediğiniz an bu kutudan geri çekebilirsiniz (KVKK).
              </span>
            </span>
          </label>
        </form>
      </div>
    </div>
  );
}
