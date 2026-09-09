import fs from "node:fs";
import path from "node:path";

const DATES = path.join(process.cwd(), "..", "data", "site", "dates");

export type DateItem = {
  year: number;
  year_label: string;
  kind: string;
  section: string;
  text: string;
  cite: { url: string; title: string; revid: number; section: string };
};
export type DatePage = {
  slug: string;
  label: string;
  month: string;
  day: number;
  groups: { title: string; items: DateItem[] }[];
  count: number;
  span: [string, string] | null;
  years: number[];
};
export type DateRow = { slug: string; label: string; month: string; day: number; count: number };

export function readDateIndex(): { dates: DateRow[]; total: number } {
  return JSON.parse(fs.readFileSync(path.join(DATES, "index.json"), "utf8"));
}

export function readDate(slug: string): DatePage | null {
  const file = path.join(DATES, `${slug}.json`);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];
const LENGTHS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const DAY_DATE = new RegExp(`^(${MONTHS.join("|")}) (\\d{1,2})$`);

/** The link target for an entry's own date, or null when the source only gave a month
 *  ("June", "June–November"). Must agree with pipeline/dates.py or a year page would
 *  link to a date page that was never built. */
export function dateHref(date: string | null): string | null {
  if (!date) return null;
  const m = DAY_DATE.exec(date);
  if (!m) return null;
  const day = parseInt(m[2], 10);
  if (day < 1 || day > LENGTHS[MONTHS.indexOf(m[1])]) return null;
  return `/on/${m[1].toLowerCase()}-${day}`;
}

export { MONTHS, LENGTHS };
