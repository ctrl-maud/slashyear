"use client";

import { useEffect, useState } from "react";

type Src = { wikipedia_article?: string; revision_id?: number; url?: string };
type Line = { text: string; source: Src };
type Snap = {
  error?: string;
  date: string;
  weekday?: string;
  events: Line[];
  births: Line[];
  deaths: Line[];
  events_same_year: number;
  leaders?: { basis: string; states: { state: string; holders: { name: string; post: string | null }[] }[]; source: { title: string; url: string } };
  number_one_song?: { chart_issue_date: string; title: string; artist: string; source: { url: string } };
  us_prices?: { one_dollar_then_in_today_dollars: number; today_as_of: string; items: { label: string; per: string; then: number; source: { url: string } }[] };
  world_population?: { value: number; source: { url: string } };
  official_series?: Record<string, { name: string; unit: string; value: number; source: { publisher: string; url: string } }>;
  nobel_prizes?: { prizes: { category: string; name: string }[] };
  exchange_rates?: { rates: { name: string; unit: string; value: number; source: { url: string } }[] };
  pages: { year: string; day: string; leaders?: string };
};

const fmt = (n: number) => n.toLocaleString("en-US");
const A = ({ href, children }: { href: string; children: React.ReactNode }) => (
  <a className="underline underline-offset-2 hover:text-foreground" href={href}>{children}</a>
);

function H({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-2 mt-8 text-xs uppercase tracking-wide text-muted-foreground">{children}</h2>;
}

function Lines({ rows }: { rows: Line[] }) {
  return (
    <ul className="space-y-2">
      {rows.map((r, i) => (
        <li key={i} className="text-sm leading-relaxed text-foreground/90">
          {r.text}{" "}
          {r.source?.url && <a className="text-xs text-muted-foreground underline-offset-2 hover:underline" href={r.source.url}>[{r.source.wikipedia_article}, rev {r.source.revision_id}]</a>}
        </li>
      ))}
    </ul>
  );
}

export default function AsOf() {
  const [date, setDate] = useState("1969-07-20");
  const [snap, setSnap] = useState<Snap | null>(null);
  const [busy, setBusy] = useState(false);

  async function load(d: string) {
    setBusy(true);
    try {
      const r = await fetch(`/api/asof/${d}`);
      setSnap(await r.json());
      history.replaceState(null, "", `/asof?date=${d}`);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const d = new URLSearchParams(location.search).get("date");
    const start = d && /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : "1969-07-20";
    setDate(start);
    load(start);
  }, []);

  return (
    <div>
      <form
        className="mb-8 flex flex-wrap items-center gap-2 border border-border p-4 text-sm"
        onSubmit={(e) => { e.preventDefault(); load(date); }}
      >
        <label htmlFor="asof-date" className="text-foreground">Date</label>
        <input id="asof-date" type="date" min="0001-01-01" max="2025-12-31" value={date}
          onChange={(e) => setDate(e.target.value)} className="border border-border bg-background px-2 py-1" />
        <button className="border border-border px-3 py-1 hover:bg-muted" type="submit">{busy ? "Loading…" : "Show"}</button>
        <a className="ml-auto text-xs text-muted-foreground underline-offset-2 hover:underline" href={`/api/asof/${date}`}>JSON</a>
      </form>
      {snap?.error && <p className="text-sm text-muted-foreground">{snap.error}</p>}
      {snap && !snap.error && (
        <div>
          <p className="text-2xl text-foreground">{snap.date}{snap.weekday ? `, a ${snap.weekday}` : ""}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            <A href={snap.pages.year}>The whole year</A> · <A href={snap.pages.day}>This day in every year</A>
            {snap.pages.leaders && <> · <A href={snap.pages.leaders}>Every leader that year</A></>}
          </p>

          <H>That day</H>
          {snap.events.length ? <Lines rows={snap.events} /> : <p className="text-sm text-muted-foreground">Nothing in the record is dated to this exact day. The year has {snap.events_same_year} other dated entries.</p>}
          {snap.births.length > 0 && (<><H>Born that day</H><Lines rows={snap.births} /></>)}
          {snap.deaths.length > 0 && (<><H>Died that day</H><Lines rows={snap.deaths} /></>)}

          {snap.number_one_song && (
            <>
              <H>No. 1 on the Billboard Hot 100</H>
              <p className="text-sm text-foreground/90">
                &ldquo;{snap.number_one_song.title}&rdquo; by {snap.number_one_song.artist} (issue dated {snap.number_one_song.chart_issue_date}){" "}
                <a className="text-xs text-muted-foreground hover:underline" href={snap.number_one_song.source.url}>[source]</a>
              </p>
            </>
          )}

          {snap.exchange_rates && (
            <>
              <H>Exchange rates that day (Federal Reserve)</H>
              <ul className="text-sm text-foreground/90">
                {snap.exchange_rates.rates.map((r) => (<li key={r.name}>{r.value} {r.unit} <a className="text-xs text-muted-foreground hover:underline" href={r.source.url}>[source]</a></li>))}
              </ul>
            </>
          )}

          {(snap.us_prices || snap.world_population || snap.official_series) && (
            <>
              <H>The year in numbers</H>
              <ul className="space-y-1 text-sm text-foreground/90">
                {snap.world_population && <li>World population: {fmt(snap.world_population.value)} <a className="text-xs text-muted-foreground hover:underline" href={snap.world_population.source.url}>[source]</a></li>}
                {snap.us_prices && <li>$1 then is worth ${snap.us_prices.one_dollar_then_in_today_dollars.toFixed(2)} as of {snap.us_prices.today_as_of.slice(0, 7)} (U.S. CPI)</li>}
                {snap.us_prices?.items.map((i) => (
                  <li key={i.label}>{i.label}: ${fmt(i.then)} per {i.per} <a className="text-xs text-muted-foreground hover:underline" href={i.source.url}>[source]</a></li>
                ))}
                {snap.official_series && Object.entries(snap.official_series).map(([k, s]) => (
                  <li key={k}>{s.name}: {fmt(s.value)} {s.unit} <a className="text-xs text-muted-foreground hover:underline" href={s.source.url}>[{s.source.publisher}]</a></li>
                ))}
              </ul>
            </>
          )}

          {snap.nobel_prizes && snap.nobel_prizes.prizes.length > 0 && (
            <>
              <H>Nobel Prizes that year</H>
              <ul className="text-sm text-foreground/90">
                {snap.nobel_prizes.prizes.map((p, i) => (<li key={i}>{p.category}: {p.name}</li>))}
              </ul>
            </>
          )}

          {snap.leaders && (
            <>
              <H>Leaders in office that year</H>
              <p className="mb-2 text-xs text-muted-foreground">{snap.leaders.basis}.</p>
              <ul className="columns-1 gap-6 text-sm text-foreground/90 sm:columns-2">
                {snap.leaders.states.map((s) => (
                  <li key={s.state} className="mb-1 break-inside-avoid">
                    <span className="text-muted-foreground">{s.state}:</span> {s.holders.map((h) => h.name + (h.post ? ` (${h.post})` : "")).join("; ")}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
