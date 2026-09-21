import { NextRequest, NextResponse } from "next/server";

// Canlı tema editörü: panel iframe'i /?onizleme=1 ile açar → kısa ömürlü çerez
// yazılır, sayfalar taslak temayı (theme_preview) önbelleksiz çeker.
// Çerez yanıtla yazıldığından İLK istek onu göremez — parametre aynı isteğin
// request header'ına da yansıtılır ki editördeki değişiklik ilk yüklemede görünsün.
export function middleware(req: NextRequest) {
  const flag = req.nextUrl.searchParams.get("onizleme");
  const hasCookie = req.cookies.get("vitrin_onizleme")?.value === "1";

  const requestHeaders = new Headers(req.headers);
  // Kök düzen yolu bilemez; bakım ekranından MUAF sayfaları (sipariş takibi,
  // ödeme sonucu) ayırt edebilmesi için yol başlığa yazılır.
  requestHeaders.set("x-vitrin-yol", req.nextUrl.pathname);
  if (flag === "1" || (hasCookie && flag !== "0")) {
    requestHeaders.set("x-vitrin-onizleme", "1");
  }
  const res = NextResponse.next({ request: { headers: requestHeaders } });

  if (flag === "1") {
    res.cookies.set("vitrin_onizleme", "1", { maxAge: 900, path: "/" });
  } else if (flag === "0") {
    res.cookies.delete("vitrin_onizleme");
  }
  return res;
}

export const config = {
  matcher: ["/((?!_next|api|storage|favicon.ico).*)"],
};
