import Reveal from "@/components/Reveal";

// İkon şeridi (ShinePro icon-bar) — avantaj vurguları.
export default function IconBar({
  items = [],
}: {
  items?: { icon: string; title: string; text?: string }[];
}) {
  const valid = items.filter((i) => i.title);
  if (valid.length === 0) return null;
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <Reveal>
        <div className={`grid gap-3 grid-cols-2 ${valid.length >= 4 ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}>
          {valid.map((i, idx) => (
            <div key={idx}
              className="bg-white border border-zinc-200 rounded-2xl p-4 text-center">
              <div className="text-3xl">{i.icon || "✨"}</div>
              <div className="mt-2 text-sm font-semibold">{i.title}</div>
              {i.text && <div className="mt-1 text-xs text-zinc-500">{i.text}</div>}
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
