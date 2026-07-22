"use client";

// Ödeme sonucu — backend'i poll'lar (PayTR bildirimi tarayıcıdan bağımsız
// geldiği için "beklemede" durumu birkaç saniye sürebilir).
import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCart } from "@/lib/cart";
import { trackPurchaseOnce } from "@/lib/track";

interface StatusResponse {
  status: "pending" | "paid" | "failed" | "expired" | "cancelled";
  order_number?: string;
  lookup_token?: string;
  amount?: string;
  items?: { id: string; name?: string; quantity: number; price?: string }[];
}

const POLL_MS = 2500;
const MAX_POLLS = 24; // ~60 sn

export interface ThankyouText {
  title?: string;
  message?: string;
}

function ResultInner({ thankyou }: { thankyou?: ThankyouText | null }) {
  const params = useSearchParams();
  const token = params.get("token");
  const { clear } = useCart();
  const [state, setState] = useState<StatusResponse | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const polls = useRef(0);
  const cleared = useRef(false);

  useEffect(() => {
    if (!token) return;
    let stop = false;

    const poll = async () => {
      if (stop) return;
      polls.current += 1;
      try {
        const res = await fetch(`/api/checkout/${token}/status`, { cache: "no-store" });
        if (res.ok) {
          const data = (await res.json()) as StatusResponse;
          setState(data);
          if (data.status === "paid" && !cleared.current) {
            cleared.current = true;
            trackPurchaseOnce(token, {
              value: Number(data.amount || 0),
              orderId: data.order_number,
              // Katalog eşleşmesi: id = ürün slug'ı (Meta feed g:id ile aynı)
              items: (data.items || []).filter((i) => i.id).map((i) => ({
                id: i.id, name: i.name || "", price: Number(i.price || 0),
                quantity: i.quantity || 1,
              })),
            });
            clear(); // ödeme kesinleşti — sepeti boşalt
          }
          if (data.status !== "pending") return; // nihai durum
        }
      } catch {
        // geçici ağ hatası — poll devam eder
      }
      if (polls.current >= MAX_POLLS) {
        setTimedOut(true);
        return;
      }
      setTimeout(poll, POLL_MS);
    };
    poll();
    return () => {
      stop = true;
    };
  }, [token, clear]);

  if (!token) {
    return (
      <Shell icon="⚠️" title="Geçersiz bağlantı">
        <Link href="/" className="underline text-sm">Anasayfaya dön</Link>
      </Shell>
    );
  }

  if (state?.status === "paid") {
    return (
      <Shell icon="✅" title={thankyou?.title || "Siparişiniz alındı!"}>
        {state.order_number && (
          <p className="text-sm text-zinc-600">
            Sipariş numaranız: <b>#{state.order_number}</b>
          </p>
        )}
        <p className="text-sm text-zinc-600 mt-1 whitespace-pre-line">
          {thankyou?.message ||
            "Onay e-postası gönderildi. Siparişinizin durumunu istediğiniz an kontrol edebilirsiniz."}
        </p>
        {state.lookup_token && (
          <Link
            href={`/siparis/${state.lookup_token}`}
            className="mt-5 inline-block rounded-xl bg-zinc-900 text-white px-5 py-2.5 text-sm font-medium hover:bg-zinc-700"
          >
            Siparişimi Takip Et
          </Link>
        )}
      </Shell>
    );
  }

  if (state?.status === "failed" || state?.status === "expired" || state?.status === "cancelled") {
    return (
      <Shell icon="❌" title="Ödeme tamamlanamadı">
        <p className="text-sm text-zinc-600">
          Ödemeniz alınamadı. Kart bilgilerinizi kontrol edip tekrar deneyebilirsiniz.
          Hesabınızdan para çekildiyse, ödeme kuruluşu tarafından otomatik iade edilir.
        </p>
        <Link
          href="/odeme"
          className="mt-5 inline-block rounded-xl bg-zinc-900 text-white px-5 py-2.5 text-sm font-medium hover:bg-zinc-700"
        >
          Tekrar Dene
        </Link>
      </Shell>
    );
  }

  if (timedOut) {
    return (
      <Shell icon="⏳" title="Sonuç henüz ulaşmadı">
        <p className="text-sm text-zinc-600">
          Ödemeniz işleniyor olabilir. Bu sayfayı yenileyerek tekrar kontrol edin;
          sipariş kesinleştiyse e-posta da alacaksınız.
        </p>
      </Shell>
    );
  }

  return (
    <Shell icon="⏳" title="Ödemeniz doğrulanıyor…">
      <p className="text-sm text-zinc-500">Lütfen bu sayfayı kapatmayın.</p>
      <div className="mt-4 mx-auto h-1.5 w-40 overflow-hidden rounded bg-zinc-200">
        <div className="h-full w-1/3 bg-zinc-900 animate-pulse" />
      </div>
    </Shell>
  );
}

function Shell({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-xl px-4 py-20 text-center">
      <div className="text-5xl">{icon}</div>
      <h1 className="mt-4 text-xl font-semibold">{title}</h1>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export default function ResultClient({
  thankyou,
  demo = false,
}: {
  thankyou?: ThankyouText | null;
  demo?: boolean;
}) {
  // Tema editörü önizlemesi — ödeme olmadan onay ekranının örneğini gösterir
  if (demo) {
    return (
      <Shell icon="✅" title={thankyou?.title || "Siparişiniz alındı!"}>
        <p className="text-sm text-zinc-600">
          Sipariş numaranız: <b>#1234</b>
        </p>
        <p className="text-sm text-zinc-600 mt-1 whitespace-pre-line">
          {thankyou?.message ||
            "Onay e-postası gönderildi. Siparişinizin durumunu istediğiniz an kontrol edebilirsiniz."}
        </p>
        <span className="mt-5 inline-block rounded-xl bg-zinc-900 text-white px-5 py-2.5 text-sm font-medium">
          Siparişimi Takip Et
        </span>
      </Shell>
    );
  }
  return (
    <Suspense>
      <ResultInner thankyou={thankyou} />
    </Suspense>
  );
}
