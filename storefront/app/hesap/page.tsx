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
  addresses?: Record<string, string>[];
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

          {/* Tasarım talepleri — müşteri kendi görselini yükleyip talep açar */}
          <DesignRequests />
        </div>

        {/* Adres defteri + bülten */}
        <div className="bg-white border border-zinc-200 rounded-2xl p-4 space-y-3">
          <AddressBook initial={me.addresses ?? (me.default_address ? [me.default_address] : [])} />

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
        </div>
      </div>
    </div>
  );
}

// Adres defteri — ilk adres varsayılandır (ödeme sayfası onu doldurur).
const ADDR_FIELDS: [string, string][] = [
  ["label", "Etiket (Ev, İş… ops.)"], ["first_name", "Ad"], ["last_name", "Soyad"],
  ["phone", "Telefon"], ["address1", "Adres"], ["city", "İl"],
  ["province", "İlçe"], ["zip", "Posta Kodu"],
];

function AddressBook({ initial }: { initial: Record<string, string>[] }) {
  const [addresses, setAddresses] = useState<Record<string, string>[]>(initial.filter(Boolean));
  const [editing, setEditing] = useState<number | null>(null); // -1 = yeni
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  // İl/ilçe dropdown verisi — yüklenemezse metin girişine düşer
  const [ilData, setIlData] = useState<Record<string, string[]> | null>(null);
  useEffect(() => {
    fetch("/api/il-ilce")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && Object.keys(d).length > 0) setIlData(d); })
      .catch(() => {});
  }, []);

  const persist = async (next: Record<string, string>[]) => {
    setBusy(true);
    try {
      const res = await fetch("/api/account?action=addresses", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ addresses: next }),
      });
      if (res.ok) {
        const data = await res.json();
        setAddresses(data.addresses ?? next);
        setEditing(null);
      }
    } finally { setBusy(false); }
  };

  const startEdit = (i: number) => {
    setEditing(i);
    setForm(i === -1 ? {} : { ...addresses[i] });
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const next = [...addresses];
    if (editing === -1) next.push(form);
    else if (editing != null) next[editing] = form;
    persist(next);
  };
  const remove = (i: number) => persist(addresses.filter((_, j) => j !== i));
  const makeDefault = (i: number) =>
    persist([addresses[i], ...addresses.filter((_, j) => j !== i)]);

  return (
    <div className="space-y-2.5">
      <div className="flex items-center">
        <div className="text-sm font-semibold">Adres Defteri</div>
        {addresses.length < 5 && editing === null && (
          <button onClick={() => startEdit(-1)}
            className="ml-auto text-xs underline text-zinc-600 hover:text-zinc-900">
            + Yeni Adres
          </button>
        )}
      </div>
      <p className="text-[11px] text-zinc-400 -mt-1.5">
        İlk adres varsayılandır — ödeme sayfasında otomatik doldurulur.
      </p>

      {addresses.length === 0 && editing === null && (
        <p className="text-xs text-zinc-400">Henüz kayıtlı adres yok.</p>
      )}

      {addresses.map((a, i) => (
        <div key={i} className={`rounded-xl border p-2.5 text-xs ${
          i === 0 ? "border-emerald-300 bg-emerald-50/40" : "border-zinc-200"}`}>
          <div className="flex items-center gap-1.5">
            <span className="font-medium">
              {a.label || `${a.first_name || ""} ${a.last_name || ""}`.trim() || "Adres"}
            </span>
            {i === 0 && (
              <span className="text-[10px] text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded-full">
                Varsayılan
              </span>
            )}
            <span className="ml-auto flex gap-1.5">
              {i !== 0 && (
                <button onClick={() => makeDefault(i)} disabled={busy}
                  className="text-zinc-500 hover:text-zinc-900 underline">Varsayılan yap</button>
              )}
              <button onClick={() => startEdit(i)} className="text-zinc-500 hover:text-zinc-900 underline">
                Düzenle
              </button>
              <button onClick={() => remove(i)} disabled={busy}
                className="text-red-400 hover:text-red-600 underline">Sil</button>
            </span>
          </div>
          <div className="mt-1 text-zinc-500 leading-relaxed">
            {a.address1}<br />
            {[a.province, a.city, a.zip].filter(Boolean).join(" / ")}
            {a.phone && <> · {a.phone}</>}
          </div>
        </div>
      ))}

      {editing !== null && (
        <form onSubmit={submit} className="rounded-xl border border-zinc-300 p-3 space-y-2">
          <div className="text-xs font-medium">{editing === -1 ? "Yeni Adres" : "Adresi Düzenle"}</div>
          <div className="grid grid-cols-2 gap-2">
            {ADDR_FIELDS.map(([k, ph]) => {
              // İl/ilçe: liste yüklendiyse dropdown (elle yazım hatası biter)
              if (ilData && (k === "city" || k === "province")) {
                const iller = Object.keys(ilData);
                const ilKey = iller.find((x) =>
                  x.toLocaleLowerCase("tr") === (form.city || "").toLocaleLowerCase("tr")) || "";
                const opts = k === "city" ? iller : (ilKey ? ilData[ilKey] : []);
                return (
                  <select key={k} value={form[k] || ""} required={k === "city"}
                    disabled={k === "province" && !ilKey}
                    onChange={(e) => setForm((f) => ({
                      ...f, [k]: e.target.value,
                      ...(k === "city" ? { province: "" } : {}),
                    }))}
                    className="rounded-lg border border-zinc-300 px-2.5 py-2 text-sm bg-white disabled:opacity-50">
                    <option value="">{k === "city" ? "İl seçin…" : ilKey ? "İlçe seçin…" : "Önce il seçin"}</option>
                    {opts.map((x) => <option key={x} value={x}>{x}</option>)}
                  </select>
                );
              }
              return (
                <input key={k} value={form[k] || ""} placeholder={ph}
                  required={k === "address1" || k === "city"}
                  onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))}
                  className={`rounded-lg border border-zinc-300 px-2.5 py-2 text-sm ${
                    k === "address1" ? "col-span-2" : ""}`} />
              );
            })}
          </div>
          <div className="flex gap-2">
            <button disabled={busy}
              className="flex-1 rounded-lg text-white text-sm font-medium py-2 disabled:opacity-50 hover:opacity-90 transition"
              style={{ background: "var(--c-primary)" }}>
              {busy ? "Kaydediliyor…" : "Kaydet"}
            </button>
            <button type="button" onClick={() => setEditing(null)}
              className="rounded-lg border border-zinc-300 px-3 text-sm">Vazgeç</button>
          </div>
        </form>
      )}
    </div>
  );
}

