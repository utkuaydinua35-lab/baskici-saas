"use client";

// Misafir checkout — form + KVKK onayı → backend ödeme oturumu → redirect/iframe.
import { useEffect, useState } from "react";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import CouponInput from "@/components/CouponInput";
import { trackInitiateCheckout } from "@/lib/track";
import TrustBadges from "@/components/TrustBadges";

interface CheckoutResponse {
  token: string;
  mode: "redirect" | "iframe";
  url: string;
  amount: string;
  shipping_amount: string;
}

export default function CheckoutPage() {
  const { items, subtotal, coupon, setCoupon } = useCart();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [iframeUrl, setIframeUrl] = useState<string | null>(null);
  const [checkoutToken, setCheckoutToken] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<Record<string, string>>({});
  const [corporate, setCorporate] = useState(false);

  // Girişli müşteri: kayıtlı bilgilerle formu doldur
  useEffect(() => {
    fetch("/api/account")
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => {
        if (!me) return;
        const a = me.default_address || {};
        setPrefill({
          first_name: a.first_name || (me.name || "").split(" ")[0] || "",
          last_name: a.last_name || (me.name || "").split(" ").slice(1).join(" ") || "",
          email: me.email || "",
          phone: a.phone || me.phone || "",
          address1: a.address1 || "",
          city: a.city || "",
          province: a.province || "",
          zip: a.zip || "",
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (items.length === 0) return;
    trackInitiateCheckout({
      value: subtotal,
      items: items.map((i) => ({
        id: i.variantId, name: i.title, price: Number(i.price), quantity: i.quantity,
      })),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
            invoice_company: fd.get("invoice_company") || null,
            invoice_tax_office: fd.get("invoice_tax_office") || null,
            invoice_tax_no: fd.get("invoice_tax_no") || null,
          },
          kvkk_accept: fd.get("kvkk_accept") === "on",
          discount_code: coupon?.code || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : "Ödeme başlatılamadı";
        // Kupon artık geçersizse (limit doldu vb.) otomatik kaldır — müşteri tekrar denesin
        if (coupon && /kupon/i.test(detail)) setCoupon(null);
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
      <form key={prefill.email || "misafir"} onSubmit={submit} className="grid md:grid-cols-[1fr_260px] gap-6 items-start">
        <div className="space-y-4 bg-white border border-zinc-200 rounded-2xl p-5">
          <div className="grid grid-cols-2 gap-3">
            <Input name="first_name" label="Ad" required autoComplete="given-name" defaultValue={prefill.first_name} />
            <Input name="last_name" label="Soyad" required autoComplete="family-name" defaultValue={prefill.last_name} />
          </div>
          <Input name="email" label="E-posta" type="email" required autoComplete="email" defaultValue={prefill.email} />
          <Input name="phone" label="Telefon" type="tel" required autoComplete="tel"
            placeholder="05xx xxx xx xx" defaultValue={prefill.phone} />
          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="address1">Adres</label>
            <textarea
              id="address1" name="address1" required minLength={5} maxLength={300} rows={2}
              autoComplete="street-address" defaultValue={prefill.address1}
              className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-sm bg-white"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Input name="city" label="İl" required autoComplete="address-level1" defaultValue={prefill.city} />
            <Input name="province" label="İlçe" autoComplete="address-level2" defaultValue={prefill.province} />
            <Input name="zip" label="Posta Kodu" autoComplete="postal-code" defaultValue={prefill.zip} />
          </div>
          <Input name="note" label="Sipariş notu (isteğe bağlı)" />

          <label className="flex items-center gap-2 text-sm pt-1">
            <input type="checkbox" checked={corporate}
              onChange={(e) => setCorporate(e.target.checked)} />
            Kurumsal fatura istiyorum
          </label>
          {corporate && (
            <div className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3">
              <Input name="invoice_company" label="Firma Ünvanı" required maxLength={200} />
              <div className="grid grid-cols-2 gap-3">
                <Input name="invoice_tax_office" label="Vergi Dairesi" required maxLength={100} />
                <Input name="invoice_tax_no" label="Vergi No / TC Kimlik No" required
                  maxLength={20} inputMode="numeric" />
              </div>
            </div>
          )}

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
          <CouponInput />
          <div className="border-t border-zinc-200 pt-2 flex justify-between text-sm">
            <span>Ara toplam</span>
            <span className="font-semibold">{formatPrice(subtotal)}</span>
          </div>
          {coupon && !coupon.freeShipping && (
            <div className="flex justify-between text-sm text-emerald-600">
              <span>İndirim ({coupon.code})</span>
              <span>−{formatPrice(coupon.discountAmount)}</span>
            </div>
          )}
          {coupon?.freeShipping && (
            <div className="text-sm text-emerald-600">🎟️ Ücretsiz kargo uygulandı</div>
          )}
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
          <TrustBadges compact />
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
