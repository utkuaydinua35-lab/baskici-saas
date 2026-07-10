import { NextRequest, NextResponse } from "next/server";

// Canlı tema editörü: panel iframe'i /?onizleme=1 ile açar → kısa ömürlü çerez
// yazılır, sayfalar taslak temayı (theme_preview) önbelleksiz çeker.
export function middleware(req: NextRequest) {
  const res = NextResponse.next();
  const flag = req.nextUrl.searchParams.get("onizleme");
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