// ── 🎨 Tasarım Taleplerim — görsel yükle + açıklama; mağaza inceleyip yanıtlar ──
interface DesignReq {
  id: string;
  image_url: string;
  message: string | null;
  phone_model: string | null;
  status: string;
  status_label: string;
  admin_note: string | null;
  created_at: string | null;
}

const REQ_STATUS_COLOR: Record<string, string> = {
  acik: "bg-amber-50 text-amber-700",
  incelendi: "bg-sky-50 text-sky-700",
  teklif: "bg-indigo-50 text-indigo-700",
  tamam: "bg-emerald-50 text-emerald-700",
  red: "bg-red-50 text-red-600",
};

function DesignRequests() {
  const [reqs, setReqs] = useState<DesignReq[]>([]);
  const [open, setOpen] = useState(false);
  const [image, setImage] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [phoneModel, setPhoneModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetch("/api/account?action=design-requests")
      .then((r) => (r.ok ? r.json() : { requests: [] }))
      .then((d) => setReqs(d.requests || []))
      .catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const upload = async (file: File) => {
    setBusy(true); setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Görsel yüklenemedi");
      setImage(data.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yükleme hatası");
    } finally {
      setBusy(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!image) { setError("Önce tasarımınızı yükleyin"); return; }
    setBusy(true); setError("");
    try {
      const res = await fetch("/api/account?action=design-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_url: image,
          message: message.trim() || null,
          phone_model: phoneModel.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Talep gönderilemedi");
      setImage(null); setMessage(""); setPhoneModel(""); setOpen(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Beklenmeyen hata");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-t border-zinc-100 px-4 py-3">
      <div className="flex items-center">
        <div className="text-sm font-semibold">🎨 Tasarım Taleplerim{reqs.length > 0 ? ` (${reqs.length})` : ""}</div>
        <button onClick={() => setOpen(!open)}
          className="ml-auto text-xs underline text-zinc-600 hover:text-zinc-900">
          {open ? "Vazgeç" : "+ Yeni Talep"}
        </button>
      </div>
      <p className="text-[11px] text-zinc-400 mt-0.5">
        Kendi tasarımınızı yükleyin — inceleyip size özel kılıf teklifi hazırlayalım.
      </p>

      {open && (
        <form onSubmit={submit} className="mt-3 space-y-2 rounded-xl border border-zinc-200 p-3">
          {image ? (
            <div className="flex items-center gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={image} alt="Tasarım" className="h-20 w-20 object-cover rounded-lg border border-zinc-200" />
              <button type="button" onClick={() => setImage(null)}
                className="text-xs text-red-500 underline">Kaldır</button>
            </div>
          ) : (
            <label className="flex items-center justify-center rounded-xl border border-dashed border-zinc-300 px-4 py-6 text-sm text-zinc-500 cursor-pointer hover:border-zinc-500">
              {busy ? "Yükleniyor…" : "📷 Tasarımınızı yükleyin"}
              <input type="file" accept="image/*" className="hidden" disabled={busy}
                onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            </label>
          )}
          <input value={phoneModel} onChange={(e) => setPhoneModel(e.target.value)}
            placeholder="Telefon modeliniz (örn. iPhone 15 Pro)" maxLength={120}
            className="w-full rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
          <textarea value={message} onChange={(e) => setMessage(e.target.value)}
            placeholder="Nasıl bir kılıf hayal ediyorsunuz? (isteğe bağlı)" rows={2} maxLength={2000}
            className="w-full rounded-lg border border-zinc-300 px-2.5 py-2 text-sm" />
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button disabled={busy || !image}
            className="w-full rounded-xl text-white text-sm font-medium py-2.5 disabled:opacity-50 hover:opacity-90 transition"
            style={{ background: "var(--c-primary)" }}>
            {busy ? "Gönderiliyor…" : "Talebi Gönder"}
          </button>
        </form>
      )}

      {reqs.length > 0 && (
        <div className="mt-3 space-y-2">
          {reqs.map((r) => (
            <div key={r.id} className="flex gap-2.5 rounded-xl border border-zinc-200 p-2.5 text-xs">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={r.image_url} alt="" className="h-12 w-12 object-cover rounded-lg border border-zinc-100 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${
                    REQ_STATUS_COLOR[r.status] || "bg-zinc-100 text-zinc-600"}`}>
                    {r.status_label}
                  </span>
                  {r.phone_model && <span className="text-zinc-400 truncate">{r.phone_model}</span>}
                  {r.created_at && (
                    <span className="ml-auto text-zinc-400 whitespace-nowrap">
                      {new Date(r.created_at).toLocaleDateString("tr-TR")}
                    </span>
                  )}
                </div>
                {r.message && <p className="mt-1 text-zinc-500 line-clamp-1">{r.message}</p>}
                {r.admin_note && (
                  <p className="mt-1 text-emerald-700 bg-emerald-50 rounded-lg px-2 py-1">
                    💬 {r.admin_note}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
