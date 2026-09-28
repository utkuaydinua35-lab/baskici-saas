// İnce çizgi ikonlar — ikon şeridi (serit stili) için. Ad listesi backend
// theme.py CIZGI_IKONLAR ile birebir. Ad tanınmazsa değer emoji/yazı olarak
// basılır (eski "🚚" ikonları bozulmaz).
const YOLLAR: Record<string, React.ReactNode> = {
  kargo: (<><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7" /><circle cx="7" cy="17.5" r="1.7" /><circle cx="17" cy="17.5" r="1.7" /></>),
  konum: (<><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21Z" /><circle cx="12" cy="9.5" r="2.5" /></>),
  iade: (<><path d="M4 9h11a5 5 0 0 1 0 10H9" /><path d="m8 5-4 4 4 4" /></>),
  eposta: (<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3.5 6 8.5 7 8.5-7" /></>),
  destek: (<><path d="M4 13v-1a8 8 0 0 1 16 0v1" /><rect x="3" y="13" width="4" height="6" rx="1.5" /><rect x="17" y="13" width="4" height="6" rx="1.5" /><path d="M19 19a4 4 0 0 1-4 3h-2" /></>),
  guvenli: (<><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>),
  hediye: (<><rect x="4" y="9" width="16" height="11" rx="1.5" /><path d="M3 9h18M12 9v11M12 9S10.5 4 8 4.5 7 9 12 9Zm0 0s1.5-5 4-4.5S17 9 12 9Z" /></>),
  yildiz: (<path d="m12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6-5.4-2.9-5.4 2.9 1.1-6-4.5-4.2 6.1-.8Z" />),
  kalp: (<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21.2l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8Z" />),
  saat: (<><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>),
  telefon: (<><rect x="7" y="2.5" width="10" height="19" rx="2.5" /><path d="M11 18.5h2" /></>),
  kutu: (<><path d="m3.5 7.5 8.5-4 8.5 4v9l-8.5 4-8.5-4Z" /><path d="m3.5 7.5 8.5 4 8.5-4M12 11.5v9" /></>),
};

export const CIZGI_IKON_ADLARI = Object.keys(YOLLAR);

export default function CizgiIkon({ ad, className = "w-6 h-6" }: { ad: string; className?: string }) {
  const yol = YOLLAR[ad];
  if (!yol) return <span className="text-2xl leading-none">{ad || "✨"}</span>;
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      {yol}
    </svg>
  );
}
