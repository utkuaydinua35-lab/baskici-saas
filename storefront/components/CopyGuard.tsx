"use client";

// İçerik koruması — sağ tık menüsü, görsel sürükleme/kaydetme ve metin
// kopyalama engellenir. Form alanları (input/textarea/contenteditable)
// İSTİSNADIR: müşteri adres yazarken yapıştır/kopyala çalışmalı.
import { useEffect } from "react";

const FORM_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

function inForm(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node || !node.closest) return false;
  if (FORM_TAGS.has(node.tagName)) return true;
  return !!node.closest("input, textarea, select, [contenteditable='true']");
}

export default function CopyGuard() {
  useEffect(() => {
    const onContext = (e: MouseEvent) => { if (!inForm(e.target)) e.preventDefault(); };
    const onCopy = (e: ClipboardEvent) => { if (!inForm(e.target)) e.preventDefault(); };
    const onCut = (e: ClipboardEvent) => { if (!inForm(e.target)) e.preventDefault(); };
    const onDrag = (e: DragEvent) => {
      if ((e.target as HTMLElement)?.tagName === "IMG") e.preventDefault();
    };
    document.addEventListener("contextmenu", onContext);
    document.addEventListener("copy", onCopy);
    document.addEventListener("cut", onCut);
    document.addEventListener("dragstart", onDrag);

    const style = document.createElement("style");
    style.textContent = `
      body { -webkit-user-select: none; user-select: none; }
      input, textarea, select, [contenteditable="true"] {
        -webkit-user-select: text; user-select: text;
      }
      img { -webkit-user-drag: none; }
    `;
    document.head.appendChild(style);

    return () => {
      document.removeEventListener("contextmenu", onContext);
      document.removeEventListener("copy", onCopy);
      document.removeEventListener("cut", onCut);
      document.removeEventListener("dragstart", onDrag);
      style.remove();
    };
  }, []);

  return null;
}
