import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import { hasPlace, placeSlug } from "@/lib/cross";
import { keyStates, leaderYears, posts, postsLine, readFacts, stateLabel, wiki, type StateRow } from "@/lib/facts";
import { breadcrumb, canonical, JsonLd, SITE, trim, OG_IMAGE } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return leaderYears().map((y) => ({ year: String(y) }));
}

const REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"];

export async function generateMetadata({ params }: { params: Promise<{ year: string }> }) {
  const { year } = await params;
  const f = readFacts(parseInt(year, 10));
  if (!f?.leaders) return { title: SITE.name };
  const key = keyStates(f.leaders);
  const title = `World leaders in ${year}: who ruled every country`;
  const description = trim(
    `Who led every country in ${year}. ${key
      .slice(0, 4)
      .map((s) => `${stateLabel(s)}: ${postsLine(s)}`)
      .join(". ")}.`,
  );
  const url = canonical(`/leaders/${year}`);
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, images: OG_IMAGE, url, type: "article" },
    twitter: { card: "summary_large_image", title, description, images: OG_IMAGE },
  };
}

function State({ s, heading }: { s: StateRow; heading: string }) {
  const country = [s.country, s.key].find((c) => c && hasPlace(c));
  const place = country ? `/in/${placeSlug(country)}` : null;
  return (
    <section className="mb-5">
      <h3 className="mb-1 text-base font-medium text-foreground">
        {heading}
        {place && (
          <a className="ml-2 text-xs font-normal text-muted-foreground underline-offset-2 hover:underline" href={place}>
            {country} history
          </a>
        )}
      </h3>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-[minmax(0,14rem)_1fr]">
        {posts(s).map(([post, names]) => (
          <div className="contents" key={post}>
            <dt className="text-muted-foreground">{post}</dt>
            <dd className="text-foreground/85">
              {names.map((n, i) => {
                const h = s.holders.find((h) => h.name === n)!;
                return (
                  <span key={n}>
                    {i > 0 && ", then "}
                    <a className="underline-offset-2 hover:underline" href={wiki(h.person)} title={h.quote} target="_blank" rel="noreferrer nofollow">
                      {n}
                    </a>
                  </span>
                );
              })}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export default async function LeadersYear({ params }: { params: Promise<{ year: string }> }) {
  const { year } = await params;
  const y = parseInt(year, 10);
  const f = readFacts(y);
  if (!f?.leaders) notFound();
  const L = f.leaders;
  const key = keyStates(L);
  const years = leaderYears();
  const i = years.indexOf(y);
  const byRegion = REGIONS.map((r) => ({
    region: r,
    states: L.states.filter((s) => s.region === r).sort((a, b) => a.state.localeCompare(b.state)),
  })).filter((g) => g.states.length);

  return (
    <main className="min-h-screen">
      <SiteNav>
        <a className="text-base text-foreground" href="/leaders">/leaders</a>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: `World leaders in ${year}`,
          url: canonical(`/leaders/${year}`),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          isBasedOn: { "@type": "CreativeWork", name: L.source.title, url: L.source.url, license: "https://creativecommons.org/licenses/by-sa/4.0/" },
          breadcrumb: breadcrumb([
            { name: "World leaders", path: "/leaders" },
            { name: String(year), path: `/leaders/${year}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">World leaders in {year}</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Everyone who held a state&rsquo;s top posts at some point in {year}, in the order they held them. Names
          are from Wikipedia&rsquo;s list of state leaders and appear only where the person&rsquo;s Wikidata record
          agrees on the post and the years.{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href={`/${year}`}>What happened in {year} →</a>
        </p>

        {key.length > 0 && (
          <section className="mb-10 border border-border p-4">
            <h2 className="mb-3 text-lg font-medium text-foreground">Major powers in {year}</h2>
            {key.map((s) => (
              <State key={s.state} s={s} heading={stateLabel(s)} />
            ))}
          </section>
        )}

        {byRegion.map((g) => (
          <section className="mb-8" key={g.region}>
            <h2 className="mb-3 border-b border-border pb-1 text-lg font-medium text-foreground">{g.region}</h2>
            {g.states.map((s) => (
              <State key={s.state} s={s} heading={s.state} />
            ))}
          </section>
        ))}

        <nav className="mb-10 mt-10 flex justify-between text-sm" aria-label="Nearby">
          {i > 0 ? <a className="underline underline-offset-2" href={`/leaders/${years[i - 1]}`}>← {years[i - 1]}</a> : <span />}
          {i < years.length - 1 ? <a className="underline underline-offset-2" href={`/leaders/${years[i + 1]}`}>{years[i + 1]} →</a> : <span />}
        </nav>
        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Quoted from English Wikipedia,{" "}
          <a className="underline underline-offset-2" href={L.source.url} target="_blank" rel="noreferrer nofollow">
            {L.source.title}
          </a>{" "}
          (revision {L.source.revid}, CC BY-SA 4.0); hover a name for the line it came from. A name is kept for{" "}
          {year} only when the person&rsquo;s Wikidata record holds the same post with start and end years within
          a year of the list&rsquo;s, so a mistyped term on either side drops the name instead of printing it.
          States and titles are as the list writes them. Machine-readable:{" "}
          <a className="underline underline-offset-2" href={`/api/facts/${year}.json`}>/api/facts/{year}.json</a>.
        </footer>
      </article>
    </main>
  );
}
