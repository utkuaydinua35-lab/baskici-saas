/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Baskıcı (studio) ile AYNI koyu tema — Cryptix stili yeşil-siyah.
        // Kaynak: frontend/tailwind.config.js brand.* paleti.
        panel: {
          bg: '#070d0a',       // sayfa arka planı (koyu yeşil-siyah)
          card: '#0e1612',     // kart / panel arka planı
          border: '#21302a',   // ince kenarlık
          input: '#16201b',    // input arka planı
          ink: '#f3f4f6',      // ana metin (gray-100)
          muted: '#8aa096',    // ikincil metin (yeşilimsi gri)
          accent: '#14b8a6',   // teal — Baskıcı accent'iyle aynı
          accent2: '#818cf8',  // indigo-400
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
