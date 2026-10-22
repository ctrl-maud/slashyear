"use client";

import { useEffect, useState } from "react";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];
const LENGTHS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

type Week = { date: string; title: string; artist: string };
type Dated = { date: string; text: string; url: string };
type Birth = { year: number; year_label: string; text: string; cite: { url: string } };

/** The part of a birthday that depends on the day, not just the year: the No. 1 song that
 *  week, what the year article records on that exact date, and who else was born on it.
 *  The day comes from the URL hash (/born/1985#july-13) so the /born form can link
 *  straight to it and a reader can share the result. */
export default function BirthdayTool({ year, weeks, dated }: { year: number; weeks: Week[]; dated: Dated[] }) {
  const [month, setMonth] = useState<number | null>(null);
  const [day, setDay] = useState<number | null>(null);
  const [births, setBirths] = useState<Birth[] | null>(null);

  useEffect(() => {
    const read = () => {
      const m = /^#([a-z]+)-(\d{1,2})$/.exec(window.location.hash);
      if (!m) return;
      const mi = MONTHS.findIndex((x) => x.toLowerCase() === m[1]);
      const d = parseInt(m[2], 10);
      if (mi >= 0 && d >= 1 && d <= LENGTHS[mi]) {
        setMonth(mi);
        setDay(d);
      }
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);

  useEffect(() => {
    if (month === null || day === null) return;
    const slug = `${MONTHS[month].toLowerCase()}-${day}`;
    if (window.location.hash !== `#${slug}`) history.replaceState(null, "", `#${slug}`);
    setBirths(null);
    fetch(`/api/date/${slug}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const g = d?.groups?.find((g: { title: string }) => g.title === "Births");
        // The same person can be listed by both the year article and a country-year
        // article; keep the first of each name.
        const seen = new Set<string>();
        const rows = (g ? g.items : []).filter((b: Birth) => {
          const who = b.text.split(",")[0].trim().toLowerCase();
          if (seen.has(who)) return false;
          seen.add(who);
          return true;
        });
        setBirths(rows);
      })
      .catch(() => setBirths([]));
  }, [month, day]);

  const iso = month !== null && day !== null
    ? `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
    : null;
  const valid = iso !== null && !(month === 1 && day === 29 && !(year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)));
  // Billboard dates each issue by a day at the end of its chart week, so the issue that
  // covers a birthday is the first one dated on or after it. Said on the page, not hidden.
  const song = valid ? weeks.find((w) => w.date >= iso!) ?? null : null;
  const label = month !== null && day !== null ? `${MONTHS[month]} ${day}` : "";
  const sameDay = dated.filter((d) => d.date === label);
  const ageDays = valid ? Math.floor((Date.now() - Date.parse(iso! + "T00:00:00Z")) / 86400000) : null;

  return (
    <section className="mb-10 border border-border p-4" id="birthday">
      <h2 className="mb-3 text-lg font-medium text-foreground">Your birthday in {year}</h2>
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <select
          aria-label="Month"
          className="border border-border bg-background px-2 py-1"
          value={month ?? ""}
          onChange={(e) => setMonth(e.target.value === "" ? null : parseInt(e.target.value, 10))}
        >
          <option value="">Month</option>
          {MONTHS.map((m, i) => (
            <option key={m} value={i}>{m}</option>
          ))}
        </select>
        <select
          aria-label="Day"
          className="border border-border bg-background px-2 py-1"
          value={day ?? ""}
          onChange={(e) => setDay(e.target.value === "" ? null : parseInt(e.target.value, 10))}
        >
          <option value="">Day</option>
          {Array.from({ length: month === null ? 31 : LENGTHS[month] }, (_, i) => i + 1).map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <span className="text-muted-foreground">{year}</span>
      </div>
      {iso && !valid && <p className="text-sm text-muted-foreground">{year} had no February 29.</p>}
      {valid && (
        <div className="flex flex-col gap-4 text-sm text-foreground/85">
          {ageDays !== null && ageDays > 0 && (
            <p>
              You have been alive for about <strong>{ageDays.toLocaleString("en-US")} days</strong>.
            </p>
          )}
          {song ? (
            <p>
              No. 1 on the Billboard Hot 100 that week: <strong>&ldquo;{song.title}&rdquo;</strong> by {song.artist}{" "}
              <span className="text-muted-foreground">
                (the first chart issue dated on or after your birthday, {song.date})
              </span>
              .
            </p>
          ) : weeks.length === 0 && year < 1958 ? (
            <p className="text-muted-foreground">The Billboard Hot 100 started in August 1958, so there is no No. 1 for this date.</p>
          ) : null}
          <div>
            <h3 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Recorded on {label}, {year}
            </h3>
            {sameDay.length ? (
              <ul className="flex flex-col gap-2">
                {sameDay.map((d, i) => (
                  <li className="leading-relaxed" key={i}>
                    {d.text}{" "}
                    <a className="align-super text-[10px] text-muted-foreground hover:underline" href={d.url} target="_blank" rel="noreferrer nofollow">
                      source
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">
                Nothing on the {year} page is dated {label}.{" "}
                <a className="underline underline-offset-2" href={`/${year}`}>See the whole year →</a>
              </p>
            )}
          </div>
          <div>
            <h3 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Also born on {label}
            </h3>
            {births === null ? (
              <p className="text-muted-foreground">Loading…</p>
            ) : births.length ? (
              <ul className="flex flex-col gap-2">
                {births.slice(-12).reverse().map((b, i) => (
                  <li className="leading-relaxed" key={i}>
                    <a className="mr-2 tabular-nums font-medium underline decoration-dotted underline-offset-2" href={b.year === 404 ? "/404/" : `/${b.year}`}>
                      {b.year_label.replace(/ CE$/, "")}
                    </a>
                    {b.text}{" "}
                    <a className="align-super text-[10px] text-muted-foreground hover:underline" href={b.cite.url} target="_blank" rel="noreferrer nofollow">
                      source
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">No births are filed under {label}.</p>
            )}
            <a className="mt-2 inline-block underline underline-offset-2" href={`/on/${MONTHS[month!].toLowerCase()}-${day}`}>
              Everything on {label} in history →
            </a>
          </div>
        </div>
      )}
    </section>
  );
}
