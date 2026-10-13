// Forma tasarlayıcıda kulüp/marka adı engeli — müşteriye ANINDA uyarı için.
// Asıl karar sunucuda verilir (backend/app/services/yasak_kelime.py); bu dosya
// onun KOPYASIDIR, listeyi değiştirirsen ikisini birlikte değiştir.
// Mağazanın panelden eklediği kelimeler buraya gelmez (vitrine sızdırılmaz);
// onlar yalnız kaydederken sunucuda yakalanır.

const TR: Record<string, string> = { ç: "c", ğ: "g", ı: "i", ö: "o", ş: "s", ü: "u", â: "a", î: "i", û: "u" };
const LEET: Record<string, string> = { "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b" };

const ICEREN = [
  "galatasaray", "fenerbahce", "besiktas", "trabzonspor", "basaksehir",
  "cimbom", "ultraslan", "carsi", "genclerbirligi", "bursaspor", "goztepe",
  "samsunspor", "konyaspor", "sivasspor", "kayserispor", "antalyaspor",
  "alanyaspor", "rizespor", "kasimpasa", "gaziantepfk", "hatayspor",
  "adanademirspor", "eyupspor", "kocaelispor", "sakaryaspor",
  "karsiyaka", "eskisehirspor", "ankaragucu",
  "realmadrid", "barcelona", "atleticomadrid", "manchesterunited", "manchestercity",
  "liverpool", "chelsea", "arsenal", "tottenham", "juventus", "acmilan", "intermilan",
  "internazionale", "bayernmunchen", "bayernmunich", "borussiadortmund",
  "parissaintgermain", "ajax", "benfica", "napoli",
  "fifa", "uefa", "superlig", "tff",
];
const TAM = ["gs", "fb", "bjk", "ts", "gfk", "psg", "fcb", "rma", "mufc", "mcfc", "lfc"];

export const YASAK_MESAJ =
  "Bu alana kulüp ya da marka adı yazılamaz — lisanssız üründe basamıyoruz. "
  + "Kendi adını, lakabını ya da numaranı yazabilirsin.";

function normalize(metin: string): string {
  const s = (metin || "").replace(/İ/g, "i").replace(/I/g, "i").toLowerCase()
    .replace(/[çğıöşüâîû]/g, (h) => TR[h] || h);
  return s.replace(/[^a-z0-9]+/g, "");
}

export function yasakMi(metin: string): boolean {
  const n = normalize(metin);
  if (!n) return false;
  if (TAM.includes(n)) return true;
  const leet = n.replace(/[0134578]/g, (h) => LEET[h] || h);
  return ICEREN.some((k) => n.includes(k) || leet.includes(k));
}
