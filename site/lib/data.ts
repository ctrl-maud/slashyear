import fs from "node:fs";
import path from "node:path";

const DATA = path.join(process.cwd(), "..", "data", "site");

export type Cite = {
  url: string;
  title: string;
  revid: number;
  section: string;
};

export type Item = { date: string | null; text: string; cite: Cite };
export type Section = { title: string; items: Item[] };

export type Source = {
  title: string;
  url: string;
  permalink: string;
  revid: number;
  license: string;
  retrieved: string;
};

export type YearPage = {
  year: number;
  label: string;
  lead: string;
  sections: Section[];
  counts: { shown: number; available: number };
  source: Source;
  /** Wikipedia moved the deaths of 1977 onward out of the year article and into
      "Deaths in <month> <year>". Those bullets cite their own revision, so the page
      footer has to name every article it quotes, not just the year one. */
  extra_sources?: Source[];
};

export type IndexRow = { year: number; label: string; sections: number; entries: number };

export function readIndex(): { years: IndexRow[]; total: number; span: [string, string] } {
  return JSON.parse(fs.readFileSync(path.join(DATA, "index.json"), "utf8"));
}

export function readYear(year: string): YearPage | null {
  const file = path.join(DATA, `${year}.json`);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

export function allYears(): number[] {
  return readIndex().years.map((r) => r.year);
}
