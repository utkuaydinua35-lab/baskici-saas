"use client";

// Özel kod enjeksiyonu — innerHTML ile eklenen <script> tarayıcıda ÇALIŞMAZ;
// script etiketleri gerçek DOM düğümü olarak yeniden oluşturulur.
// Yalnızca mağaza sahibinin panelden girdiği kod; kendi vitrininde çalışır.
import { useEffect, useRef } from "react";

export default function CustomCode({ html }: { html: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const done = useRef(false);

  useEffect(() => {
    if (!ref.current || done.current || !html) return;
    done.current = true;
    const container = ref.current;
    container.innerHTML = html;
    // Script'leri çalıştırılabilir kopyalarla değiştir
    container.querySelectorAll("script").forEach((old) => {
      const script = document.createElement("script");
      for (const attr of old.attributes) script.setAttribute(attr.name, attr.value);
      script.text = old.text;
      old.replaceWith(script);
    });
  }, [html]);

  return <div ref={ref} />;
}
