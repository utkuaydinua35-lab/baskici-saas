// Güven şeridi — ürün sayfası ve ödeme sayfasında güvenlik/hizmet vurguları.
const ITEMS = [
  { icon: "🔒", text: "256-bit SSL güvenli ödeme" },
  { icon: "💳", text: "iyzico / PayTR güvencesi" },
  { icon: "🚚", text: "1-3 iş gününde kargo" },
  { icon: "↩️", text: "Kolay iade ve değişim" },
];

export default function TrustBadges({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500">
        {ITEMS.map((i) => (
          <span key={i.text}>{i.icon} {i.text}</span>
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-2 text-xs text-zinc-600">
      {ITEMS.map((i) => (
        <div key={i.text}
          className="flex items-center gap-2 bg-zinc-50 border border-zinc-200 rounded-xl px-3 py-2">
          <span className="text-base">{i.icon}</span>
          {i.text}
        </div>
      ))}
    </div>
  );
}
