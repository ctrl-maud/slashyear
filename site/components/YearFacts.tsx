import { money, monthYear, panelStates, people, postsLine, readFacts, stateLabel } from "@/lib/facts";

/** The questions people actually put to a year, answered from the public series that
 *  hold the answer, each figure linked to its publisher. Rendered as a definition list,
 *  never as <li> bullets: everything in a bullet on this page is a Wikipedia quote and
 *  pipeline/audit.py checks it word for word against the source. */
export default function YearFacts({ year }: { year: number }) {
  const f = readFacts(year);
  if (!f) return null;
  const key = panelStates(f.leaders);
  const most = Math.max(0, ...(f.hot100?.songs.map((s) => s.weeks) ?? []));
  const top = f.hot100?.songs.filter((s) => s.weeks === most) ?? [];
  const gas = f.prices?.items.find((i) => i.id === "gas");
  const rows: { term: string; value: React.ReactNode; src: { href: string; label: string } }[] = [];

  if (f.population)
    rows.push({
      term: "World population",
      value: `about ${people(f.population.value)}`,
      src: { href: f.population.source.url, label: f.population.source.publisher ?? f.population.source.name },
    });
  for (const s of key) {
    rows.push({
      term: stateLabel(s),
      value: postsLine(s),
      src: { href: f.leaders!.source.url, label: `Wikipedia rev. ${f.leaders!.source.revid}` },
    });
  }
  if (f.prices)
    rows.push({
      term: `$1 in ${year}`,
      value: `${money(f.prices.dollar_today)} in ${monthYear(f.prices.cpi_now_date)} dollars`,
      src: { href: f.prices.cpi_source.url, label: "BLS CPI-U" },
    });
  if (gas)
    rows.push({
      term: "Gallon of gas (U.S. average)",
      value: `${money(gas.then)} (${money(gas.now)} in ${monthYear(gas.now_date)})`,
      src: { href: gas.source.url, label: "BLS" },
    });
  if (top.length && f.hot100?.source)
    rows.push({
      term: `Most weeks at No. 1 in ${year}`,
      value: `${top.map((s) => `“${s.title}” by ${s.artist}`).join("; ")}, ${most} week${most === 1 ? "" : "s"}${top.length > 1 ? " each" : ""}`,
      src: { href: f.hot100.source.url, label: `Wikipedia rev. ${f.hot100.source.revid}` },
    });
  if (!rows.length) return null;

  return (
    <section className="mb-10 border border-border p-4" aria-label={`${year} at a glance`}>
      <h2 className="mb-3 text-lg font-medium text-foreground">{year} at a glance</h2>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-[minmax(0,13rem)_1fr]">
        {rows.map((r, i) => (
          <div className="contents" key={i}>
            <dt className="text-muted-foreground">{r.term}</dt>
            <dd className="text-foreground/85">
              {r.value}{" "}
              <a
                className="align-super text-[10px] text-muted-foreground hover:text-foreground hover:underline"
                href={r.src.href}
                target="_blank"
                rel="noreferrer nofollow"
              >
                {r.src.label}
              </a>
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 flex flex-wrap gap-x-4 text-sm">
        {f.leaders && (
          <a className="underline underline-offset-2 hover:text-foreground" href={`/leaders/${year}`}>
            Who led every country in {year} →
          </a>
        )}
        {f.prices && (
          <a className="underline underline-offset-2 hover:text-foreground" href={`/born/${year}`}>
            Born in {year}? What it cost, who led, what was No. 1 →
          </a>
        )}
      </p>
    </section>
  );
}
