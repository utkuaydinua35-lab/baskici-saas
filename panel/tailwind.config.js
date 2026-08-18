/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // VISION UI — koyu lacivert + cam kartlar + mor/mavi gradyan.
        // Kaynak referans: Vision UI Dashboard (Creative Tim). Renkler
        // demodan ÖLÇÜLDÜ, tahmin edilmedi.
        //
        // Token ADLARI kasten korundu (panel-bg, panel-card, …): panelin 32
        // dosyası bu adları kullanıyor, yalnız değerleri değişince hepsi
        // birden koyu temaya geçiyor.
        panel: {
          bg: '#0b1437',       // sayfa zemini (üstüne aurora gradyanı biner)
          card: '#111c44',     // düz kart rengi (cam efekti .card sınıfında)
          border: 'rgba(255,255,255,0.10)',
          input: '#0f1535',    // girdi / ikincil yüzey
          ink: '#ffffff',
          muted: '#a0aec0',
          accent: '#0075ff',   // Vision UI marka mavisi
          accent2: '#4318ff',  // mor vurgu
          cyan: '#21d4fd',     // gradyanın açık ucu
          ok: '#01b574',
          warn: '#ffb547',
          err: '#e31a1a',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', '-apple-system', 'BlinkMacSystemFont',
               'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
