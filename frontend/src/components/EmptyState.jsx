// Boş ekranlar tek biçim. Düz gri bir cümle "bir şey mi bozuldu?" hissi
// veriyordu; ikon + açıklama + (varsa) aksiyon bunu "burada henüz bir şey yok"a
// çeviriyor.
export default function EmptyState({ ikon = '📭', baslik, aciklama, aksiyon, dar = false }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center ${dar ? 'py-8' : 'py-14'} px-6`}>
      <div className="w-14 h-14 rounded-2xl bg-brand-input/70 border border-brand-border
                      flex items-center justify-center text-2xl mb-3 select-none">
        {ikon}
      </div>
      <div className="text-sm font-medium text-gray-300">{baslik}</div>
      {aciklama && <p className="text-xs text-gray-500 mt-1.5 max-w-sm leading-relaxed">{aciklama}</p>}
      {aksiyon && <div className="mt-4">{aksiyon}</div>}
    </div>
  )
}
