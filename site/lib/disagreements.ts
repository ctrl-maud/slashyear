import fs from "node:fs";
import path from "node:path";

const FILE = path.join(process.cwd(), "..", "data", "extras", "disagreements.json");

export type WpSource = { url: string; title?: string; article?: string; revid: number } | null;
export type LeaderRow = {
  state: string; person: string; post: string | null; wikidata: string; wikipedia_says: string; wikipedia_quote: string;
  wikipedia_source: WpSource; wikidata_says: { post: string; start: number; end: number }[]; wikidata_url: string;
  difference_years: number; note: string | null;
};
export type LifeYearRow = {
  kind: "birth" | "death"; person: string; wikipedia_says: number; wikidata_says: number[]; wikipedia_text: string;
  wikipedia_source: WpSource; difference_years: number; approximate: boolean;
};
export type LifeDayRow = {
  kind: "birth" | "death"; person: string; year: number; wikipedia_says: string; wikidata_says: string[];
  wikipedia_text: string; wikipedia_source: WpSource; difference_days: number; calendar_note: string | null;
};
export type NobelRow = { year: number; category: string; name: string; qid: string; nobel_api: string; wikidata: string; reason: string; wikidata_item?: string; wikidata_recipients_that_year?: string[] };
type Section<T> = { title: string; rule: string; count: number; rows: T[] };
export type Ledger = {
  generated: string;
  what: string;
  sections: { leaders: Section<LeaderRow>; life_years: Section<LifeYearRow>; life_days: Section<LifeDayRow>; nobel: Section<NobelRow> };
};

export function ledger(): Ledger | null {
  if (!fs.existsSync(FILE)) return null;
  return JSON.parse(fs.readFileSync(FILE, "utf-8"));
}

export const yearLabel = (y: number) => (y <= 0 ? `${1 - y} BC` : String(y));
