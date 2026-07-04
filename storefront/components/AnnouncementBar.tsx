// Duyuru şeridi — tema ayarından (announcement.enabled) gelir.
export default function AnnouncementBar({
  text,
  url,
}: {
  text: string;
  url?: string;
}) {
  if (!text) return null;
  const inner = <span className="text-xs font-medium tracking-wide">{text}</span>;
  return (
    <div
      className="text-center py-2 px-4 text-white"
      style={{ background: "var(--c-primary)" }}
    >
      {url ? (
        <a href={url} className="hover:underline">{inner}</a>
      ) : (
        inner
      )}
    </div>
  );
}
