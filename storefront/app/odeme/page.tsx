"use client";

// Misafir checkout — form + KVKK onayı → backend ödeme oturumu → redirect/iframe.
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import CouponInput from "@/components/CouponInput";
import { trackAddPaymentInfo, trackInitiateCheckout } from "@/lib/track";
import TrustBadges from "@/components/TrustBadges";
import IlIlceSelect from "@/components/IlIlceSelect";
import { useAutoQuote } from "@/lib/useAutoQuote";

interface CheckoutResponse {
  token: string;
  mode: "redirect" | "iframe";
  url: string;
  amount: string;
  shipping_amount: string;
}

interface AdresKaydi {
  title?: string;
  first_name?: string; last_name?: string; phone?: string;
  address1?: string; city?: string; province?: string; zip?: string;
}

export default function CheckoutPage() {
  const { items, subtotal, coupon, setCoupon } = useCart();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [iframeUrl, setIframeUrl] = useState<string | null>(null);
  const [checkoutToken, setCheckoutToken] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<Record<string, string>>({});
  const [corporate, setCorporate] = useState(false);
  const [giftWrapOn, setGiftWrapOn] = useState(false);   // mağaza ayarı açık mı
  const [giftWrap, setGiftWrap] = useState(false);       // müşteri istedi mi
  const [shipCfg, setShipCfg] = useState<{ fee: number; freeOver: number } | null>(null);
  // Otomatik kampanya (örn. 3 al 2 öde) — sunucudan gerçek tutar (kupon girilirse kod kazanır)
  const autoQuote = useAutoQuote(items, coupon);

  useEffect(() => {
    fetch("/api/shop-config")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setGiftWrapOn(!!d?.settings?.gift_wrap_enabled);
        setShipCfg({
          fee: Number(d?.settings?.shipping_fee || 0),
          freeOver: Number(d?.settings?.free_shipping_over || 0),
        });
      })
      .catch(() => {});
  }, []);

  // Tahmini kargo/toplam — kesin tutar yine sunucuda hesaplanır
  // Kupon kargo bedava İLE birleşmiş olabilir — para indirimi ayrı tutulur
  const discountAmt = coupon
    ? Number(coupon.discountAmount) || 0
    : autoQuote ? autoQuote.discount : 0;
  // KESİN tutar SUNUCUDAN gelir (kupon yanıtı ya da /api/quote). Sayfa kendi
  // kargo hesabını yapınca gösterilen tutar TAHSİL EDİLENLE ÇELİŞEBİLİYORDU:
  // özet "Tahmini Toplam 484,00" derken karta 399,90 düşüyordu (sunucu kargoyu
  // 0 hesaplamıştı). Sunucu değeri yoksa yalnız İLK saniyede config'ten kaba
  // tahmin gösterilir.
  const sunucuKargo = coupon?.shipping != null ? Number(coupon.shipping)
    : autoQuote ? autoQuote.shipping : null;
  const sunucuToplam = coupon?.total != null ? Number(coupon.total)
    : autoQuote ? autoQuote.total : null;

  const kabaKargo = shipCfg == null ? null
    : (coupon?.freeShipping || autoQuote?.freeShipping) ? 0
    : shipCfg.freeOver > 0 && subtotal >= shipCfg.freeOver ? 0
    : shipCfg.fee;
  const estShipping = sunucuKargo ?? kabaKargo;
  const estTotal = sunucuToplam
    ?? (estShipping == null ? null : Math.max(0, subtotal - discountAmt) + estShipping);
  // Sunucu tutarı geldiyse "tahmini" demek yanıltıcı olur
  const kesin = sunucuToplam != null;

  // Girişli müşteri: kayıtlı bilgilerle formu doldur. Birden fazla adres
  // varsa üstte kartlar çıkar, tıklayınca form o adrese göre yenilenir
  // (form uncontrolled olduğu için key değişimiyle yeniden kurulur).
  const [adresler, setAdresler] = useState<AdresKaydi[]>([]);
  const [adresIdx, setAdresIdx] = useState(0);
  const [hesap, setHesap] = useState<{ name?: string; email?: string; phone?: string } | null>(null);

  const adresiUygula = useCallback((a: AdresKaydi, me: typeof hesap) => {
    setPrefill({
      first_name: a?.first_name || (me?.name || "").split(" ")[0] || "",
      last_name: a?.last_name || (me?.name || "").split(" ").slice(1).join(" ") || "",
      email: me?.email || "",
      phone: a?.phone || me?.phone || "",
      address1: a?.address1 || "",
      city: a?.city || "",
      province: a?.province || "",
      zip: a?.zip || "",
    });
  }, []);

  useEffect(() => {
    fetch("/api/account")
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => {
        if (!me) return;
        setHesap(me);
        const liste: AdresKaydi[] = Array.isArray(me.addresses) && me.addresses.length
          ? me.addresses
          : (me.default_address ? [me.default_address] : []);
        setAdresler(liste);
        adresiUygula(liste[0] || {}, me);
      })
      .catch(() => {});
  }, [adresiUygula]);

  useEffect(() => {
    if (items.length === 0) return;
    trackInitiateCheckout({
      value: subtotal,
      // id = ürün slug'ı — Meta katalog (g:id) ile aynı anahtar
      items: items.map((i) => ({
        id: i.productSlug, name: i.title, price: Number(i.price), quantity: i.quantity,
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
          items: items.map((i) => ({
            variant_id: i.variantId, quantity: i.quantity,
            second_variant_id: i.secondVariantId || null,
            custom: i.custom || null,
            design_id: i.designId || null,
          })),
          customer: {
            first_name: fd.get("first_name"),
            last_name: fd.get("last_name"),
            email: fd.get("email"),
            phone: fd.get("phone"),
            address1: fd.get("address1"),
            city: fd.get("city"),
            province: fd.get("province") || null,
            zip: fd.get("zip") || null,
            note: [giftWrap ? "🎁 Hediye paketi istiyorum" : null, fd.get("note") || null]
              .filter(Boolean).join(" — ") || null,
            invoice_company: fd.get("invoice_company") || null,
            invoice_tax_office: fd.get("invoice_tax_office") || null,
            invoice_tax_no: fd.get("invoice_tax_no") || null,
          },
          kvkk_accept: fd.get("kvkk_accept") === "on",
          discount_code: coupon?.code || null,
          // Meta CAPI eşleşme sinyalleri — piksel çerezleri (varsa)
          fbp: document.cookie.match(/(?:^|;\s*)_fbp=([^;]+)/)?.[1] || null,
          fbc: document.cookie.match(/(?:^|;\s*)_fbc=([^;]+)/)?.[1] || null,
          // Ziyaretçi kimliği — CAPI Purchase'ta gezinme olaylarıyla aynı external_id
          vid: document.cookie.match(/(?:^|;\s*)bz_vid=([^;]+)/)?.[1] || null,
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
      // Kart bilgisi aşaması — ödeme sağlayıcısının sayfasına geçiş anı
      trackAddPaymentInfo({
        value: Number(out.amount || 0),
        items: items.map((i) => ({
          id: i.productSlug, name: i.title, price: Number(i.price), quantity: i.quantity,
        })),
      });
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
      {/* Kayıtlı adresler — birden fazlaysa aralarında geçiş */}
      {adresler.length > 1 && (
        <div className="mb-4">
          <div className="text-xs text-zinc-500 mb-1.5">Kayıtlı adreslerin</div>
          <div className="grid sm:grid-cols-2 gap-2">
            {adresler.map((a, i) => (
              <button key={i} type="button"
                onClick={() => { setAdresIdx(i); adresiUygula(a, hesap); }}
                className={`text-left rounded-xl border px-3 py-2 text-xs transition ${
                  adresIdx === i
                    ? "border-zinc-900 bg-zinc-50"
                    : "border-zinc-200 hover:border-zinc-400"}`}>
                <div className="font-medium text-sm">
                  {a.title || `${a.first_name || ""} ${a.last_name || ""}`.trim() || `Adres ${i + 1}`}
                  {adresIdx === i && <span className="ml-1.5 text-[10px]">✓ seçili</span>}
                </div>
                <div className="text-zinc-600 mt-0.5 line-clamp-2">{a.address1}</div>
                <div className="text-zinc-500">{[a.province, a.city].filter(Boolean).join(" / ")}</div>
              </button>
            ))}
          </div>
          <p className="text-[11px] text-zinc-400 mt-1.5">
            Seçtiğin adres aşağıdaki forma dolar; istersen üzerinde değişiklik yapabilirsin.
          </p>
        </div>
      )}

      <form key={`${prefill.email || "misafir"}-${adresIdx}`} onSubmit={submit} className="grid md:grid-cols-[1fr_260px] gap-6 items-start">
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
            <IlIlceSelect defaultIl={prefill.city} defaultIlce={prefill.province} />
            <Input name="zip" label="Posta Kodu" autoComplete="postal-code" defaultValue={prefill.zip} />
          </div>
          <Input name="note" label="Sipariş notu (isteğe bağlı)" maxLength={500} />
          {giftWrapOn && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={giftWrap}
                onChange={(e) => setGiftWrap(e.target.checked)} />
              🎁 Hediye paketi istiyorum (ücretsiz)
            </label>
          )}

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
          {coupon && Number(coupon.discountAmount) > 0 && (
            <div className="flex justify-between text-sm text-emerald-600">
              <span>İndirim ({coupon.code})</span>
              <span>−{formatPrice(coupon.discountAmount)}</span>
            </div>
          )}
          {coupon?.freeShipping && (
            <div className="text-sm text-emerald-600">🎟️ Ücretsiz kargo uygulandı</div>
          )}
          {!coupon && autoQuote && autoQuote.discount > 0 && (
            <div className="flex justify-between text-sm text-emerald-600">
              <span>🎁 Kampanya{autoQuote.code ? ` (${autoQuote.code})` : ""}</span>
              <span>−{formatPrice(autoQuote.discount)}</span>
            </div>
          )}
          {!coupon && autoQuote?.freeShipping && (
            <div className="text-sm text-emerald-600">🎁 Kampanya: kargo ücretsiz</div>
          )}
          {estShipping != null && (
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">Kargo</span>
              <span>{estShipping === 0
                ? <span className="text-emerald-600 font-medium">Ücretsiz</span>
                : formatPrice(estShipping)}</span>
            </div>
          )}
          {estTotal != null && (
            <div className="flex justify-between text-sm border-t border-zinc-200 pt-2 font-semibold">
              <span>{kesin ? "Genel Toplam" : "Tahmini Toplam"}</span>
              <span>{formatPrice(estTotal)}</span>
            </div>
          )}
          <p className="text-[11px] text-zinc-400">
            {kesin
              ? "Kartınızdan tahsil edilecek tutar budur."
              : "Kesin tutar güvenli ödeme sayfasında onaylanır."}
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
