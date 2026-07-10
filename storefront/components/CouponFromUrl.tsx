"use client";

// Kupon paylaşım linki yakalayıcı — herhangi bir sayfada ?kupon=KOD varsa
// localStorage'a yazar; CouponInput sepette otomatik uygular.
import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { PENDING_COUPON_KEY } from "@/components/CouponInput";

export default function CouponFromUrl() {
  const params = useSearchParams();

  useEffect(() => {
    const code = (params.get("kupon") || "").trim().toUpperCase();
    if (!code || code.length > 40) return;
    try {
      localStorage.setItem(PENDING_COUPON_KEY, code);
    } catch {
      /* private mode */
    }
  }, [params]);

  return null;
}
