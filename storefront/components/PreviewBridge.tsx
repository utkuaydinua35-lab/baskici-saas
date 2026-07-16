"use client";

// Canlı tema editörü köprüsü — yalnızca panel'in editör IFRAME'i içinde çalışır.
// Bölümlere hover çerçevesi çizer; tıklanınca panel'e bölüm id'sini bildirir.
//
// KRİTİK: ?onizleme=1 çerezi tarayıcıda 15 dk yaşar; kullanıcı editörden sonra
// siteyi NORMAL sekmede gezerse önizleme moduna sıkışıyordu ("düzenlemek için
// tıkla" her yerde). İframe dışında olduğumuzu görürsek çerezi silip sayfayı
// tazeleyerek kendiliğinden normal moda döneriz.
import { useEffect, useState } from "react";

export default function PreviewBridge() {
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (window.self === window.top) {
      // Editör iframe'i dışındayız — önizleme modundan otomatik çık
      // (?onizleme=1 parametresi de düşer, yoksa middleware çerezi geri yazar)
      document.cookie = "vitrin_onizleme=; Max-Age=0; path=/";
      window.location.replace(window.location.pathname);
      return;
    }
    setActive(true);

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

  if (!active) return null;
  return (
    <div className="fixed bottom-3 left-3 z-50 text-[11px] bg-emerald-600 text-white rounded-full px-3 py-1.5 shadow-lg font-medium">
      👁 Önizleme modu — bölüme tıklayıp düzenleyin
    </div>
  );
}
