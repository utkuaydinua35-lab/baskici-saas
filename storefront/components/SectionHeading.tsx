import Link from "next/link";

// Bölüm başlığı üçlüsü — üst etiket / başlık / alt başlık. Görünümü tema
// seçer (html[data-heading]): compact'ta solda küçük başlık + sağda link,
// showcase'te ortalı büyük başlık; link o zaman SectionFooterLink ile
// şeridin altına iner. Boş alanlar hiç basılmaz.
export default function SectionHeading({
  eyebrow,
  title,
  subtitle,
  href,
  linkText = "Tümünü gör →",
  center = false,
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  href?: string;
  linkText?: string;
  // compact stilde de ortala (galeri/yorumlar eskiden hep ortalıydı)
  center?: boolean;
}) {
  if (!eyebrow && !title && !subtitle) return null;
  return (
    <div className={`bolum-baslik${center ? " bb-orta" : ""}`}>
      <div>
        {eyebrow ? <p className="bb-ust">{eyebrow}</p> : null}
        {title ? <h2 className="bb-baslik">{title}</h2> : null}
        {subtitle ? <p className="bb-alt">{subtitle}</p> : null}
      </div>
      {href ? <Link href={href} className="bb-link">{linkText}</Link> : null}
    </div>
  );
}

// Showcase başlık stilinde "Tümünü görüntüle" düğmesi şeridin altında durur;
// compact stilde CSS gizler (link zaten başlığın sağında).
export function SectionFooterLink({ href, text = "Tümünü görüntüle" }: { href: string; text?: string }) {
  return (
    <div className="bb-alt-link">
      <Link href={href}
        className="btn-r border border-zinc-900 px-7 py-2.5 text-sm font-semibold hover:bg-zinc-900 hover:text-white transition">
        {text}
      </Link>
    </div>
  );
}
