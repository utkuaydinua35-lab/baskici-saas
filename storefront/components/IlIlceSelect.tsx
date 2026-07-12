"use client";

// İl + ilçe dropdown çifti — elle yazım hatası yerine listeden seçim.
// Liste yüklenemezse metin girişine düşer (form asla kilitlenmez).
import { useEffect, useState } from "react";

const inputCls =
  "w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white " +
  "focus:outline-none focus:ring-2 focus:ring-zinc-900/10 focus:border-zinc-900";

export default function IlIlceSelect({
  defaultIl = "",
  defaultIlce = "",
}: {
  defaultIl?: string;
  defaultIlce?: string;
}) {
  const [data, setData] = useState<Record<string, string[]> | null>(null);
  const [il, setIl] = useState(defaultIl);
  const [ilce, setIlce] = useState(defaultIlce);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/api/il-ilce")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && Object.keys(d).length > 0) setData(d);
        else setFailed(true);
      })
      .catch(() => setFailed(true));
  }, []);

  // prefill güncellenirse (girişli müşteri verisi sonradan gelir) eşitle
  useEffect(() => { if (defaultIl) setIl(defaultIl); }, [defaultIl]);
  useEffect(() => { if (defaultIlce) setIlce(defaultIlce); }, [defaultIlce]);

  if (failed || !data) {
    // Yükleniyor/başarısız: mevcut davranış (metin girişi) — kayıpsız geriye dönüş
    return (
      <>
        <label className="block text-sm">
          <span className="text-zinc-500 text-xs">İl *</span>
          <input name="city" required autoComplete="address-level1"
            defaultValue={defaultIl} className={`${inputCls} mt-1`} />
        </label>
        <label className="block text-sm">
          <span className="text-zinc-500 text-xs">İlçe</span>
          <input name="province" autoComplete="address-level2"
            defaultValue={defaultIlce} className={`${inputCls} mt-1`} />
        </label>
      </>
    );
  }

  const iller = Object.keys(data);
  // Kayıtlı il listedekiyle birebir eşleşmiyorsa (örn. "kütahya") normalize et
  const ilKey = iller.find((x) => x.toLocaleLowerCase("tr") === il.toLocaleLowerCase("tr")) || "";
  const ilceler = ilKey ? data[ilKey] : [];

  return (
    <>
      <label className="block text-sm">
        <span className="text-zinc-500 text-xs">İl *</span>
        <select name="city" required value={ilKey}
          onChange={(e) => { setIl(e.target.value); setIlce(""); }}
          className={`${inputCls} mt-1`}>
          <option value="">İl seçin…</option>
          {iller.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      </label>
      <label className="block text-sm">
        <span className="text-zinc-500 text-xs">İlçe *</span>
        <select name="province" required value={
          ilceler.find((x) => x.toLocaleLowerCase("tr") === ilce.toLocaleLowerCase("tr")) || ""}
          onChange={(e) => setIlce(e.target.value)}
          disabled={!ilKey}
          className={`${inputCls} mt-1 disabled:opacity-50`}>
          <option value="">{ilKey ? "İlçe seçin…" : "Önce il seçin"}</option>
          {ilceler.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      </label>
    </>
  );
}
