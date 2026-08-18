// Durum renkleri — TEK ölçek.
//
// Renkler daha önce her sayfada ayrı seçiliyordu: aynı anlam bir yerde amber,
// başka yerde sky oluyordu. Anlam → renk eşlemesi burada durur; yeni bir durum
// eklerken buraya bakılır.
//
// Ölçek (anlam sırasıyla):
//   notr     — bilgi, eylem gerektirmez
//   bekliyor — sırada, henüz başlamadı
//   islemde  — üzerinde çalışılıyor
//   tamam    — bitti, sorunsuz
//   uyari    — dikkat ister ama akışı durdurmaz
//   hata     — akışı durduran sorun
export const DURUM_RENK = {
  notr:     { cls: 'text-gray-400 bg-gray-500/10 border-gray-500/25',        nokta: 'bg-gray-400' },
  bekliyor: { cls: 'text-amber-300 bg-amber-500/10 border-amber-500/30',     nokta: 'bg-amber-400' },
  islemde:  { cls: 'text-accent bg-accent/10 border-accent/30',              nokta: 'bg-accent' },
  tamam:    { cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30', nokta: 'bg-emerald-400' },
  uyari:    { cls: 'text-orange-300 bg-orange-500/10 border-orange-500/30',  nokta: 'bg-orange-400' },
  hata:     { cls: 'text-red-300 bg-red-500/10 border-red-500/30',           nokta: 'bg-red-400' },
}

export const renk = (t) => DURUM_RENK[t] || DURUM_RENK.notr
