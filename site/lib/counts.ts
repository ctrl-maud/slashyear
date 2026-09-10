import { readIndex } from "@/lib/data";

/** What the dataset actually contains, counted by pipeline/build.py while it writes the
 *  pages and carried in index.json. The /data page is written as prose and states these
 *  numbers in words; hand-writing them is how that page came to claim 86,322 entries
 *  across 2,960 years while the site was serving 86,902 across 3,078. */
export type Totals = {
  entries: number;
  events: number;
  people: number;
  years: number;
  country_entries: number;
  countries: number;
};

export function totals(): Totals {
  const idx = readIndex() as unknown as { totals?: Totals; years: { entries: number }[]; total: number };
  if (idx.totals) return idx.totals;
  // An older index.json, from before build.py counted these.
  const entries = idx.years.reduce((n, r) => n + r.entries, 0);
  return { entries, events: entries, people: 0, years: idx.total, country_entries: 0, countries: 0 };
}

const ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
  "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
  "eighteen", "nineteen"];
const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];

function under1000(n: number): string {
  if (n < 20) return ONES[n];
  if (n < 100) return TENS[Math.floor(n / 10)] + (n % 10 ? `-${ONES[n % 10]}` : "");
  const rest = n % 100;
  return `${ONES[Math.floor(n / 100)]} hundred${rest ? ` and ${under1000(rest)}` : ""}`;
}

/** Numbers written the way the /data page writes them, because that page is prose and a
 *  wall of digits is what makes a page read as a table to the text pipelines it is for. */
export function words(n: number): string {
  if (n < 0) return `minus ${words(-n)}`;
  if (n < 1000) return under1000(n);
  const parts: string[] = [];
  const scales: [number, string][] = [[1_000_000, "million"], [1000, "thousand"]];
  let left = n;
  for (const [size, name] of scales) {
    if (left >= size) {
      parts.push(`${under1000(Math.floor(left / size))} ${name}`);
      left %= size;
    }
  }
  if (left) parts.push(left < 100 ? `and ${under1000(left)}` : under1000(left));
  return parts.join(" ");
}
