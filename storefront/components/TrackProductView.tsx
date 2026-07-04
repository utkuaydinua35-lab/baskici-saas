"use client";

// Ürün sayfası ViewContent olayı — server component'ten küçük client köprüsü.
import { useEffect } from "react";
import { trackViewContent } from "@/lib/track";

export default function TrackProductView({
  id,
  name,
  price,
}: {
  id: string;
  name: string;
  price: number;
}) {
  useEffect(() => {
    trackViewContent({ id, name, price, quantity: 1 });
  }, [id, name, price]);
  return null;
}
