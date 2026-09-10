import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import CrossEntry from "@/components/CrossEntry";
import { crossIndex, readPlace } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE, trim } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return (crossIndex().places ?? []).map((p) => ({ country: p.slug }));
}

function describe(p: NonNullable<ReturnType<typeof readPlace>>) {
  return trim(`${p.total.toLocaleString()} dated entries about ${p.label}, ${p.span[0]} to ${p.span[1]}, each one quoted from the Wikipedia revision it came from.`);
}

export async function generateMetadata({ params }: { params: Promise<{ country: string }> }) {
  const { country } = await params;
  const p = readPlace(country);
  if (!p) return { title: SITE.name };
  const title = `${p.label} — a timeline from ${p.span[0]} to ${p.span[1]}`;
  const description = describe(p);
  const url = canonical(`/in/${p.slug}`);
  return {
    title, description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "article" },
    twitter: { title, description },
  };
}

export default async function Place({ params }: { params: Promise<{ country: string }> }) {
  const { country } = await params;
  const p = readPlace(country);
  if (!p) notFound();

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: `${p.label} through history`,
          description: describe(p),
          url: canonical(`/in/${p.slug}`),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          about: { "@type": "Place", name: p.label },
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Countries", path: "/in" },
            { name: p.label, path: `/in/${p.slug}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">{p.label}</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {p.total.toLocaleString()} entries quoted from the Wikipedia articles written per year
          for {p.label}, {p.span[0]} to {p.span[1]}. Each century below shows a sample spread
          across it; the year link on a line opens everything held for that year.
        </p>

        {p.centuries.map((c) => (
          <section className="mb-10" key={c.slug}>
            <h2 className="mb-1 border-b border-border pb-2 text-lg font-medium text-foreground">
              <a className="hover:underline" href={`/century/${c.slug}`}>{c.label}</a>
            </h2>
            <p className="mb-4 text-xs text-muted-foreground">
              {c.count.toLocaleString()} {c.count === 1 ? "entry" : "entries"}, {c.span[0]} to {c.span[1]}
              {c.count > c.items.length && ` — ${c.items.length} shown, spread across the century`}
            </p>
            <ul className="flex flex-col gap-3">
              {c.items.map((item, k) => (
                <CrossEntry item={item} key={k} />
              ))}
            </ul>
          </section>
        ))}

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Which country a line is filed under is the article it was quoted from, not a claim about
          borders as they stood at the time. The sentence itself is English Wikipedia&rsquo;s,
          quoted at the revision linked beside it and reused under{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer nofollow">
            CC BY-SA 4.0
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
