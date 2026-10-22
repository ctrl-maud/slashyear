import fs from "node:fs";
import path from "node:path";

const FACTS = path.join(process.cwd(), "..", "data", "extras", "facts");

export type Origin = { name: string; publisher?: string; url: string; license: string; series?: string };

export type Holder = { qid: string; name: string; start: string; end?: string | null; acting?: boolean; approx?: boolean };
export type Office = {
  role: "head_of_state" | "head_of_government";
  office: string;
  office_qid: string;
  also_head_of_government: boolean;
  holders: Holder[];
};
export type StateRow = { state: string; qid: string; slug: string; page: boolean; offices: Office[] };

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
  leaders?: { key: StateRow[]; source: Origin & { retrieved: string }; checked: string };
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

export function roleLabel(o: Office): string {
  if (o.role === "head_of_state") return o.also_head_of_government ? "Head of state and government" : "Head of state";
  return "Head of government";
}

/** "Richard Nixon" or "Lyndon B. Johnson, then Richard Nixon (from January 20)" for the
 *  holders of one office during one year. */
export function holderLine(o: Office, year: number): string {
  return o.holders
    .map((h, i) => {
      const from = h.start.startsWith(`${year}-`) && i > 0 && !h.approx ? ` (from ${longDate(h.start).replace(`, ${year}`, "")})` : "";
      return `${h.name}${h.acting ? " (acting)" : ""}${from}`;
    })
    .join(", then ");
}

export const wd = (qid: string) => `https://www.wikidata.org/wiki/${qid}`;
