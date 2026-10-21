import SiteNav from "@/components/SiteNav";
import Today from "@/components/Today";
import { readDateIndex, MONTHS } from "@/lib/dates";
import { breadcrumb, canonical, JsonLd, SITE , OG_IMAGE } from "@/lib/seo";

const title = "On this day in history — events, births and deaths for every date";
const description =
  "What happened on this day in history: today's events, births and deaths, and every other calendar date, each line quoted from the Wikipedia revision it came from.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/on") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/on") },
};

export default function Calendar() {
  const { dates, total } = readDateIndex();

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: title,
          description,
          url: canonical("/on"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "On this day", path: "/on" },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">On this day</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {total.toLocaleString()} sourced entries filed by the calendar day they happened on.
          Pick a date to see everything recorded on it, oldest first, each line quoted from the
          revision it came from.
        </p>
        <Today />
        {MONTHS.map((month) => (
          <section className="mb-8" key={month}>
            <h2 className="mb-3 border-b border-border pb-2 text-lg font-medium text-foreground">
              {month}
            </h2>
            <ul className="flex flex-wrap gap-x-3 gap-y-1">
              {dates
                .filter((d) => d.month === month)
                .map((d) => (
                  <li key={d.slug}>
                    <a
                      className="text-sm text-foreground/85 underline-offset-2 hover:text-foreground hover:underline"
                      href={`/on/${d.slug}`}
                      title={`${d.label} — ${d.count} entries`}
                    >
                      {d.day}
                    </a>
                  </li>
                ))}
            </ul>
          </section>
        ))}
      </article>
    </main>
  );
}
