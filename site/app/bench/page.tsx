import fs from "node:fs";
import path from "node:path";
import SiteNav from "@/components/SiteNav";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

type Model = { n: number; accuracy: number; per_type: Record<string, number>; event_year_within_1?: number; n_errors?: number };
type Summary = { generated: string; n_items: number; n_by_type: Record<string, number>; models: Record<string, Model> };

const title = "SlashYear-Bench: how well AI models know dated history";
const description =
  "A closed-book test of what language models remember about dates: the year of an event, the Billboard No. 1 on a chart date, who held an office in a year, and what a dollar was worth. Every answer comes from a sourced record.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/bench") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/bench") },
};

const TYPES: Record<string, string> = {
  event_year: "Year of an event",
  number_one: "Billboard No. 1 on a chart date",
  leader: "Who held an office in a year",
  cpi: "What $100 was worth in another year",
};

const pct = (x: number | undefined) => (x == null ? "–" : `${(x * 100).toFixed(1)}%`);
const a = "underline underline-offset-2 hover:text-foreground";

function load(): Summary | null {
  const f = path.join(process.cwd(), "..", "data", "extras", "bench-summary.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf-8")) : null;
}

export default function BenchPage() {
  const s = load();
  if (!s) return null;
  const models = Object.entries(s.models).sort((x, y) => y[1].accuracy - x[1].accuracy);
  const types = Object.keys(s.n_by_type);
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/bench</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: "SlashYear-Bench",
          description,
          url: canonical("/bench"),
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          isAccessibleForFree: true,
          creator: { "@type": "Organization", name: SITE.name, url: SITE.base },
          distribution: [{ "@type": "DataDownload", encodingFormat: "application/x-ndjson", contentUrl: canonical("/api/bench/items.jsonl") }],
          breadcrumb: breadcrumb([{ name: "SlashYear-Bench", path: "/bench" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">SlashYear-Bench</h1>
        <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
          {s.n_items.toLocaleString("en-US")} questions about dated history, asked closed-book: the model gets the question
          and nothing else. Every answer key comes from the same sourced record as the rest of the site. Event sentences
          are quoted from a numbered Wikipedia revision with the date removed. Leaders are taken from the checked leader
          lists, No. 1 singles from the Hot 100 lists and dollar values from the BLS consumer price index. Each item
          carries the source it was built from.
        </p>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Questions and answers: <a className={a} href="/api/bench/items.jsonl">/api/bench/items.jsonl</a> · scores:{" "}
          <a className={a} href="/api/bench/summary.json">/api/bench/summary.json</a> · code:{" "}
          <a className={a} href="https://github.com/ctrl-maud/slashyear/tree/main/bench">bench/</a>. Run {s.generated}.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-normal">Model</th>
                <th className="py-2 pr-3 font-normal">Overall</th>
                {types.map((t) => (<th key={t} className="py-2 pr-3 font-normal">{TYPES[t] || t}</th>))}
              </tr>
            </thead>
            <tbody>
              {models.map(([m, v]) => (
                <tr key={m} className="border-b border-border/60">
                  <td className="py-2 pr-3 text-foreground">{m}</td>
                  <td className="py-2 pr-3 text-foreground">{pct(v.accuracy)}</td>
                  {types.map((t) => (<td key={t} className="py-2 pr-3 text-foreground/85">{pct(v.per_type[t])}</td>))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h2 className="mb-2 mt-10 text-lg text-foreground">The questions</h2>
        <ul className="space-y-2 text-sm leading-relaxed text-foreground/85">
          <li><span className="text-foreground">Year of an event</span> ({s.n_by_type.event_year}): a dated sentence with its date removed. Sentences that give away the year, or that appear under more than one year, are left out. Scored on the exact year. Also reported within one year.</li>
          <li><span className="text-foreground">Billboard No. 1</span> ({s.n_by_type.number_one}): the song at No. 1 on a chart issue date, 1958 on. Scored on the title.</li>
          <li><span className="text-foreground">Office holders</span> ({s.n_by_type.leader}): only state, post and year combinations with exactly one recorded holder, so there is one right answer.</li>
          <li><span className="text-foreground">Dollar values</span> ({s.n_by_type.cpi}): $100 in one year in another year&rsquo;s dollars, by the annual CPI-U. Correct within 3%.</li>
        </ul>
      </article>
    </main>
  );
}
