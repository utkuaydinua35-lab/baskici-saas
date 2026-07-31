/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Baskıcı (studio) ile AYNI koyu tema — Cryptix stili yeşil-siyah.
        // Kaynak: frontend/tailwind.config.js brand.* paleti.
        // SOFT tema — Shopify admin'in açık, yumuşak paleti.
        // Göz yormayan kırık beyaz zemin + beyaz kartlar + koyu lacivert metin.
        panel: {
          bg: '#f6f6f7',       // sayfa arka planı (kırık beyaz)
          card: '#ffffff',     // kart / panel arka planı
          border: '#e1e3e5',   // ince kenarlık
          input: '#f1f2f4',    // input / ikincil yüzey
          ink: '#202223',      // ana metin (koyu gri-siyah)
          muted: '#6d7175',    // ikincil metin
          accent: '#008060',   // Shopify yeşili — birincil aksiyon
          accent2: '#5c6ac4',  // indigo — ikincil vurgu
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
