"use client";

import { useState } from "react";

type Ev = { year?: number; date?: string | null; text?: string; title?: string; artist?: string; chart_issue_date?: string;
  name?: string; post?: string; state?: string; quote?: string; category?: string;
  source?: { url?: string; wikipedia_article?: string; revision_id?: number } };
type Res = { error?: string; verdict?: string; explanation?: string; basis?: string; evidence?: Ev[] };

const LABEL: Record<string, string> = {
  supported: "Supported by the record",
  contradicted: "Contradicted by the record",
  matched_same_year: "An entry dated that year holds every key word",
  matched_other_dates: "Matching entries, but dated to other days",
  matched_other_years: "Matching entries, but dated to other years",
  partial_matches: "Only partial matches",
  evidence_only: "No year given: here is where the record dates it",
  no_evidence: "Nothing in the record bears on it",
};

const EXAMPLES = [
  "Richard Nixon was president of the United States in 1975",
  "The Berlin Wall fell in 1991",
  "Hey Jude was number one on the Billboard Hot 100 in 1968",
  "Albert Einstein won the Nobel Prize in Physics in 1921",
];

function line(e: Ev) {
  if (e.text) return `${e.year ?? ""}: ${e.text}`;
  if (e.chart_issue_date) return `${e.chart_issue_date}: "${e.title}" by ${e.artist}`;
  if (e.quote) return `${e.year}, ${e.state}: ${e.quote}`;
  if (e.category) return `${e.category}: ${e.name}`;
  return JSON.stringify(e);
}

export default function CheckClaim() {
  const [claim, setClaim] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(c: string) {
    if (!c.trim()) return;
    setBusy(true);
    try {
      const r = await fetch(`/api/check?claim=${encodeURIComponent(c)}`);
      setRes(await r.json());
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <form className="mb-3 flex flex-col gap-2 border border-border p-4 text-sm" onSubmit={(e) => { e.preventDefault(); run(claim); }}>
        <label htmlFor="claim" className="text-foreground">A sentence with a date in it</label>
        <input id="claim" className="border border-border bg-background px-2 py-1" value={claim} maxLength={400}
          placeholder="Richard Nixon was president of the United States in 1975" onChange={(e) => setClaim(e.target.value)} />
        <button className="self-start border border-border px-3 py-1 hover:bg-muted" type="submit">{busy ? "Checking…" : "Check"}</button>
      </form>
      <p className="mb-8 text-xs text-muted-foreground">
        Try:{" "}
        {EXAMPLES.map((x, i) => (
          <button key={i} className="mr-3 underline underline-offset-2 hover:text-foreground" onClick={() => { setClaim(x); run(x); }}>{x}</button>
        ))}
      </p>
      {res?.error && <p className="text-sm text-muted-foreground">{res.error}</p>}
      {res?.verdict && (
        <div>
          <p className="text-xl text-foreground">{LABEL[res.verdict] || res.verdict}</p>
          {res.explanation && <p className="mt-1 text-sm text-muted-foreground">{res.explanation}</p>}
          {res.basis && <p className="mt-1 text-xs text-muted-foreground">How: {res.basis}</p>}
          {res.evidence && res.evidence.length > 0 && (
            <ul className="mt-4 space-y-2">
              {res.evidence.map((e, i) => (
                <li key={i} className="text-sm leading-relaxed text-foreground/90">
                  {line(e)}{" "}
                  {e.source?.url && <a className="text-xs text-muted-foreground hover:underline" href={e.source.url}>[source]</a>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
