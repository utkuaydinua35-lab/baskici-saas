import NewsletterForm from "@/components/NewsletterForm";
import Reveal from "@/components/Reveal";

// Bülten kayıt bölümü — footer'daki formun anasayfa versiyonu.
export default function NewsletterSection({
  title,
  subtitle,
}: {
  title?: string;
  subtitle?: string;
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <Reveal>
        <div className="bg-white border border-zinc-200 rounded-2xl px-6 py-10 text-center">
          <h2 className="text-xl font-bold">{title || "Kampanyalardan haberdar olun"}</h2>
          {subtitle && <p className="mt-2 text-sm text-zinc-500">{subtitle}</p>}
          <div className="mt-6 max-w-sm mx-auto text-left">
            <NewsletterForm />
          </div>
        </div>
      </Reveal>
    </section>
  );
}
