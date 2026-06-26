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
        brand: {
          bg:     '#0e0f17',   // sayfa arka plan
          card:   '#171a26',   // kart arka plan
          input:  '#1f2231',   // input arka plan
          border: '#262a3a',
        },
        // Accent runtime CSS değişkeninden gelir (white-label per-tenant override).
        // Opacity modifier'lar (accent/15 vb.) için RGB kanalları kullanılır.
        accent: 'rgb(var(--accent-rgb) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
