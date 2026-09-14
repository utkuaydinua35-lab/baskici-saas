/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Marka renkleri — BERNZ paletinden esinlenildi, gerekirse değiştir
        // Koyu mor + cam tema. Kartlar YARI SAYDAM (.card) olduğu icin bu
        // renkler zeminin ustune biner; opak karsiliklari fallback'tir.
        brand: {
          bg:     '#0a0613',   // sayfa zemini (mor-siyah)
          card:   '#17102b',   // kart zemini (saydamlik .card'da)
          input:  '#1e1638',   // input / ikincil yuzey
          border: '#2e2450',   // ince kenarlik
        },
        // Accent runtime CSS değişkeninden gelir (white-label per-tenant override).
        // Opacity modifier'lar (accent/15 vb.) için RGB kanalları kullanılır.
        accent: 'rgb(var(--accent-rgb) / <alpha-value>)',
      },
      // Kodda "border-white/8", "bg-amber-500/12" gibi ARA opaklıklar kullanılmış
      // (bayi paneli, ~40 yer) ama Tailwind'in ölçeğinde yalnız 5'in katları var:
      // bu sınıflar HİÇ ÜRETİLMİYORDU. Kenarlıklar varsayılan açık griye düşüyor
      // (koyu zeminde parlak çizgi), rozetlerin zemini hiç çıkmıyordu.
      opacity: {
        6: '0.06', 8: '0.08', 12: '0.12', 35: '0.35', 45: '0.45', 55: '0.55', 65: '0.65', 85: '0.85',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
