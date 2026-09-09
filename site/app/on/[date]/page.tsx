import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import { readDate, readDateIndex } from "@/lib/dates";
import { breadcrumb, canonical, JsonLd, SITE, trim } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return readDateIndex().dates.map((d) => ({ date: d.slug }));
}

/** A year page is a near-copy of the Wikipedia article of the same name. A date page is
 *  not a copy of anything: no single article holds everything recorded on 7 September
 *  across 2,960 years. So the description is built from the page's own oldest entry
 *  rather than from a template — it is the one thing here no other page can say. */
function describe(page: NonNullable<ReturnType<typeof readDate>>) {
  const first = page.groups[0]?.items[0];
  const head = `${page.label} in history: ${page.count} sourced entries`;
  const span = page.span ? ` from ${page.span[0]} to ${page.span[1]}` : "";
  return trim(first ? `${head}${span}. ${first.year_label} — ${first.text}` : head + span);
}

export async function generateMetadata({ params }: { params: Promise<{ date: string }> }) {
  const { date } = await params;
  const page = readDate(date);
  if (!page) return { title: SITE.name };
  const title = `${page.label} in history — events, births and deaths`;
  const description = describe(page);
  const url = canonical(`/on/${page.slug}`);
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "article" },
    twitter: { title, description },
  };
}

export default async function DatePage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = await params;
  const page = readDate(date);
  if (!page) notFound();

  const all = readDateIndex().dates;
  const i = all.findIndex((d) => d.slug === page.slug);
  const prev = all[(i - 1 + all.length) % all.length];
  const next = all[(i + 1) % all.length];

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: `${page.label} in history`,
          description: describe(page),
          url: canonical(`/on/${page.slug}`),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          about: { "@type": "Thing", name: page.label },
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "On this day", path: "/on" },
            { name: page.label, path: `/on/${page.slug}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">{page.label} in history</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {page.count > 0 ? (
            <>
              {page.count} sourced entries recorded on {page.label}, from {page.span![0]} to{" "}
              {page.span![1]}. Every line is quoted from the revision it came from.
            </>
          ) : (
            <>No sourced entries are filed under {page.label} yet.</>
          )}
        </p>

        {page.groups.map((group) => (
          <section className="mb-10" key={group.title}>
            <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
              {group.title}
            </h2>
            <ul className="flex flex-col gap-3">
              {group.items.map((item, k) => (
                <li className="text-sm leading-relaxed text-foreground/85" key={k}>
                  <a
                    className="mr-2 tabular-nums text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground hover:decoration-solid"
                    href={item.year === 404 ? "/404/" : `/${item.year}`}
                  >
                    {item.year_label.replace(/ CE$/, "")}
                  </a>
                  {item.text}
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
              ))}
            </ul>
          </section>
        ))}

        <nav className="mb-10 flex justify-between text-sm" aria-label="Nearby dates">
          <a className="underline underline-offset-2 hover:text-foreground" href={`/on/${prev.slug}`}>
            ← {prev.label}
          </a>
          <a className="underline underline-offset-2 hover:text-foreground" href={`/on/${next.slug}`}>
            {next.label} →
          </a>
        </nav>

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Each entry above is quoted from English Wikipedia&rsquo;s article for the year it sits
          under, at the exact revision linked beside it, and re-filed here by the day it happened
          on. Nothing is written by us and nothing is generated. Text is reused under{" "}
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
