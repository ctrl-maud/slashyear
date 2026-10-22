import BornForm from "@/components/BornForm";
import SiteNav from "@/components/SiteNav";
import { bornYears } from "@/lib/facts";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

const title = "The year you were born: prices, No. 1 songs, leaders and events";
const description =
  "Enter your birthday to see the No. 1 song that week, what a dollar was worth, what gas and eggs cost, who was president and who else was born on your day. Every figure sourced.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/born") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/born") },
};

export default function BornHub() {
  const years = bornYears();
  const decades = Array.from(new Set(years.map((y) => Math.floor(y / 10) * 10)));

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/born</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: title,
          description,
          url: canonical("/born"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([{ name: "Born in…", path: "/born" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">The year you were born</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          What a dollar was worth, what gas, eggs and a house cost, the No. 1 song the week you were born, who
          led the world&rsquo;s countries, and who else shares your birthday. The prices are U.S. government
          statistics, the leaders are quoted from Wikipedia and checked against Wikidata, and the songs and people are quoted from cited Wikipedia
          revisions, each linked to its source.
        </p>
        <BornForm first={years[0]} last={years[years.length - 1]} />
        {decades.map((d) => (
          <section className="mb-6" key={d}>
            <h2 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{d}s</h2>
            <ul className="flex flex-wrap gap-x-3 gap-y-1">
              {years
                .filter((y) => y >= d && y < d + 10)
                .map((y) => (
                  <li key={y}>
                    <a className="text-sm text-foreground/85 underline-offset-2 hover:text-foreground hover:underline" href={`/born/${y}`}>
                      {y}
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
