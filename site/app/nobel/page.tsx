import fs from "node:fs";
import path from "node:path";
import SiteNav from "@/components/SiteNav";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

type Prize = { category: string; name: string; motivation?: string; nobel_url?: string; prize_status?: string };
type Doc = { retrieved: string; years: Record<string, Prize[]>; not_awarded: Record<string, string[]>; source: { url: string } };

const title = "Every Nobel Prize by year, checked against Wikidata";
const description =
  "Every Nobel laureate from 1901, in Physics, Chemistry, Physiology or Medicine, Literature, Peace and Economic Sciences, from the Nobel Prize's own data and kept only where Wikidata records the same prize in the same year.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/nobel") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/nobel") },
};

function load(): Doc | null {
  const f = path.join(process.cwd(), "..", "data", "extras", "nobel.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf-8")) : null;
}

export default function NobelPage() {
  const d = load();
  if (!d) return null;
  const years = Array.from(new Set([...Object.keys(d.years), ...Object.keys(d.not_awarded)])).map(Number).sort((a, b) => b - a);
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/nobel</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: title,
          description,
          url: canonical("/nobel"),
          license: "https://creativecommons.org/publicdomain/zero/1.0/",
          isAccessibleForFree: true,
          creator: { "@type": "Organization", name: SITE.name, url: SITE.base },
          distribution: [{ "@type": "DataDownload", encodingFormat: "application/json", contentUrl: canonical("/api/nobel.json") }],
          breadcrumb: breadcrumb([{ name: "Nobel Prizes", path: "/nobel" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Nobel Prizes by year</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          From the <a className="underline underline-offset-2 hover:text-foreground" href={d.source.url}>Nobel Prize API</a> (CC0),
          kept only where Wikidata independently records the same prize in the same year. The two cases where they
          disagree are on <a className="underline underline-offset-2 hover:text-foreground" href="/disagreements">where the sources disagree</a>.
          Data: <a className="underline underline-offset-2 hover:text-foreground" href="/api/nobel.json">/api/nobel.json</a>.
        </p>
        {years.map((y) => (
          <section key={y} className="mb-6" id={String(y)}>
            <h2 className="mb-2 text-base font-medium text-foreground">{y <= 2025 ? <a className="hover:underline" href={`/${y}`}>{y}</a> : y}</h2>
            <ul className="space-y-1 text-sm text-foreground/85">
              {(d.years[String(y)] || []).map((p, i) => (
                <li key={i}>
                  <span className="text-muted-foreground">{p.category}:</span>{" "}
                  {p.nobel_url ? <a className="underline-offset-2 hover:underline" href={p.nobel_url}>{p.name}</a> : p.name}
                  {p.prize_status && <span className="text-muted-foreground"> ({p.prize_status})</span>}
                  {p.motivation && <span className="text-muted-foreground"> {p.motivation}</span>}
                </li>
              ))}
              {(d.not_awarded[String(y)] || []).length > 0 && (
                <li className="text-muted-foreground">Not awarded: {d.not_awarded[String(y)].join(", ")}</li>
              )}
            </ul>
          </section>
        ))}
      </article>
    </main>
  );
}
