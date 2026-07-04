import Reveal from "@/components/Reveal";

// Banner bölümü — tıklanabilir geniş görsel.
export default function Banner({ image, url }: { image?: string | null; url?: string }) {
  if (!image) return null;
  const img = (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={image} alt="" className="w-full rounded-3xl object-cover max-h-80" />
  );
  return (
    <section className="mx-auto max-w-6xl px-4 py-6">
      <Reveal>{url ? <a href={url}>{img}</a> : img}</Reveal>
    </section>
  );
}
