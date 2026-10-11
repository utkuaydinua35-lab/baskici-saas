// Telefon numarasını wa.me biçimine çevirir: ülke kodlu, yalnız rakam.
//
// Eskiden bağlantı `wa.me/9` + rakamlar diye kuruluyordu — numaranın "0" ile
// başladığını VARSAYIYORDU. Müşteri "530 428 34 93" yazınca 95304283493 çıktı
// (Myanmar kodu) ve WhatsApp "bu numara WhatsApp kullanmıyor" dedi.
//   05304283493 / 5304283493 / +90 530 428 34 93 / 0090530… → 905304283493
// Türk cep numarasına benzemeyen (yabancı, ülke kodlu) numara olduğu gibi kalır.
export function waNumara(telefon) {
  let r = String(telefon || '').replace(/\D/g, '')
  if (r.startsWith('00')) r = r.slice(2)
  if (r.length === 12 && r.startsWith('90')) return r
  if (r.length === 11 && r.startsWith('0')) return '9' + r
  if (r.length === 10 && r.startsWith('5')) return '90' + r
  return r
}

export function waBaglanti(telefon, metin) {
  const n = waNumara(telefon)
  if (!n) return null
  return `https://wa.me/${n}${metin ? `?text=${encodeURIComponent(metin)}` : ''}`
}
