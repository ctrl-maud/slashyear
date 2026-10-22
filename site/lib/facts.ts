import fs from "node:fs";
import path from "node:path";

const FACTS = path.join(process.cwd(), "..", "data", "extras", "facts");

export type Origin = { name: string; publisher?: string; url: string; license: string; series?: string };

export type Holder = { name: string; person: string; qid: string; title: string | null; office: string | null; quote: string };
export type StateRow = {
  state: string;
  region: string | null;
  country: string;
  wikipedia: string | null;
  key: string | null;
  holders: Holder[];
};
export type Leaders = {
  states: StateRow[];
  source: { name: string; title: string; revid: number; url: string; license: string; retrieved: string };
  checked: string;
};

export type PriceItem = {
  id: string;
  label: string;
  unit: string;
  then: number;
  then_in_today_dollars: number;
  now: number;
  now_date: string;
  source: Origin;
};

export type Facts = {
  year: number;
  population?: { value: number; source: Origin };
  prices?: {
    cpi: number;
    cpi_now: number;
    cpi_now_date: string;
    dollar_today: number;
    cpi_source: Origin;
    items: PriceItem[];
  };
  births?: Birth[];
  leaders?: Leaders;
  hot100?: {
    weeks: { date: string; title: string; artist: string }[];
    songs: { title: string; artist: string; weeks: number }[];
    source: { year: number; title: string; revid: number; url: string; license: string; retrieved: string } | null;
  };
};

export type Birth = { text: string; person: string; cite: { url: string; title: string; revid: number } };

export type FactsRow = { year: number; population: boolean; prices: boolean; leaders: number; hot100: boolean };

export function factsIndex(): FactsRow[] {
  const file = path.join(FACTS, "index.json");
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, "utf8")).years;
}

export function readFacts(year: number): Facts | null {
  const file = path.join(FACTS, `${year}.json`);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

/** Years with enough outside data to carry a page of their own. */
export const bornYears = () => factsIndex().filter((r) => r.prices).map((r) => r.year);

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];

export function monthYear(iso: string): string {
  return `${MONTHS[parseInt(iso.slice(5, 7), 10) - 1]} ${iso.slice(0, 4)}`;
}

export function longDate(iso: string): string {
  return `${MONTHS[parseInt(iso.slice(5, 7), 10) - 1]} ${parseInt(iso.slice(8, 10), 10)}, ${iso.slice(0, 4)}`;
}

export function money(v: number): string {
  if (v >= 1000) return "$" + Math.round(v).toLocaleString("en-US");
  if (v >= 100) return "$" + v.toFixed(0);
  return "$" + v.toFixed(2);
}


export function people(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} billion`;
  return `${Math.round(n / 1e6).toLocaleString("en-US")} million`;
}

/** Years that have a world-leaders page. */
export const leaderYears = () => factsIndex().filter((r) => r.leaders > 0).map((r) => r.year);

/** The panel's states, in the order of the countries readers ask about first. */
export function keyStates(l: Leaders | undefined): StateRow[] {
  const order = ["United States", "United Kingdom", "Russia", "China", "France", "Germany", "Japan", "India"];
  return (l?.states ?? []).filter((s) => s.key).sort((a, b) => order.indexOf(a.key!) - order.indexOf(b.key!));
}

/** The panel's first `n` countries; East and West Germany count as one. */
export function panelStates(l: Leaders | undefined, n = 6): StateRow[] {
  const all = keyStates(l);
  const keys = Array.from(new Set(all.map((s) => s.key))).slice(0, n);
  return all.filter((s) => keys.includes(s.key));
}

/** The list's own name for the state unless it is a mouthful ("United Kingdom of Great
 *  Britain and Northern Ireland", "France: Fifth Republic"). */
export const stateLabel = (s: StateRow) =>
  s.key && (s.state.length > 30 || s.state.includes(":")) ? s.key : s.state;

/** One state's holders grouped by post, in list order:
 *  [["Queen", ["Elizabeth II"]], ["Prime minister", ["Harold Wilson", "Edward Heath"]]]. */
export function posts(s: StateRow): [string, string[]][] {
  const out: [string, string[]][] = [];
  for (const h of s.holders) {
    const label = h.title || h.office || "";
    const row = out.find(([t]) => t.toLowerCase() === label.toLowerCase());
    if (row) {
      if (!row[1].includes(h.name)) row[1].push(h.name);
    } else out.push([label, [h.name]]);
  }
  return out;
}

/** "Elizabeth II (Queen); Harold Wilson, then Edward Heath (Prime minister)" */
export function postsLine(s: StateRow): string {
  return posts(s)
    .map(([t, names]) => `${names.join(", then ")}${t ? ` (${t})` : ""}`)
    .join("; ");
}

export const wiki = (title: string) => `https://en.wikipedia.org/wiki/${encodeURIComponent(title.replace(/ /g, "_"))}`;

export const wd = (qid: string) => `https://www.wikidata.org/wiki/${qid}`;
