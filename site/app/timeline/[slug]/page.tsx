import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import { entityIndex, readEntity, type EntityPage } from "@/lib/entities";
import { readable } from "@/lib/display";
import { yearPath } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE, trim , OG_IMAGE } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return entityIndex().entities.map((e) => ({ slug: e.slug }));
}

function describe(p: EntityPage) {
  const what = p.description ? ` (${p.description})` : "";
  return trim(
    `Every dated event mentioning ${p.label}${what} in the year-by-year record: ` +
      `${p.entries.toLocaleString()} entries across ${p.years.toLocaleString()} years, ` +
      `${p.span_label[0]} to ${p.span_label[1]}, each quoted from the Wikipedia revision it came from.`,
  );
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const p = readEntity(slug);
  if (!p) return { title: SITE.name };
  const title = `${p.label} — timeline of ${p.entries.toLocaleString()} sourced events`;
  const description = describe(p);
  const url = canonical(`/timeline/${p.slug}`);
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, images: OG_IMAGE, url, type: "article" },
    twitter: { card: "summary_large_image", title, description, images: OG_IMAGE },
  };
}

export default async function Timeline({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const p = readEntity(slug);
  if (!p) notFound();

  // One heading per century, so a 400-entry page reads as a timeline and not a wall.
  const groups: { label: string; items: typeof p.items }[] = [];
  for (const it of p.items) {
    const bce = it.year <= 0;
    const n = bce ? Math.abs(it.year) + 1 : it.year;
    const c = Math.floor((n - 1) / 100) + 1;
    const suffix =
      c % 100 >= 11 && c % 100 <= 13 ? "th" : (["th", "st", "nd", "rd"][c % 10] ?? "th");
    const label = `${c}${suffix} century${bce ? " BC" : ""}`;
    if (!groups.length || groups[groups.length - 1].label !== label)
      groups.push({ label, items: [] });
    groups[groups.length - 1].items.push(it);
  }

  const sameAs = [p.wikipedia, ...(p.wikidata ? [p.wikidata] : [])];

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: `${p.label} — timeline`,
          description: describe(p),
          url: canonical(`/timeline/${p.slug}`),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          about: {
            "@type": "Thing",
            name: p.label,
            ...(p.description ? { description: p.description } : {}),
            ...(p.qid ? { identifier: p.qid } : {}),
            sameAs,
          },
          mainEntity: {
            "@type": "ItemList",
            // The list encodes a 40-row sample of a timeline that can run to hundreds, so
            // the count has to be the number of rows actually encoded, not p.entries.
            numberOfItems: Math.min(p.items.length, 40),
            itemListElement: p.items.slice(0, 40).map((it, i) => ({
              "@type": "ListItem",
              position: i + 1,
              item: {
                "@type": "Event",
                name: trim(it.text, 110),
                startDate: it.year > 0 ? String(it.year).padStart(4, "0") : undefined,
                url: canonical(yearPath(it.year)),
              },
            })),
          },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Timelines", path: "/timeline" },
            { name: p.label, path: `/timeline/${p.slug}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-2 text-3xl font-normal text-foreground md:text-4xl">{p.label}</h1>
        {p.description && (
          <p className="mb-4 text-sm text-muted-foreground">{p.description}</p>
        )}
        <p className="mb-6 text-sm leading-relaxed text-muted-foreground">
          {p.entries.toLocaleString()} dated entries naming {p.label}, drawn from{" "}
          {p.years.toLocaleString()} separate years between {p.span_label[0]} and{" "}
          {p.span_label[1]}. Nothing here is written by us: each line is the sentence a
          Wikipedia year article used, and the link beside it opens the exact revision.
        </p>

        {p.also_known_as && p.also_known_as.length > 0 && (
          <p className="mb-6 text-sm leading-relaxed text-muted-foreground">
            Also written as {p.also_known_as.slice(0, 8).join(", ")} in the source
            articles; Wikipedia redirects those to the same subject, so their entries are
            on this page.
          </p>
        )}

        <p className="mb-10 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <a className="underline underline-offset-2 hover:text-foreground" href={`/api/entity/${p.slug}.json`}>
            JSON
          </a>
          <a className="underline underline-offset-2 hover:text-foreground" href={p.wikipedia} target="_blank" rel="noreferrer nofollow">
            Wikipedia article
          </a>
          {p.wikidata && (
            <a className="underline underline-offset-2 hover:text-foreground" href={p.wikidata} target="_blank" rel="noreferrer nofollow">
              Wikidata {p.qid}
            </a>
          )}
        </p>

        {groups.map((g) => (
          <section className="mb-10" key={g.label}>
            <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
              {g.label}
            </h2>
            <ul className="flex flex-col gap-3">
              {g.items.map((it, k) => (
                <li className="text-sm leading-relaxed text-foreground/85" key={k}>
                  <a
                    className="mr-2 tabular-nums text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground hover:decoration-solid"
                    href={yearPath(it.year)}
                  >
                    {it.year_label.replace(/ CE$/, "")}
                  </a>
                  {readable(it.text)}
                  <a
                    href={it.cite.url}
                    target="_blank"
                    rel="noreferrer nofollow"
                    title={`${it.cite.title} — ${it.cite.section} (revision ${it.cite.revid})`}
                    className="ml-1 align-super text-[10px] text-muted-foreground hover:text-foreground hover:underline"
                  >
                    source
                  </a>
                </li>
              ))}
            </ul>
          </section>
        ))}

        {p.related.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
              Named in the same entries
            </h2>
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-foreground/85">
              {p.related.map((r) => (
                <li key={r.slug}>
                  <a className="underline underline-offset-2 hover:text-foreground" href={`/timeline/${r.slug}`}>
                    {r.label}
                  </a>
                  <span className="text-muted-foreground"> ({r.shared})</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Which entries name {p.label} is Wikipedia&rsquo;s own editorial link, read out of the
          wikitext of the year articles; the sentences are English Wikipedia&rsquo;s, quoted at
          the revision linked beside each one and reused under{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer nofollow">
            CC BY-SA 4.0
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
