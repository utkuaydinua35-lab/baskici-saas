#!/usr/bin/env node
// Kontrast denetimi — "beyaz zeminde beyaz yazı" sınıfı hataları yakalar.
//
// NEDEN VAR
// Panel açık temadan koyu temaya geçirildi ve token DEĞERLERİ değişti,
// ADLARI aynı kaldı. `panel-ink` (metin rengi) açık temada koyu griydi,
// koyu temada beyaz oldu. Onu ZEMİN olarak kullanan yerler sessizce
// görünmez hâle geldi — kaydetme bandı böyle kayboldu, bir kez gösterilen
// API anahtarı böyle okunamaz oldu. Derleyici bunu yakalayamaz.
//
// NE YAPAR
// Her className metnindeki bg-* ve text-* sınıflarını gerçek renklere
// çözer, WCAG kontrast oranını hesaplar ve iki şeyi bildirir:
//   1. OPAK AÇIK zemin + metin rengi YOK  → yazı beyaz miras alır, kaybolur
//   2. Zemin + metin birlikte, kontrast < 3.0 → okunmaz
// Saydam zeminler (bg-white/5 gibi) atlanır: koyu temanın normal deyimi.
//
// Çalıştırma:  node scripts/kontrast.mjs
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import renkler from 'tailwindcss/colors.js'

const KOK = new URL('../src', import.meta.url).pathname

// tailwind.config.js'teki panel paleti (tek kaynak orada; burada yansıması)
const PANEL = {
  bg: '#0b1437', card: '#111c44', input: '#0f1535',
  ink: '#ffffff', muted: '#a0aec0',
  accent: '#0075ff', accent2: '#4318ff', cyan: '#21d4fd',
  ok: '#01b574', warn: '#ffb547', err: '#e31a1a',
}
const MIRAS_METIN = '#ffffff'   // body rengi: koyu temada metin beyaz

const hex = (h) => {
  h = h.replace('#', '')
  if (h.length === 3) h = [...h].map((c) => c + c).join('')
  return h.length === 6 ? [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) : null
}
const parlaklik = (rgb) => {
  const [r, g, b] = rgb.map((v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const kontrast = (a, b) => {
  const [x, y] = [parlaklik(a), parlaklik(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}

/** "bg-emerald-300" / "text-panel-ink" / "bg-[#0f1535]" → #rrggbb | null
 *  Saydam olanlar (…/20) bilerek null döner — koyu zemin üstünde sorun değil. */
function coz(sinif) {
  const m = sinif.match(/^(bg|text)-(.+)$/)
  if (!m) return null
  let deger = m[2]
  if (deger.includes('/')) return null                    // saydam → atla
  if (deger.startsWith('[') && deger.endsWith(']')) {
    const ic = deger.slice(1, -1)
    return ic.startsWith('#') ? ic : null
  }
  if (deger === 'white') return '#ffffff'
  if (deger === 'black') return '#000000'
  if (deger === 'transparent' || deger === 'current' || deger === 'inherit') return null
  const p = deger.match(/^panel-(\w+)$/)
  if (p) return PANEL[p[1]] || null
  const t = deger.match(/^([a-z]+)-(\d{2,3})$/)
  if (t && renkler[t[1]] && renkler[t[1]][t[2]]) return renkler[t[1]][t[2]]
  return null
}

const dosyalar = []
;(function tara(d) {
  for (const ad of readdirSync(d)) {
    const y = join(d, ad)
    if (statSync(y).isDirectory()) tara(y)
    else if (ad.endsWith('.jsx')) dosyalar.push(y)
  }
})(KOK)

const bulgular = []
for (const dosya of dosyalar) {
  const metin = readFileSync(dosya, 'utf8')
  const satirlar = metin.split('\n')
  // Sınıf metni olabilecek her dizgi: "…" ve '…' ve `…` (koşullu sınıflar dahil)
  // Yorum satırlarını çıkar: kendi açıklamalarımda geçen sınıf adları
  // (örn. bu düzeltmeyi anlatan yorum) bulgu sayılmasın
  const temiz = metin
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, (m) => ' '.repeat(m.length))
    .replace(/\/\*[\s\S]*?\*\//g, (m) => ' '.repeat(m.length))
    .replace(/^[ \t]*\/\/.*$/gm, (m) => ' '.repeat(m.length))
  const dizgiler = [...temiz.matchAll(/(["'`])((?:[^\\\n]|\\.)*?)\1/g)]
  for (const d of dizgiler) {
    const govde = d[2]
    if (!/\b(bg|text)-/.test(govde)) continue
    const parcalar = govde.split(/[\s${}?:'"`]+/).filter(Boolean)
    const zemin = parcalar.map(coz.bind(null)).filter(Boolean)
    const zeminSinif = parcalar.find((c) => c.startsWith('bg-') && coz(c))
    const metinSinif = parcalar.find((c) => c.startsWith('text-') && coz(c))
    if (!zeminSinif) continue
    const zRenk = hex(coz(zeminSinif))
    if (!zRenk) continue
    const satirNo = metin.slice(0, d.index).split('\n').length
    // İÇİNDE YAZI OLMAYAN öğeyi atla: nokta, renk kutusu, iframe, ayraç…
    // Kendi kendini kapatan etiketin metin çocuğu olamaz, kontrast aranmaz.
    const kalan = metin.slice(d.index)
    const etiketSonu = kalan.indexOf('>')
    if (etiketSonu > 0 && kalan[etiketSonu - 1] === '/') continue
    const yer = `${dosya.replace(KOK + '/', '')}:${satirNo}`

    if (!metinSinif) {
      // Metin rengi yok → body'den beyaz miras alınır
      const oran = kontrast(zRenk, hex(MIRAS_METIN))
      if (oran < 3) bulgular.push({ yer, tur: 'MIRAS', zeminSinif, metinSinif: '(miras: beyaz)',
        oran, kod: satirlar[satirNo - 1].trim().slice(0, 90) })
    } else {
      const oran = kontrast(zRenk, hex(coz(metinSinif)))
      if (oran < 3) bulgular.push({ yer, tur: 'ACIK', zeminSinif, metinSinif,
        oran, kod: satirlar[satirNo - 1].trim().slice(0, 90) })
    }
  }
}

if (!bulgular.length) {
  console.log(`✓ ${dosyalar.length} dosya tarandı — kontrast sorunu yok`)
  process.exit(0)
}
console.log(`✗ ${bulgular.length} kontrast sorunu (${dosyalar.length} dosya tarandı)\n`)
for (const b of bulgular.sort((a, c) => a.oran - c.oran)) {
  console.log(`  ${b.yer}`)
  console.log(`    ${b.zeminSinif}  +  ${b.metinSinif}   → kontrast ${b.oran.toFixed(2)}:1  (en az 3.0 olmalı)`)
  console.log(`    ${b.kod}\n`)
}
process.exit(1)
