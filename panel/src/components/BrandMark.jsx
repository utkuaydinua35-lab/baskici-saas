// Marka işareti — favicon.svg ve PWA ikonuyla AYNI glif ve gradyan.
// Üçü birlikte değişmeli, yoksa ana ekrandaki ikon panelde başka görünür.
export default function BrandMark({ size = 26, glow = true }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden
      className={glow ? 'drop-shadow-[0_0_10px_rgba(0,117,255,0.55)]' : ''}>
      <defs>
        <linearGradient id="bm" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0075ff" />
          <stop offset="1" stopColor="#21d4fd" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#bm)" />
      <path d="M10.5 12h11l-1.1 10.2a2 2 0 0 1-2 1.8h-4.8a2 2 0 0 1-2-1.8L10.5 12z"
        fill="#fff" opacity="0.96" />
      <path d="M12.8 12v-1.4a3.2 3.2 0 0 1 6.4 0V12" fill="none"
        stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M13.6 15a2.4 2.4 0 0 0 4.8 0" fill="none" stroke="#0060d2"
        strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  )
}
