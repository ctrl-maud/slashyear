"use client";

import { useEffect, useState } from "react";

import { readable } from "@/lib/display";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];

type Item = { year: number; year_label: string; text: string; kind?: string; cite: { url: string } };
type Day = { label: string; slug: string; count: number; span: [string, string]; items: Item[] };

/** The directory is 2,960 numbers and never changes. This puts the current calendar date's
 *  own entries at the top of it, so the front page says something different every morning
 *  and a returning reader has a reason to come back. It renders in the browser from /api,
 *  because the site is a static export built once and the date is not known at build time.
 *
 *  It must never read as news. A heading of "Today" over a 2022 death notice is scanned as
 *  something that happened this morning, so the block is headed "On this day", it states
 *  the range it is drawn from, it leads with the year rather than the sentence, and the
 *  four entries are spread across the whole span oldest-first instead of being the four
 *  most recent — a list that starts in the 600s cannot be mistaken for a news feed. */
export default function Today() {
  const [day, setDay] = useState<Day | null>(null);

  useEffect(() => {
    const now = new Date();
    const slug = `${MONTHS[now.getMonth()]} ${now.getDate()}`.toLowerCase().replace(" ", "-");
    fetch(`/api/date/${slug}.json`)
      .then((r) => r.json())
      .then((d) => {
        // /api groups by events / births / deaths, so the flattened list is not in year
        // order; sort it before spreading picks across it or the four jump eras.
        // Keep each group's title on its rows: a teaser line pulled out of the
        // Births group has to SAY it is a birth once the heading is gone, or
        // "Aurelian, Roman emperor (died 275)" under today's date reads as an event.
        const all: Item[] = (d.groups ?? [])
          .flatMap((g: { title: string; items: Item[] }) =>
            g.items.map((it) => ({ ...it, kind: g.title })))
          .sort((a: Item, b: Item) => a.year - b.year);
        if (!all.length) return;
        // Four picks spread across the whole range, oldest first — but a teaser row has
        // to stand alone. "Died: Marcus Annius Verus, Roman co-ruler" is a fragment with
        // no story; near each spread position, prefer a row that carries an actual
        // clause: an event sentence, or a birth/death saying more than name and title.
        const standsAlone = (it: Item) =>
          it.kind === "Events" ||
          it.text.replace(/\((?:born|died|b\.|d\.)[^)]*\)/g, "").trim().length >= 70;
        const want = Math.min(4, all.length);
        const picks: number[] = [];
        for (let i = 0; i < want; i++) {
          const target = Math.round((i * (all.length - 1)) / Math.max(1, want - 1));
          const radius = Math.max(1, Math.floor(all.length / (want * 2)));
          let fallback = -1;
          let best = -1;
          for (let off = 0; off <= radius && best < 0; off++) {
            for (const j of [target - off, target + off]) {
              if (j < 0 || j >= all.length || picks.includes(j)) continue;
              if (fallback < 0) fallback = j;
              if (standsAlone(all[j])) { best = j; break; }
            }
          }
          const pick = best >= 0 ? best : fallback;
          if (pick >= 0 && !picks.includes(pick)) picks.push(pick);
        }
        picks.sort((a, b) => a - b);
        setDay({
          label: d.label,
          slug,
          count: d.count ?? all.length,
          span: d.span ?? [all[0].year_label, all[all.length - 1].year_label],
          items: picks.map((i) => all[i]),
        });
      })
      .catch(() => {});
  }, []);

  if (!day) return null;
  const year = (s: string) => s.replace(/ CE$/, "");
  return (
    <section className="mb-10">
      <h2 className="mb-2 border-b border-border pb-2 text-lg font-medium text-foreground">
        On this day — {day.label}
      </h2>
      <p className="mb-4 text-xs text-muted-foreground">
        {day.count} sourced entries are filed under {day.label}, from {year(day.span[0])} to{" "}
        {year(day.span[1])}. Four of them, spread across that range:
      </p>
      <ul className="mb-3 flex flex-col gap-3">
        {day.items.map((item, i) => (
          <li className="text-sm leading-relaxed text-foreground/85" key={i}>
            <a
              className="mr-2 tabular-nums font-medium text-foreground underline decoration-dotted underline-offset-2 hover:decoration-solid"
              href={item.year === 404 ? "/404/" : `/${item.year}`}
            >
              {year(item.year_label)}
            </a>
            {/* The label makes a bare "Aurelian, Roman emperor" read as the death it is,
                but next to a row that already says "…is assassinated…" it is noise. */}
            {item.kind === "Births" && !/\bis born\b/.test(item.text) ? (
              <span className="mr-1 text-muted-foreground">Born:</span>
            ) : item.kind === "Deaths" &&
              !/\b(dies|is (assassinated|killed|executed|murdered))\b/.test(item.text) ? (
              <span className="mr-1 text-muted-foreground">Died:</span>
            ) : null}
            {readable(item.text)}
          </li>
        ))}
      </ul>
      <a
        className="text-sm text-muted-foreground underline underline-offset-2 hover:text-foreground"
        href={`/on/${day.slug}`}
      >
        Everything recorded on {day.label} →
      </a>
    </section>
  );
}
