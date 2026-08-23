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
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
