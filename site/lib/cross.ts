import fs from "node:fs";
import path from "node:path";

/** The decade / century / topic cross-cuts written by pipeline/cross.py. Pages under the
 *  thinness floors in that script are never written, so every read here can come back
 *  null and every link must be guarded — a link to a page that was dropped is a 404 in
 *  our own graph, which is worse than no link. */
const CROSS = path.join(process.cwd(), "..", "data", "site", "cross");

export type Cite = { url: string; title: string; revid: number; section: string };
export type CrossItem = {
  year: number;
  year_label: string;
  section: string;
  date: string | null;
  text: string;
  cite: Cite;
  /** Only rows harvested from a country-year article ("1969 in Japan") carry this. */
  country?: string;
};
type Ref = { slug: string; label: string } | null;

export type DecadePage = {
  slug: string; label: string; key: number;
  century: Ref;
  years: { year: number; label: string; entries: number; lead_items: string[] }[];
  entries: number; prev: Ref; next: Ref;
};
export type CenturyPage = {
  slug: string; label: string; key: number;
  decades: { slug: string; label: string; key: number; entries: number; years: number }[];
  years: number; entries: number;
  topics: { slug: string; label: string; count: number }[];
  highlights: { year: number; label: string; text: string }[];
  prev: Ref; next: Ref;
};
export type TopicHub = {
  slug: string; label: string; total: number;
  centuries: { slug: string; label: string; count: number; span: [string, string] }[];
  highlights: CrossItem[];
};
export type TopicCentury = {
  topic: { slug: string; label: string };
  century: { slug: string; label: string };
  count: number; span: [string, string];
  items: CrossItem[];
  prev: Ref; next: Ref;
};
export type PlaceCentury = {
  slug: string; label: string; key: number;
  count: number; span: [string, string];
  items: CrossItem[];
};
export type PlaceHub = {
  slug: string; label: string; total: number;
  span: [string, string];
  centuries: PlaceCentury[];
};
export type CrossIndex = {
  centuries: { slug: string; label: string; years: number; entries: number; key: number }[];
  decades: { slug: string; label: string; years: number; entries: number; key: number; century: string | null }[];
  topics: { slug: string; label: string; total: number; centuries: number }[];
  places: { slug: string; label: string; total: number; centuries: number; span: [string, string] }[];
};

function read<T>(...parts: string[]): T | null {
  const file = path.join(CROSS, ...parts);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8")) as T;
}

export const crossIndex = (): CrossIndex => read<CrossIndex>("index.json")!;
export const readDecade = (slug: string) => read<DecadePage>("decade", `${slug}.json`);
export const readCentury = (slug: string) => read<CenturyPage>("century", `${slug}.json`);
export const readTopic = (slug: string) => read<TopicHub>("topic", `${slug}.json`);
export const readTopicCentury = (topic: string, century: string) =>
  read<TopicCentury>("topic", topic, `${century}.json`);
export const readPlace = (slug: string) => read<PlaceHub>("place", `${slug}.json`);

/** The same slug rule as slugify() in pipeline/cross.py. Written twice on purpose --
 *  the build has no shared runtime with the pipeline -- so any change goes in both. */
export const placeSlug = (country: string) =>
  country.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** Countries that actually got a page. A row can carry a country whose total fell under
 *  PLACE_MIN, and linking that row to /in/<slug> would be a 404 in our own graph. */
let placeSlugs: Set<string> | null = null;
export function hasPlace(country: string): boolean {
  placeSlugs ??= new Set((crossIndex().places ?? []).map((p) => p.slug));
  return placeSlugs.has(placeSlug(country));
}

/** year -> the decade and century page that actually exist for it, either possibly null. */
export type YearParents = { decade: Ref; century: Ref };
let parents: Record<string, YearParents> | null = null;
export function yearParents(year: number): YearParents {
  parents ??= read<Record<string, YearParents>>("years.json")!;
  return parents[String(year)] ?? { decade: null, century: null };
}

/** Every (topic, century) pair that was written, for generateStaticParams. */
export function topicCenturyParams(): { topic: string; century: string }[] {
  const out: { topic: string; century: string }[] = [];
  for (const t of crossIndex().topics) {
    const hub = readTopic(t.slug);
    for (const c of hub?.centuries ?? []) out.push({ topic: t.slug, century: c.slug });
  }
  return out;
}

export const yearPath = (year: number) => (year === 404 ? "/404/" : `/${year}`);

/** Does a (topic, century) page exist? Year pages link their section headings at it and
 *  must not emit a link to a bucket that fell under TOPIC_MIN. */
let pairs: Set<string> | null = null;
export function hasTopicCentury(topic: string, century: string): boolean {
  if (!pairs) pairs = new Set(topicCenturyParams().map((p) => `${p.topic}/${p.century}`));
  return pairs.has(`${topic}/${century}`);
}
