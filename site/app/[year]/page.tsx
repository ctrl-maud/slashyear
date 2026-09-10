import { notFound } from "next/navigation";
import YearNav from "@/components/YearNav";
import { allYears, readYear, type Item } from "@/lib/data";
import { readable } from "@/lib/display";
import { dateHref } from "@/lib/dates";
import { hasPlace, hasTopicCentury, placeSlug, yearParents } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE, trim } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return allYears().map((y) => ({ year: String(y) }));
}

/** /404 is the one page whose canonical URL keeps its trailing slash: the bare
 *  404.html has to stay the not-found page, so the year 404 CE lives in a directory. */
const pathOf = (year: number) => (year === 404 ? "/404/" : `/${year}`);

export async function generateMetadata({ params }: { params: Promise<{ year: string }> }) {
  const { year } = await params;
  const page = readYear(year);
  if (!page) return { title: SITE.name };
  const title = `${page.label} — events, births and deaths`;
  const description = trim(page.lead);
  const url = canonical(pathOf(page.year));
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "article" },
    twitter: { title, description },
  };
}

/** The source prints the day at the head of the sentence ("January 5 – Edward…").
 *  Turning that prefix into a link to the day's own page costs the reader nothing —
 *  the visible words are unchanged — and it is what wires 2,960 year pages to 366
 *  date pages in both directions. */
function Entry({ item }: { item: Item }) {
  const href = dateHref(item.date);
  const body =
    href && item.date && item.text.startsWith(item.date) ? (
      <>
        <a className="underline decoration-dotted underline-offset-2 hover:decoration-solid" href={href}>
          {item.date}
        </a>
        {readable(item.text.slice(item.date.length))}
      </>
    ) : (
      readable(item.text)
    );
  return (
    <li className="text-sm leading-relaxed text-foreground/85">
      {body}
      {item.country && hasPlace(item.country) && (
        <a
          className="ml-1 whitespace-nowrap rounded-sm border border-border px-1 text-[10px] text-muted-foreground hover:text-foreground"
          href={`/in/${placeSlug(item.country)}`}
        >
          {item.country}
        </a>
      )}
      <a
        href={item.cite.url}
        target="_blank"
        rel="noreferrer nofollow"
        title={`${item.cite.title} — ${item.cite.section} (revision ${item.cite.revid})`}
        className="ml-1 align-super text-[10px] text-muted-foreground hover:text-foreground hover:underline"
      >
        source
      </a>
    </li>
  );
}

/** A section heading is a link to that subject across the whole century — but only when
 *  the pipeline actually wrote that page, since thin subject-centuries are dropped. */
function topicHref(section: string, century?: string): string | null {
  if (!century) return null;
  const slug = section.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return hasTopicCentury(slug, century) ? `/topic/${slug}/${century}` : null;
}

function decadeOf(year: number) {
  const start = Math.floor(year / 10) * 10;
  return { start, end: start + 9 };
}

function label(year: number) {
  return year > 0 ? `${year}` : `${Math.abs(year) + 1} BCE`;
}

