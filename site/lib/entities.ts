import fs from "node:fs";
import path from "node:path";
import type { Cite } from "@/lib/cross";

/** The entity cross-cut written by pipeline/entities.py: every published sentence in
 *  which Wikipedia's own editors linked to a given subject, in chronological order.
 *  Only entities that cleared the floor in that script have a file here, so every read
 *  can come back null and every link out must be guarded. */
const DIR = path.join(process.cwd(), "..", "data", "site", "entities");

export type EntityItem = {
  year: number;
  year_label: string;
  section: string;
  date: string | null;
  text: string;
  cite: Cite;
};

export type EntityPage = {
  slug: string;
  label: string;
  wikipedia: string;
  wikidata: string | null;
  qid: string | null;
  description: string | null;
  entries: number;
  years: number;
  span: [number, number];
  span_label: [string, string];
  topics: { title: string; count: number }[];
  /** Other spellings Wikipedia redirects to this subject, merged in by entities.py. */
  also_known_as?: string[];
  related: { slug: string; label: string; shared: number }[];
  items: EntityItem[];
};

/** Timelines under this many entries are published and crawlable but carry
 *  `noindex, follow` and stay out of the sitemap. Search Console (2026-09-28) had every
 *  URL discovered and few indexed: thousands of near-empty timelines were diluting the
 *  site. pipeline/postbuild.py and pipeline/audit.py hold the same number as
 *  THIN_TIMELINE, and audit fails if the three ever disagree. */
export const THIN_TIMELINE = 20;

export type EntityRow = {
  slug: string;
  label: string;
  qid: string | null;
  description: string | null;
  entries: number;
  years: number;
  span_label: [string, string];
};

export function entityIndex(): { count: number; entities: EntityRow[] } {
  const f = path.join(DIR, "index.json");
  if (!fs.existsSync(f)) return { count: 0, entities: [] };
  return JSON.parse(fs.readFileSync(f, "utf8"));
}

export function readEntity(slug: string): EntityPage | null {
  const f = path.join(DIR, `${slug}.json`);
  if (!fs.existsSync(f)) return null;
  return JSON.parse(fs.readFileSync(f, "utf8"));
}
