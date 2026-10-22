import SiteNav from "@/components/SiteNav";
import { leaderYears } from "@/lib/facts";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

const title = "World leaders by year: who ruled every country";
const description =
  "Pick a year to see who led every country in it: presidents, monarchs, prime ministers, chancellors and party leaders, quoted from Wikipedia's lists of state leaders and checked against Wikidata.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/leaders") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/leaders") },
};

export default function LeadersHub() {
  const years = leaderYears();
  const decades = Array.from(new Set(years.map((y) => Math.floor(y / 10) * 10)));

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/leaders</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: title,
          description,
          url: canonical("/leaders"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([{ name: "World leaders", path: "/leaders" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">World leaders by year</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Who held each country&rsquo;s top posts in a given year. Every name is taken from Wikipedia&rsquo;s lists
          of state leaders and kept only where the person&rsquo;s own Wikidata record shows the same post over the
          same years; where the two disagree, the name is left out rather than guessed. The same data is at{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="/api/facts/1985.json">/api/facts/&#123;year&#125;.json</a>.
        </p>
        {decades.map((d) => (
          <section className="mb-6" key={d}>
            <h2 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{d}s</h2>
            <p className="flex flex-wrap gap-x-3 gap-y-1">
              {years
                .filter((y) => y >= d && y < d + 10)
                .map((y) => (
                  <a key={y} className="text-sm text-foreground/85 underline-offset-2 hover:text-foreground hover:underline" href={`/leaders/${y}`}>
                    {y}
                  </a>
                ))}
            </p>
          </section>
        ))}
      </article>
    </main>
  );
}
