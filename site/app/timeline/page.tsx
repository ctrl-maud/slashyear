import SiteNav from "@/components/SiteNav";
import { entityIndex } from "@/lib/entities";
import { breadcrumb, canonical, JsonLd, SITE } from "@/lib/seo";

const title = "Timelines — every subject the record names, in date order";
const description =
  "One timeline per subject: every dated entry in the year-by-year record that names it, sourced line by line. A shape no single encyclopedia article publishes.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/timeline") },
  openGraph: { title, description, url: canonical("/timeline") },
};

export default function Timelines() {
  const { entities } = entityIndex();
  const top = entities.slice(0, 60);
  const byLetter = new Map<string, typeof entities>();
  for (const e of [...entities].sort((a, b) => a.label.localeCompare(b.label))) {
    const c = /^[A-Za-z]/.test(e.label) ? e.label[0].toUpperCase() : "#";
    if (!byLetter.has(c)) byLetter.set(c, []);
    byLetter.get(c)!.push(e);
  }

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: "Timelines",
          description,
          url: canonical("/timeline"),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Timelines", path: "/timeline" },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Timelines</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {entities.length.toLocaleString()} subjects, each with every dated entry in the record
          that names it, in order. The association is Wikipedia&rsquo;s own link in the wikitext of
          the year article, not a guess of ours, and every line keeps the revision it was quoted
          from. Most of these subjects have an encyclopedia article about them; almost none of
          them have this.
        </p>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            The longest records
          </h2>
          <ul className="flex flex-col gap-2">
            {top.map((e) => (
              <li className="text-sm text-foreground/85" key={e.slug}>
                <a className="underline underline-offset-2 hover:text-foreground" href={`/timeline/${e.slug}`}>
                  {e.label}
                </a>
                <span className="text-muted-foreground">
                  {" "}
                  — {e.entries.toLocaleString()} entries, {e.span_label[0]} to {e.span_label[1]}
                </span>
              </li>
            ))}
          </ul>
        </section>

        {[...byLetter.entries()].map(([letter, rows]) => (
          <section className="mb-8" key={letter}>
            <h2 className="mb-3 border-b border-border pb-2 text-lg font-medium text-foreground">
              {letter}
            </h2>
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-foreground/85">
              {rows.map((e) => (
                <li key={e.slug}>
                  <a className="underline underline-offset-2 hover:text-foreground" href={`/timeline/${e.slug}`}>
                    {e.label}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        ))}

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Every timeline is also a JSON file at <code>/api/entity/&lt;slug&gt;.json</code>, and the
          whole set is listed at <code>/api/entities.json</code>. Sentences are English
          Wikipedia&rsquo;s, reused under{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer nofollow">
            CC BY-SA 4.0
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
