"use client";

// Scroll'da yumuşak belirme — IntersectionObserver.
// Tema toggle'ı: layout <html data-reveal="0"> set ettiyse animasyon yapılmaz.
import { useEffect, useRef, useState } from "react";

export default function Reveal({
  delay = 0,
  children,
}: {
  delay?: number;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"hidden" | "visible" | "off">("hidden");

  useEffect(() => {
    if (document.documentElement.dataset.reveal === "0") {
      setState("off");
      return;
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setState("visible");
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -40px 0px", threshold: 0.05 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  if (state === "off") return <>{children}</>;

  return (
    <div
      ref={ref}
      className={state === "visible" ? "reveal-in" : "reveal-out"}
      style={state === "visible" && delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}
