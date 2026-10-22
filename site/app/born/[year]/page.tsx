import { notFound } from "next/navigation";
import BirthdayTool from "@/components/BirthdayTool";
import SiteNav from "@/components/SiteNav";
import { readYear } from "@/lib/data";
import { dateHref } from "@/lib/dates";
import { readable } from "@/lib/display";
import { bornYears, keyStates, money, monthYear, people, postsLine, readFacts, stateLabel } from "@/lib/facts";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return bornYears().map((y) => ({ year: String(y) }));
}

const BUILT = new Date().getUTCFullYear();
const HEADLINE = ["Geopolitics", "Conflict", "Science", "Technology", "Exploration", "Disasters", "Culture", "Economy"];

export async function generateMetadata({ params }: { params: Promise<{ year: string }> }) {
  const { year } = await params;
  const f = readFacts(parseInt(year, 10));
  if (!f?.prices) return { title: SITE.name };
  const title = `Born in ${year}? What the world was like the year you were born`;
  const gas = f.prices.items.find((i) => i.id === "gas");
  const description =
    `The year ${year}: $1 then is ${money(f.prices.dollar_today)} today` +
    (gas ? `, gas was ${money(gas.then)} a gallon` : "") +
    (f.hot100 ? `, the year's No. 1 songs` : "") +
    `, who was president, famous people born in ${year} and what happened.`;
  const url = canonical(`/born/${year}`);
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, images: OG_IMAGE, url, type: "article" },
    twitter: { card: "summary_large_image", title, description, images: OG_IMAGE },
  };
}

