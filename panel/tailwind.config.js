/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Açık "commerce" teması — Baskıcı'nın koyu brand-* paletinden bilinçli farklı
        panel: {
          bg: '#f8fafc',       // sayfa zemini (slate-50)
          card: '#ffffff',
          border: '#e2e8f0',   // slate-200
          input: '#f1f5f9',    // slate-100
          ink: '#0f172a',      // slate-900
          muted: '#64748b',    // slate-500
          accent: '#059669',   // emerald-600
          accent2: '#4f46e5',  // indigo-600
        },
      },
    },
  },
  plugins: [],
}
