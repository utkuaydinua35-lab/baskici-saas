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
          bg:     '#070d0a',   // sayfa arka plan (koyu yeşil-siyah)
          card:   '#0e1612',   // kart / panel arka plan
          input:  '#16201b',   // input arka plan
          border: '#21302a',   // ince kenarlık
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
