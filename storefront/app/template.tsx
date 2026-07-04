// Sayfalar arası geçiş animasyonu — her navigasyonda yeniden mount olur.
// html[data-reveal="0"] ise animasyon CSS'te kapatılır (globals.css).
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-transition">{children}</div>;
}
