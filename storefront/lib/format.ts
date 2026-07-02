export function formatPrice(value: string | number, currency = "TRY"): string {
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return String(value);
  return new Intl.NumberFormat("tr-TR", { style: "currency", currency }).format(n);
}
