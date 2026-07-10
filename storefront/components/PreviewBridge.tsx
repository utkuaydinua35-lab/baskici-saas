"use client";

// Canlı tema editörü köprüsü — yalnızca önizleme modunda render edilir.
// Bölümlere hover çerçevesi çizer; tıklanınca panel'e bölüm id'sini bildirir
// (panel o bölümün editörünü açar). Linklerin gezinmesini engellemez.
import { useEffect } from "react";

export default function PreviewBridge() {
  useEffect(() => {
    const style = document.createElement("style");
    style.textContent = `
      [data-sec-id] { position: relative; }
      [data-sec-id]:hover { outline: 2px dashed rgba(16,185,129,.8); outline-offset: -2px; cursor: pointer; }
      [data-sec-id]:hover::after {
        content: "✏️ Düzenlemek için tıkla";
        position: absolute; top: 6px; right: 8px; z-index: 30;
        background: rgb(16,185,129); color: white; font-size: 11px;
        padding: 2px 8px; border-radius: 999px; font-family: sans-serif;
      }
    `;
    document.head.appendChild(style);

    const onClick = (e: MouseEvent) => {
      const target = (e.target as HTMLElement).closest("[data-sec-id]");
      if (!target) return;
      e.preventDefault();
      e.stopPropagation();
      window.parent?.postMessage(
        { type: "vitrin-sec-click", id: target.getAttribute("data-sec-id") },
        "*",
      );
    };
    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("click", onClick, true);
      style.remove();
    };
  }, []);

  return (
    <div className="fixed bottom-3 left-3 z-50 text-[11px] bg-emerald-600 text-white rounded-full px-3 py-1.5 shadow-lg font-medium">
      👁 Önizleme modu — bölüme tıklayıp düzenleyin
    </div>
  );
}
