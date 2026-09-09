"use client";

import { useEffect, useState } from "react";
import YearNav from "@/components/YearNav";

/** Undocumented years still deserve an answer: say so, and point at the nearest year
 *  that does have sourced records. */
export default function NotFound() {
  const [label, setLabel] = useState<string | null>(null);
  const [nearest, setNearest] = useState<{ year: number; label: string } | null>(null);

  useEffect(() => {
    const raw = decodeURIComponent(window.location.pathname.replace(/^\//, "").replace(/\/$/, ""));
    const n = parseInt(raw, 10);
    if (Number.isNaN(n)) return;
    setLabel(n > 0 ? `${n} CE` : `${Math.abs(n) + 1} BCE`);
    fetch("/years.json")
      .then((r) => r.json())
      .then((rows: { year: number; label: string }[]) => {
        let best = rows[0];
        for (const r of rows) {
          if (Math.abs(r.year - n) < Math.abs(best.year - n)) best = r;
        }
        setNearest(best);
      })
      .catch(() => {});
  }, []);

  return (
    <main className="min-h-screen">
      <YearNav />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">
          {label ?? "Not found"}
        </h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          No sourced records for this year yet.
          {nearest ? (
            <>
              {" "}
              The nearest year with records is{" "}
              <a className="underline underline-offset-2" href={`/${nearest.year}`}>
                {nearest.label}
              </a>
              .
            </>
          ) : null}
        </p>
      </article>
    </main>
  );
}
