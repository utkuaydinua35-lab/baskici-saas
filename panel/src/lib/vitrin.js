// Mağazanın müşteriye görünen adresi — backend'deki services/site.py
// site_url() ile AYNI sıra: storefront_url → custom_domain → shop_domain.
//
// Panel eskiden custom_domain'i atlıyordu: yalnız kendi alan adı bağlanmış
// bir mağazada (Lunera) "Vitrini Gör" hiç çıkmıyor, SEO önizlemesi ise BERNZ'in
// alan adını gösteriyordu. İki tarafın aynı kuralı izlemesi şart.
export function vitrinAdresi(store) {
  const c = store?.config || {}
  const elle = (c.storefront_url || '').trim()
  if (elle) return elle.replace(/\/+$/, '')
  const alan = (c.custom_domain || c.shop_domain || '').trim().replace(/\/+$/, '')
  if (!alan) return null
  return /^https?:\/\//.test(alan) ? alan : `https://${alan}`
}

/** SEO önizlemesi için yalnız alan adı: "luneracase.com" */
export function vitrinAlanAdi(store) {
  const a = vitrinAdresi(store)
  return a ? a.replace(/^https?:\/\//, '') : 'magazaniz.com'
}