export default async function YearPage({ params }: { params: Promise<{ year: string }> }) {
  const { year } = await params;
  const page = readYear(year);
  if (!page) notFound();

  const years = allYears();
  const i = years.indexOf(page.year);
  const prev = i > 0 ? years[i - 1] : null;
  const next = i >= 0 && i < years.length - 1 ? years[i + 1] : null;
  const { start, end } = decadeOf(page.year);
  const parents = yearParents(page.year);
  const decade = years.filter((y) => y >= start && y <= end);
  const days = Array.from(
    new Set(
      page.sections
        .flatMap((s) => s.items)
        .map((it) => (dateHref(it.date) ? it.date! : null))
        .filter((d): d is string => d !== null),
    ),
  );

  return (
    <main className="min-h-screen">
      <YearNav value={year} />
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: `${page.label} — events, births and deaths`,
          headline: page.label,
          description: trim(page.lead),
          url: canonical(pathOf(page.year)),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          about: { "@type": "Thing", name: page.label },
          dateModified: page.source.retrieved,
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          isBasedOn: {
            "@type": "Article",
            name: page.source.title,
            url: page.source.permalink,
            publisher: { "@type": "Organization", name: "Wikipedia" },
          },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            ...(parents.century ? [{ name: parents.century.label, path: `/century/${parents.century.slug}` }] : []),
            ...(parents.decade ? [{ name: `The ${parents.decade.label}`, path: `/decade/${parents.decade.slug}` }] : []),
            { name: page.label, path: pathOf(page.year) },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">{page.label}</h1>
        <p className="mb-6 text-sm leading-relaxed text-muted-foreground">{page.lead}</p>
        {(parents.decade || parents.century) && (
          <p className="mb-10 text-sm text-muted-foreground">
            In{" "}
            {parents.decade && (
              <a className="underline underline-offset-2 hover:text-foreground" href={`/decade/${parents.decade.slug}`}>
                the {parents.decade.label}
              </a>
            )}
            {parents.decade && parents.century && ", "}
            {parents.century && (
              <a className="underline underline-offset-2 hover:text-foreground" href={`/century/${parents.century.slug}`}>
                the {parents.century.label}
              </a>
            )}
            .
          </p>
        )}

        {page.sections.map((section) => (
          <section className="mb-10" key={section.title}>
            <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
              {topicHref(section.title, parents.century?.slug) ? (
                <a
                  className="underline-offset-2 hover:underline"
                  href={topicHref(section.title, parents.century?.slug)!}
                  title={`${section.title} across the whole ${parents.century!.label}`}
                >
                  {section.title}
                </a>
              ) : (
                section.title
              )}
            </h2>
            <ul className="flex flex-col gap-3">
              {section.items.map((item, k) => (
                <Entry item={item} key={k} />
              ))}
            </ul>
          </section>
        ))}

        <nav className="mb-10" aria-label="Nearby">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            Nearby
          </h2>
          <div className="mb-4 flex justify-between text-sm">
            {prev ? (
              <a className="underline underline-offset-2 hover:text-foreground" href={pathOf(prev)}>
                ← {label(prev)}
              </a>
            ) : (
              <span />
            )}
            {next ? (
              <a className="underline underline-offset-2 hover:text-foreground" href={pathOf(next)}>
                {label(next)} →
              </a>
            ) : (
              <span />
            )}
          </div>
          {decade.length > 1 && (
            <>
              <h3 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
                {label(start)}–{label(end)}
              </h3>
              <ul className="mb-4 flex flex-wrap gap-x-3 gap-y-1">
                {decade.map((y) => (
                  <li key={y}>
                    {y === page.year ? (
                      <span className="text-sm text-muted-foreground">{label(y)}</span>
                    ) : (
                      <a
                        className="text-sm text-foreground/85 underline-offset-2 hover:text-foreground hover:underline"
                        href={pathOf(y)}
                      >
                        {label(y)}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
          {days.length > 0 && (
            <>
              <h3 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
                Days named on this page
              </h3>
              <ul className="flex flex-wrap gap-x-3 gap-y-1">
                {days.map((d) => (
                  <li key={d}>
                    <a
                      className="text-sm text-foreground/85 underline-offset-2 hover:text-foreground hover:underline"
                      href={dateHref(d)!}
                    >
                      {d}
                    </a>
                  </li>
                ))}
              </ul>
            </>
          )}
        </nav>

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          {page.counts.shown} of {page.counts.available} sourced entries shown. Every line above is
          quoted from the revision linked beside it, which is{" "}
          <a
            className="underline underline-offset-2 hover:text-foreground"
            href={page.source.permalink}
            target="_blank"
            rel="noreferrer nofollow"
          >
            {page.source.title}
          </a>{" "}
          on English Wikipedia, revision {page.source.revid}, retrieved {page.source.retrieved}
          {page.extra_sources && page.extra_sources.length > 0 && (
            <>
              , and from{" "}
              {page.extra_sources.map((s, i) => (
                <span key={s.revid}>{i === 0 ? "" : i === page.extra_sources!.length - 1 ? " and " : ", "}<a className="underline underline-offset-2 hover:text-foreground" href={s.permalink} target="_blank" rel="noreferrer nofollow">{s.title}</a>{` (revision ${s.revid})`}</span>
              ))}
            </>
          )}
          .
          Nothing on this page is written by us and nothing is generated: the sentences are the
          source&rsquo;s own, so a claim you doubt can be checked against the exact revision it came
          from. Text is reused under{" "}
          <a
            className="underline underline-offset-2 hover:text-foreground"
            href="https://creativecommons.org/licenses/by-sa/4.0/"
            target="_blank"
            rel="noreferrer nofollow"
          >
            CC BY-SA 4.0
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
