import SiteNav from "@/components/SiteNav";
import { crossIndex } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE } from "@/lib/seo";

const title = "Centuries — the whole record, three clicks deep";
const description =
  "Every documented century, each opening onto its decades and then its individual years. The hierarchy that turns 2,960 year pages into something you can actually walk through.";

export const metadata = {
  title, description,
  alternates: { canonical: canonical("/century") },
  openGraph: { title, description, url: canonical("/century") },
};

export default function Centuries() {
  const { centuries } = crossIndex();
  const bce = centuries.filter((c) => c.key < 0);
  const ce = centuries.filter((c) => c.key > 0);
  const total = centuries.reduce((n, c) => n + c.entries, 0);

  const Group = ({ label, rows }: { label: string; rows: typeof centuries }) => (
    <section className="mb-10">
      <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">{label}</h2>
      <ul className="flex flex-col gap-2">
        {rows.map((c) => (
          <li className="text-sm text-foreground/85" key={c.slug}>
            <a className="underline underline-offset-2 hover:text-foreground" href={`/century/${c.slug}`}>
              The {c.label}
            </a>
            <span className="text-muted-foreground">
              {" "}— {c.years} documented {c.years === 1 ? "year" : "years"}, {c.entries.toLocaleString()} entries
            </span>
          </li>
        ))}
      </ul>
    </section>
  );

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: title, description, url: canonical("/century"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Centuries", path: "/century" },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Centuries</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {centuries.length} centuries hold {total.toLocaleString()} sourced entries. Open one to
          get its decades, and a decade to get its years. A century here runs 1900&ndash;1999
          rather than 1901&ndash;2000, so its decades sit inside it exactly.
        </p>
        {ce.length > 0 && <Group label="Common Era" rows={ce} />}
        {bce.length > 0 && <Group label="Before Common Era" rows={bce} />}
      </article>
    </main>
  );
}
