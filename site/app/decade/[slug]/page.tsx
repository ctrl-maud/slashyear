import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import { crossIndex, readDecade, yearPath } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE, trim } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return crossIndex().decades.map((d) => ({ slug: d.slug }));
}

function describe(p: NonNullable<ReturnType<typeof readDecade>>) {
  const first = p.years.find((y) => y.lead_items.length)?.lead_items[0];
  const head = `The ${p.label}: ${p.entries.toLocaleString()} sourced entries across ${p.years.length} years`;
  return trim(first ? `${head}. ${first}` : head);
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const p = readDecade(slug);
  if (!p) return { title: SITE.name };
  const title = `The ${p.label} — every year, event, birth and death`;
  const description = describe(p);
  const url = canonical(`/decade/${p.slug}`);
  return {
    title, description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "article" },
    twitter: { title, description },
  };
}

export default async function Decade({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const p = readDecade(slug);
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
          name: `The ${p.label}`,
          description: describe(p),
          url: canonical(`/decade/${p.slug}`),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            ...(p.century ? [{ name: p.century.label, path: `/century/${p.century.slug}` }] : []),
            { name: p.label, path: `/decade/${p.slug}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">The {p.label}</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {p.entries.toLocaleString()} sourced entries across {p.years.length}{" "}
          {p.years.length === 1 ? "year" : "years"}
          {p.century && (
            <>
              , inside the{" "}
              <a className="underline underline-offset-2 hover:text-foreground" href={`/century/${p.century.slug}`}>
                {p.century.label}
              </a>
            </>
          )}
          . Each year below opens its own page; the lines under it are that year&rsquo;s
          highest-ranked entries.
        </p>

        {p.years.map((y) => (
          <section className="mb-8" key={y.year}>
            <h2 className="mb-3 border-b border-border pb-2 text-lg font-medium text-foreground">
              <a className="underline-offset-2 hover:underline" href={yearPath(y.year)}>
                {y.label}
              </a>
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                {y.entries} entries
              </span>
            </h2>
            {y.lead_items.length > 0 && (
              <ul className="flex flex-col gap-2">
                {y.lead_items.map((t, k) => (
                  <li className="text-sm leading-relaxed text-foreground/85" key={k}>
                    {t}
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}

        <nav className="mb-10 mt-10 flex justify-between text-sm" aria-label="Nearby decades">
          {p.prev ? (
            <a className="underline underline-offset-2 hover:text-foreground" href={`/decade/${p.prev.slug}`}>
              ← {p.prev.label}
            </a>
          ) : <span />}
          {p.next ? (
            <a className="underline underline-offset-2 hover:text-foreground" href={`/decade/${p.next.slug}`}>
              {p.next.label} →
            </a>
          ) : <span />}
        </nav>

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Every sentence on this page is quoted from English Wikipedia&rsquo;s article for the year
          it sits under, at the revision linked on that year&rsquo;s own page. Nothing here is
          written by us. Text is reused under{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer nofollow">
            CC BY-SA 4.0
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
