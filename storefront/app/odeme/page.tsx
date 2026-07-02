"use client";

// Misafir checkout — form + KVKK onayı → backend ödeme oturumu → redirect/iframe.
import { useState } from "react";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";

interface CheckoutResponse {
  token: string;
  mode: "redirect" | "iframe";
  url: string;
  amount: string;
  shipping_amount: string;
}

export default function CheckoutPage() {
  const { items, subtotal } = useCart();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [iframeUrl, setIframeUrl] = useState<string | null>(null);
  const [checkoutToken, setCheckoutToken] = useState<string | null>(null);

  if (items.length === 0 && !iframeUrl) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <h1 className="text-xl font-semibold">Sepetiniz boş</h1>
        <Link href="/urunler" className="mt-4 inline-block text-sm underline">
          Alışverişe dön
        </Link>
      </div>
    );
  }

  // PayTR iframe modu: ödeme çerçevede açılır, sonuç sayfası poll'la takip edilir
  if (iframeUrl && checkoutToken) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <h1 className="text-xl font-semibold mb-4">Güvenli Ödeme</h1>
        <iframe
          src={iframeUrl}
          className="w-full min-h-[600px] rounded-2xl border border-zinc-200 bg-white"
          title="Ödeme"
        />
        <p className="mt-3 text-xs text-zinc-500">
          Ödemeniz tamamlandığında{" "}
          <Link href={`/odeme/sonuc?token=${checkoutToken}`} className="underline">
            sipariş durumu sayfasından
          </Link>{" "}
          kontrol edebilirsiniz.
        </p>
      </div>
    );
  }

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: items.map((i) => ({ variant_id: i.variantId, quantity: i.quantity })),
          customer: {
            first_name: fd.get("first_name"),
            last_name: fd.get("last_name"),
            email: fd.get("email"),
            phone: fd.get("phone"),
            address1: fd.get("address1"),
            city: fd.get("city"),
            province: fd.get("province") || null,
            zip: fd.get("zip") || null,
            note: fd.get("note") || null,
          },
          kvkk_accept: fd.get("kvkk_accept") === "on",
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : "Ödeme başlatılamadı";
        throw new Error(detail);
      }
      const out = data as CheckoutResponse;
      if (out.mode === "redirect") {
        window.location.href = out.url; // iyzico barındırmalı ödeme sayfası
      } else {
        setIframeUrl(out.url);
        setCheckoutToken(out.token);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Beklenmeyen bir hata oluştu");
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-xl font-semibold mb-5">Teslimat ve Ödeme</h1>
      <form onSubmit={submit} className="grid md:grid-cols-[1fr_260px] gap-6 items-start">
        <div className="space-y-4 bg-white border border-zinc-200 rounded-2xl p-5">
          <div className="grid grid-cols-2 gap-3">
            <Input name="first_name" label="Ad" required autoComplete="given-name" />
            <Input name="last_name" label="Soyad" required autoComplete="family-name" />
          </div>
          <Input name="email" label="E-posta" type="email" required autoComplete="email" />
          <Input name="phone" label="Telefon" type="tel" required autoComplete="tel"
            placeholder="05xx xxx xx xx" />
          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="address1">Adres</label>
            <textarea
              id="address1" name="address1" required minLength={5} maxLength={300} rows={2}
              autoComplete="street-address"
              className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-sm bg-white"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Input name="city" label="İl" required autoComplete="address-level1" />
            <Input name="province" label="İlçe" autoComplete="address-level2" />
            <Input name="zip" label="Posta Kodu" autoComplete="postal-code" />
          </div>
          <Input name="note" label="Sipariş notu (isteğe bağlı)" />
          <label className="flex items-start gap-2 text-xs text-zinc-600 pt-1">
            <input type="checkbox" name="kvkk_accept" required className="mt-0.5" />
            <span>
              <Link href="/gizlilik" className="underline" target="_blank">
                KVKK aydınlatma metnini
              </Link>{" "}
              ve{" "}
              <Link href="/mesafeli-satis" className="underline" target="_blank">
                mesafeli satış sözleşmesini
              </Link>{" "}
              okudum, kabul ediyorum.
            </span>
          </label>
        </div>

        <aside className="bg-white border border-zinc-200 rounded-2xl p-5 space-y-3 md:sticky md:top-20">
          <h2 className="text-sm font-semibold">Sipariş Özeti</h2>
          <ul className="text-xs text-zinc-600 space-y-1.5">
            {items.map((i) => (
              <li key={i.variantId} className="flex justify-between gap-2">
                <span className="line-clamp-1">
                  {i.title} ({i.modelDisplay}{i.variation ? `, ${i.variation}` : ""}) ×{i.quantity}
                </span>
                <span className="whitespace-nowrap">{formatPrice(Number(i.price) * i.quantity)}</span>
              </li>
            ))}
          </ul>
          <div className="border-t border-zinc-200 pt-2 flex justify-between text-sm">
            <span>Ara toplam</span>
            <span className="font-semibold">{formatPrice(subtotal)}</span>
          </div>
          <p className="text-[11px] text-zinc-400">
            Kargo dahil kesin tutar, güvenli ödeme sayfasında gösterilir.
          </p>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            disabled={busy}
            className="w-full rounded-xl bg-zinc-900 text-white font-medium py-3 disabled:opacity-50 hover:bg-zinc-700 transition"
          >
            {busy ? "Yönlendiriliyor…" : "Güvenli Ödemeye Geç"}
          </button>
          <p className="text-[11px] text-zinc-400 text-center">
            🔒 Kart bilgileriniz bize değil, yalnızca ödeme kuruluşuna iletilir.
          </p>
        </aside>
      </form>
    </div>
  );
}

function Input({
  label,
  name,
  ...rest
}: { label: string; name: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1" htmlFor={name}>
        {label}
      </label>
      <input
        id={name}
        name={name}
        {...rest}
        className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-sm bg-white"
      />
    </div>
  );
}
