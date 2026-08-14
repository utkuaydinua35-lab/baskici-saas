"use client";

// Sepet — localStorage'da tutulur; sunucu istemci fiyatına ASLA güvenmez
// (checkout'ta variant_id+quantity gönderilir, fiyat sunucuda yeniden hesaplanır).
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

// Yerel depolama anahtarları MARKASIZ: aynı kurulumda başka markaların
// vitrinleri de çalışır, kimsenin tarayıcısında yabancı bir marka adı durmaz.
// Eski anahtar bir kez okunup taşınır — yayındaki müşterilerin sepeti kaybolmasın.
const CART_KEY = "vitrin_sepet_v1";
const ESKI_ANAHTARLAR = { sepet: "bernz_cart_v1", kupon: "bernz_coupon_v1" };

function tasi(yeni: string, eski: string): string | null {
  try {
    const mevcut = localStorage.getItem(yeni);
    if (mevcut !== null) return mevcut;
    const devir = localStorage.getItem(eski);
    if (devir === null) return null;
    localStorage.setItem(yeni, devir);
    localStorage.removeItem(eski);
    return devir;
  } catch { return null; }
}
const MAX_QTY = 20;
const MAX_ITEMS = 30;

export interface CartItem {
  variantId: string;
  productSlug: string;
  title: string;
  modelDisplay: string;
  variation: string | null;
  price: string; // yalnızca GÖSTERİM için — sunucu yeniden hesaplar
  image: string | null;
  quantity: number;
  // Couple ürünler: setin 2. kılıfının modeli
  secondVariantId?: string | null;
  secondModelDisplay?: string | null;
  // Kişiye özel alanlar {key: value} — sunucu ürün tanımına göre doğrular
  custom?: Record<string, string> | null;
  // Tasarım stüdyosunda hazırlanan tasarım (varsa) — sunucu doğrular
  designId?: string | null;
  designName?: string | null;
  designPreview?: string | null;
  // Satır kimliği: aynı varyantın farklı özel içerikleri ayrı satır olur
  lineId?: string;
}

export function cartLineId(
  i: Pick<CartItem, "variantId" | "secondVariantId" | "custom" | "designId">,
): string {
  // Her tasarım AYRI satırdır — aynı modelden iki farklı tasarım birleşmemeli
  if (!i.secondVariantId && !i.custom && !i.designId) return i.variantId;
  return `${i.variantId}::${i.secondVariantId || ""}::${i.designId || ""}::${JSON.stringify(i.custom || {})}`;
}

export interface AppliedCoupon {
  code: string;
  kind: string;
  discountAmount: string; // gösterim — sunucu ödeme anında yeniden doğrular
  freeShipping: boolean;
  // Sunucunun hesapladığı KESİN kargo ve toplam (kupon uygulanmış hâli)
  shipping?: string;
  total?: string;
  // Kupon "birleşebilir" ise otomatik indirim de eklenmiş olabilir; tutarlar
  // yukarıdaki toplamlara zaten dahildir, bu liste yalnız gösterim içindir
  combined?: { code: string; label: string }[];
}

interface CartContextValue {
  items: CartItem[];
  count: number;
  subtotal: number;
  coupon: AppliedCoupon | null;
  setCoupon: (c: AppliedCoupon | null) => void;
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  addItem: (item: Omit<CartItem, "quantity">, quantity?: number) => void;
  removeItem: (variantId: string) => void;
  setQuantity: (variantId: string, quantity: number) => void;
  clear: () => void;
}

const CartContext = createContext<CartContextValue | null>(null);

function load(): CartItem[] {
  try {
    const raw = tasi(CART_KEY, ESKI_ANAHTARLAR.sepet);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_ITEMS) : [];
  } catch {
    return [];
  }
}

const COUPON_KEY = "vitrin_kupon_v1";

function loadCoupon(): AppliedCoupon | null {
  try {
    const raw = tasi(COUPON_KEY, ESKI_ANAHTARLAR.kupon);
    return raw ? (JSON.parse(raw) as AppliedCoupon) : null;
  } catch {
    return null;
  }
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [coupon, setCouponState] = useState<AppliedCoupon | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setItems(load());
    setCouponState(loadCoupon());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) localStorage.setItem(CART_KEY, JSON.stringify(items));
  }, [items, hydrated]);

  const setCoupon = useCallback((c: AppliedCoupon | null) => {
    setCouponState(c);
    if (c) localStorage.setItem(COUPON_KEY, JSON.stringify(c));
    else localStorage.removeItem(COUPON_KEY);
  }, []);

  const addItem = useCallback((item: Omit<CartItem, "quantity">, quantity = 1) => {
    setItems((prev) => {
      const lid = item.lineId ?? cartLineId(item);
      const existing = prev.find((i) => (i.lineId ?? cartLineId(i)) === lid);
      if (existing) {
        return prev.map((i) =>
          (i.lineId ?? cartLineId(i)) === lid
            ? { ...i, quantity: Math.min(MAX_QTY, i.quantity + quantity) }
            : i,
        );
      }
      if (prev.length >= MAX_ITEMS) return prev;
      return [...prev, { ...item, lineId: lid, quantity: Math.min(MAX_QTY, quantity) }];
    });
  }, []);

  const removeItem = useCallback((lineOrVariantId: string) => {
    setItems((prev) => prev.filter((i) => (i.lineId ?? cartLineId(i)) !== lineOrVariantId));
  }, []);

  const setQuantity = useCallback((lineOrVariantId: string, quantity: number) => {
    setItems((prev) =>
      quantity <= 0
        ? prev.filter((i) => (i.lineId ?? cartLineId(i)) !== lineOrVariantId)
        : prev.map((i) =>
            (i.lineId ?? cartLineId(i)) === lineOrVariantId
              ? { ...i, quantity: Math.min(MAX_QTY, quantity) }
              : i,
          ),
    );
  }, []);

  const clear = useCallback(() => {
    setItems([]);
    setCoupon(null);
  }, [setCoupon]);

  const value = useMemo<CartContextValue>(() => {
    const count = items.reduce((s, i) => s + i.quantity, 0);
    const subtotal = items.reduce((s, i) => s + Number(i.price) * i.quantity, 0);
    return {
      items, count, subtotal, coupon, setCoupon, drawerOpen, setDrawerOpen,
      addItem, removeItem, setQuantity, clear,
    };
  }, [items, coupon, setCoupon, drawerOpen, addItem, removeItem, setQuantity, clear]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart, CartProvider içinde kullanılmalı");
  return ctx;
}