export default async function BornPage({ params }: { params: Promise<{ year: string }> }) {
  const { year } = await params;
  const y = parseInt(year, 10);
  const f = readFacts(y);
  const page = readYear(year);
  if (!f?.prices || !page) notFound();
  const p = f.prices;

  // Ranked by notability across every births list for the year, not only the few the
  // year page shows; falls back to those when the year has no ranked births.
  const births = f.births?.length ? f.births : page.sections.find((s) => s.title === "Births")?.items ?? [];
  const headline = HEADLINE.map((h) => page.sections.find((s) => s.title.startsWith(h))?.items[0])
    .filter((x): x is NonNullable<typeof x> => Boolean(x));
  const dated = page.sections
    .filter((s) => s.title !== "Births" && s.title !== "Deaths")
    .flatMap((s) => s.items)
    .filter((it) => dateHref(it.date))
    .map((it) => ({ date: it.date!, text: readable(it.text), url: it.cite.url }));
  const years = bornYears();
  const i = years.indexOf(y);
  const songs = f.hot100?.songs ?? [];

  return (
    <main className="min-h-screen">
      <SiteNav>
        <a className="text-base text-foreground" href="/born">/born</a>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebPage",
          name: `Born in ${year}`,
          url: canonical(`/born/${year}`),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          about: { "@type": "Thing", name: String(year) },
          citation: [
            p.cpi_source.url,
            ...(f.population ? [f.population.source.url] : []),
            ...(f.hot100?.source ? [f.hot100.source.url] : []),
            page.source.permalink,
          ],
          breadcrumb: breadcrumb([
            { name: "Born in…", path: "/born" },
            { name: String(year), path: `/born/${year}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Born in {year}</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          People born in {year} turn {BUILT - y} in {BUILT}. A dollar in {year} buys what{" "}
          {money(p.dollar_today)} buys in {monthYear(p.cpi_now_date)}
          {f.population ? `, and about ${people(f.population.value)} people were alive` : ""}. Every figure
          below links to the source it came from.
        </p>

        <BirthdayTool year={y} weeks={f.hot100?.weeks ?? []} dated={dated} />

        <section className="mb-10">
          <h2 className="mb-3 border-b border-border pb-2 text-lg font-medium text-foreground">
            What things cost in {year}
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1 pr-2 font-normal">U.S. average</th>
                <th className="py-1 pr-2 text-right font-normal">{year}</th>
                <th className="py-1 pr-2 text-right font-normal">in today&rsquo;s dollars</th>
                <th className="py-1 text-right font-normal">latest</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-border">
                <td className="py-1.5 pr-2">One dollar</td>
                <td className="py-1.5 pr-2 text-right tabular-nums">$1.00</td>
                <td className="py-1.5 pr-2 text-right tabular-nums">{money(p.dollar_today)}</td>
                <td className="py-1.5 text-right">
                  <a className="text-[10px] text-muted-foreground hover:underline" href={p.cpi_source.url} target="_blank" rel="noreferrer nofollow">
                    CPI-U
                  </a>
                </td>
              </tr>
              {p.items.map((it) => (
                <tr className="border-t border-border" key={it.id}>
                  <td className="py-1.5 pr-2">
                    {it.label}{" "}
                    <a className="align-super text-[10px] text-muted-foreground hover:underline" href={it.source.url} target="_blank" rel="noreferrer nofollow">
                      {it.source.series}
                    </a>
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{money(it.then)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{money(it.then_in_today_dollars)}</td>
                  <td className="py-1.5 text-right tabular-nums" title={monthYear(it.now_date)}>{money(it.now)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted-foreground">
            {year} figures are annual averages of the published monthly (or quarterly) values. &ldquo;Today&rsquo;s
            dollars&rdquo; uses the Consumer Price Index for {monthYear(p.cpi_now_date)}; &ldquo;latest&rdquo; is the most
            recent published price. Sources: U.S. Bureau of Labor Statistics, U.S. Census Bureau, U.S. Department of Labor, via FRED.
            {p.items.length === 0 && ` Average retail prices are only published from 1976 on; ${year} has the CPI alone.`}
          </p>
        </section>

        {f.leaders && keyStates(f.leaders).length > 0 && (
          <section className="mb-10">
            <h2 className="mb-3 border-b border-border pb-2 text-lg font-medium text-foreground">
              Who was in charge in {year}
            </h2>
            <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-[minmax(0,14rem)_1fr]">
              {keyStates(f.leaders).map((s) => (
                <div className="contents" key={s.state}>
                  <dt className="text-muted-foreground">{stateLabel(s)}</dt>
                  <dd className="text-foreground/85">{postsLine(s)}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-xs text-muted-foreground">
              From Wikipedia&rsquo;s{" "}
              <a className="underline underline-offset-2 hover:text-foreground" href={f.leaders.source.url} target="_blank" rel="noreferrer nofollow">
                {f.leaders.source.title}
              </a>{" "}
              (revision {f.leaders.source.revid}), each name checked against Wikidata.{" "}
              <a className="underline underline-offset-2 hover:text-foreground" href={`/leaders/${year}`}>Every country in {year} →</a>
            </p>
          </section>
        )}

        {songs.length > 0 && f.hot100?.source && (
          <section className="mb-10">
            <h2 className="mb-3 border-b border-border pb-2 text-lg font-medium text-foreground">
              No. 1 songs of {year}
            </h2>
            <ol className="flex flex-col gap-1 text-sm text-foreground/85">
              {songs.map((s, k) => (
                <li key={k}>
                  &ldquo;{s.title}&rdquo; — {s.artist}{" "}
                  <span className="text-muted-foreground">
                    ({s.weeks} week{s.weeks === 1 ? "" : "s"})
                  </span>
                </li>
              ))}
            </ol>
            <p className="mt-2 text-xs text-muted-foreground">
              Weeks at No. 1 on the Billboard Hot 100 with issue dates in {year}, from{" "}
              <a className="underline underline-offset-2" href={f.hot100.source.url} target="_blank" rel="noreferrer nofollow">
                {f.hot100.source.title}
              </a>{" "}
              (Wikipedia revision {f.hot100.source.revid}).
            </p>
          </section>
        )}

        {births.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-3 border-b border-border pb-2 text-lg font-medium text-foreground">
              Famous people born in {year}
            </h2>
            <ul className="flex flex-col gap-2">
              {births.map((b, k) => (
                <li className="text-sm leading-relaxed text-foreground/90" key={k}>
                  {readable(b.text)}{" "}
                  <a className="align-super text-[10px] text-muted-foreground hover:underline" href={b.cite.url} target="_blank" rel="noreferrer nofollow">
                    source
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        {headline.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-3 border-b border-border pb-2 text-lg font-medium text-foreground">
              What happened in {year}
            </h2>
            <ul className="flex flex-col gap-2">
              {headline.map((it, k) => (
                <li className="text-sm leading-relaxed text-foreground/90" key={k}>
                  {readable(it.text)}{" "}
                  <a className="align-super text-[10px] text-muted-foreground hover:underline" href={it.cite.url} target="_blank" rel="noreferrer nofollow">
                    source
                  </a>
                </li>
              ))}
            </ul>
            <a className="mt-3 inline-block text-sm underline underline-offset-2" href={`/${year}`}>
              Everything that happened in {year} →
            </a>
          </section>
        )}

        <nav className="mb-10 flex justify-between text-sm" aria-label="Nearby">
          {i > 0 ? <a className="underline underline-offset-2" href={`/born/${years[i - 1]}`}>← Born in {years[i - 1]}</a> : <span />}
          {i < years.length - 1 ? <a className="underline underline-offset-2" href={`/born/${years[i + 1]}`}>Born in {years[i + 1]} →</a> : <span />}
        </nav>

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Prices and the CPI are U.S. government statistics (public domain). World population is Our World in
          Data&rsquo;s series (CC BY 4.0). Office holders are quoted from Wikipedia&rsquo;s lists of state leaders and checked against Wikidata. People, events and the song
          lists are quoted from the English Wikipedia revision linked beside each one (CC BY-SA 4.0). Nothing
          here is estimated or generated: a figure a source does not publish for {year} is left out.
        </footer>
      </article>
    </main>
  );
}
