import Reveal from "@/components/Reveal";

// Serbest metin bölümü — düz metin, satır sonları korunur (HTML render edilmez).
export default function RichText({ title, body }: { title?: string; body?: string }) {
  if (!title && !body) return null;
  return (
    <section className="mx-auto max-w-3xl px-4 py-10 text-center">
      <Reveal>
        {title && <h2 className="text-2xl font-bold">{title}</h2>}
        {body && (
          <p className="mt-3 text-zinc-600 leading-relaxed whitespace-pre-line">{body}</p>
        )}
      </Reveal>
    </section>
  );
}
