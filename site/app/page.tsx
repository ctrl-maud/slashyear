import SiteNav from "@/components/SiteNav";
import Today from "@/components/Today";
import { readIndex, type IndexRow } from "@/lib/data";
import { canonical, JsonLd, SITE } from "@/lib/seo";
import { crossIndex } from "@/lib/cross";

/** "20th century" / "5th century BC" for the year an entry belongs to. Site URLs use
 *  astronomical numbering, so -43 is 44 BCE and belongs to the 1st century BC. */
function centuryOf(year: number): { key: number; label: string } {
  const bce = year <= 0;
  const n = bce ? Math.abs(year) + 1 : year;
  const c = Math.floor((n - 1) / 100) + 1;
  const suffix =
    c % 100 >= 11 && c % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][c % 10] ?? "th";
  return { key: bce ? -c : c, label: `${c}${suffix} century${bce ? " BC" : ""}` };
}

function groupByCentury(rows: IndexRow[]) {
  const out: { label: string; rows: IndexRow[] }[] = [];
  for (const r of rows) {
    const { label } = centuryOf(r.year);
    if (!out.length || out[out.length - 1].label !== label) out.push({ label, rows: [] });
    out[out.length - 1].rows.push(r);
  }
  return out;
}

const title = "slashyear — every recorded year, every line sourced";
const description =
  "A directory of 2,960 documented years. Every entry is a sentence quoted from a specific Wikipedia revision you can open and check.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/") },
  openGraph: { title, description, url: canonical("/") },
};

export default function Directory() {
  const { years, total, span } = readIndex();
  // A century heading is only a link when cross.py actually wrote that page.
  const built = new Map(crossIndex().centuries.map((c) => [c.label, c.slug]));
  const ce = groupByCentury(years.filter((r) => r.year > 0));
  const bce = groupByCentury(years.filter((r) => r.year <= 0));

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: "Every recorded year",
          description: SITE.blurb,
          url: canonical("/"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Directory</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {total.toLocaleString()} documented years, from {span[0]} to {span[1]}. Every entry is
          quoted from a cited source revision. The same entries also read{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="/on">
            by calendar date
          </a>
          ,{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="/topic">
            by subject
          </a>{" "}
          and{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="/century">
            century by century
          </a>
          .
        </p>

        <Today />

        {[
          ["CE", ce],
          ["BCE", bce],
        ].map(([heading, groups]) => (
          <section className="mb-10" key={heading as string}>
            <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
              {heading as string}
            </h2>
            {(groups as { label: string; rows: IndexRow[] }[]).map((g) => (
              <div className="mb-6" key={g.label}>
                <h3 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
                  {built.has(g.label) ? (
                    <a className="underline-offset-2 hover:text-foreground hover:underline" href={`/century/${built.get(g.label)}`}>
                      {g.label}
                    </a>
                  ) : (
                    g.label
                  )}
                </h3>
                <ul className="flex flex-wrap gap-x-3 gap-y-1">
                  {g.rows.map((r) => (
                    <li key={r.year}>
                      <a
                        className="text-sm leading-relaxed text-foreground/85 underline-offset-2 hover:text-foreground hover:underline"
                        href={`/${r.year}`}
                      >
                        {r.label.replace(/ (CE|BCE)$/, "")}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
        ))}
      </article>
    </main>
  );
}
