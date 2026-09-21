// Platform kimliği — GİRİŞ EKRANINDA görünür (kiracı henüz belli değilken).
//
// Nötr: sistem kiralanıyor ve aynı panel tüm kiracılara servis ediliyor.
// Eskiden "BERNZ Commerce" sabitti; her kiracı BERNZ markasını görüyordu.
// Giriş SONRASI üst bar kiracının KENDİ adını gösterir (Layout.jsx).
// Platform adını değiştirmek için derlemede: VITE_PLATFORM_ADI="…"
export const BRAND = import.meta.env.VITE_PLATFORM_ADI || 'Mağaza Paneli'
export const BRAND_SHORT = BRAND.slice(0, 1)
export const TAGLINE = 'Mağazanı yönet, satışını büyüt'
