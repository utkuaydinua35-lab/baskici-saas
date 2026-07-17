"use client";

// Güven şeridi — ürün sayfası ve ödeme sayfasında güvenlik/hizmet vurguları.
// Ödeme rozeti mağazanın AKTİF sağlayıcısını gösterir (iyzico VEYA PayTR).
import { useEffect, useState } from "react";

function useProvider(): string {
  const [provider, setProvider] = useState("iyzico");
  useEffect(() => {
    fetch("/api/shop-config")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const p = d?.settings?.payment_provider;
        if (p === "paytr" || p === "iyzico") setProvider(p);
      })
      .catch(() => {});
  }, []);
  return provider;
}

export default function TrustBadges({ compact = false }: { compact?: boolean }) {
  const provider = useProvider();
  const items = [
    { icon: "🔒", text: "256-bit SSL güvenli ödeme" },
    { icon: "💳", text: `${provider === "paytr" ? "PayTR" : "iyzico"} güvencesi` },
    { icon: "🚚", text: "1-3 iş gününde kargo" },
    { icon: "↩️", text: "Kolay iade ve değişim" },
  ];
  if (compact) {
    return (
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500">
        {items.map((i) => (
          <span key={i.text}>{i.icon} {i.text}</span>
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-2 text-xs text-zinc-600">
      {items.map((i) => (
        <div key={i.text}
          className="flex items-center gap-2 bg-zinc-50 border border-zinc-200 rounded-xl px-3 py-2">
          <span className="text-base">{i.icon}</span>
          {i.text}
        </div>
      ))}
    </div>
  );
}
