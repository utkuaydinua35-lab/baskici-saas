"use client";

// Pazarlama pikselleri — yalnızca panelde ID tanımlıysa yüklenir.
// Route değişimlerinde PageView tekrar gönderilir.
import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

interface Props {
  meta?: string | null;
  ga4?: string | null;
  tiktok?: string | null;
}

function inject(id: string, src: string, inline?: string) {
  if (document.getElementById(id)) return;
  if (inline) {
    const s = document.createElement("script");
    s.id = id;
    s.innerHTML = inline;
    document.head.appendChild(s);
  }
  if (src) {
    const s = document.createElement("script");
    s.id = `${id}-src`;
    s.async = true;
    s.src = src;
    document.head.appendChild(s);
  }
}

export default function Pixels({ meta, ga4, tiktok }: Props) {
  const pathname = usePathname();
  const loaded = useRef(false);

  // İlk yükleme: script'ler + init
  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;

    if (meta) {
      inject("px-meta", "", `
        !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
        n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
        document,'script','https://connect.facebook.net/en_US/fbevents.js');
        fbq('init', '${meta.replace(/[^0-9]/g, "")}');
      `);
    }
    if (ga4) {
      const gid = ga4.replace(/[^A-Za-z0-9-]/g, "");
      inject("px-ga4", `https://www.googletagmanager.com/gtag/js?id=${gid}`, `
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        window.gtag = gtag;
        gtag('js', new Date());
        gtag('config', '${gid}', { send_page_view: false });
      `);
    }
    if (tiktok) {
      const tid = tiktok.replace(/[^A-Za-z0-9]/g, "");
      inject("px-tiktok", "", `
        !function (w, d, t) {
          w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];ttq.methods=["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie"],ttq.setAndDefer=function(t,e){t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);ttq.instance=function(t){for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);return e},ttq.load=function(e,n){var i="https://analytics.tiktok.com/i18n/pixel/events.js";ttq._i=ttq._i||{},ttq._i[e]=[],ttq._i[e]._u=i,ttq._t=ttq._t||{},ttq._t[e]=+new Date,ttq._o=ttq._o||{},ttq._o[e]=n||{};var o=document.createElement("script");o.type="text/javascript",o.async=!0,o.src=i+"?sdkid="+e+"&lib="+t;var a=document.getElementsByTagName("script")[0];a.parentNode.insertBefore(o,a)}(ttq);
          ttq.load('${tid}');
        }(window, document, 'ttq');
      `);
    }
  }, [meta, ga4, tiktok]);

  // Her route değişiminde PageView
  useEffect(() => {
    window.fbq?.("track", "PageView");
    window.gtag?.("event", "page_view", { page_path: pathname });
    // @ts-expect-error ttq.page pixel API'sinde mevcut
    window.ttq?.page?.();
  }, [pathname]);

  return null;
}
