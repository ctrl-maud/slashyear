import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import { crossIndex, readCentury } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE, trim , OG_IMAGE } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return crossIndex().centuries.map((c) => ({ slug: c.slug }));
}

function describe(p: NonNullable<ReturnType<typeof readCentury>>) {
  const head = `The ${p.label}: ${p.entries.toLocaleString()} sourced entries across ${p.years} documented years`;
  const first = p.highlights[0];
  return trim(first ? `${head}. ${first.label} — ${first.text}` : head);
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const p = readCentury(slug);
  if (!p) return { title: SITE.name };
  const title = `The ${p.label} — decades, years and what was recorded`;
  const description = describe(p);
  const url = canonical(`/century/${p.slug}`);
  return {
    title, description,
    alternates: { canonical: url },
    openGraph: { title, description, images: OG_IMAGE, url, type: "article" },
    twitter: { card: "summary_large_image", title, description, images: OG_IMAGE },
  };
}

export default async function Century({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const p = readCentury(slug);
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
          url: canonical(`/century/${p.slug}`),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Centuries", path: "/century" },
            { name: p.label, path: `/century/${p.slug}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">The {p.label}</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {p.entries.toLocaleString()} sourced entries across {p.years} documented years, grouped
          into {p.decades.length} {p.decades.length === 1 ? "decade" : "decades"}. A century here
          runs 1900&ndash;1999 rather than 1901&ndash;2000, so its decades sit inside it exactly; on
          the BC side the same rule puts 1&ndash;99 BC in the 1st century BC and 100 BC in the 2nd.
        </p>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            Decades
          </h2>
          <ul className="flex flex-col gap-2">
            {p.decades.map((d) => (
              <li className="text-sm text-foreground/85" key={d.slug}>
                <a className="underline underline-offset-2 hover:text-foreground" href={`/decade/${d.slug}`}>
                  The {d.label}
                </a>
                <span className="text-muted-foreground">
                  {" "}— {d.years} {d.years === 1 ? "year" : "years"}, {d.entries.toLocaleString()} entries
                </span>
              </li>
            ))}
          </ul>
        </section>

        {p.topics.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
              By subject
            </h2>
            <ul className="flex flex-col gap-2">
              {p.topics.map((t) => (
                <li className="text-sm text-foreground/85" key={t.slug}>
                  <a className="underline underline-offset-2 hover:text-foreground" href={`/topic/${t.slug}/${p.slug}`}>
                    {t.label} in the {p.label}
                  </a>
                  <span className="text-muted-foreground"> — {t.count.toLocaleString()} entries</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {p.highlights.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
              A few of the years
            </h2>
            <ul className="flex flex-col gap-3">
              {p.highlights.map((h) => (
                <li className="text-sm leading-relaxed text-foreground/85" key={h.year}>
                  <a
                    className="mr-2 tabular-nums text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground hover:decoration-solid"
                    href={h.year === 404 ? "/404/" : `/${h.year}`}
                  >
                    {h.label.replace(/ CE$/, "")}
                  </a>
                  {h.text}
                </li>
              ))}
            </ul>
          </section>
        )}

        <nav className="mb-10 flex justify-between text-sm" aria-label="Nearby centuries">
          {p.prev ? (
            <a className="underline underline-offset-2 hover:text-foreground" href={`/century/${p.prev.slug}`}>
              ← {p.prev.label}
            </a>
          ) : <span />}
          {p.next ? (
            <a className="underline underline-offset-2 hover:text-foreground" href={`/century/${p.next.slug}`}>
              {p.next.label} →
            </a>
          ) : <span />}
        </nav>

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Counts and groupings are ours; every sentence is English Wikipedia&rsquo;s, quoted at the
          revision linked on the year page it came from, reused under{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer nofollow">
            CC BY-SA 4.0
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
