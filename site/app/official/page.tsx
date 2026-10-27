import fs from "node:fs";
import path from "node:path";
import SiteNav from "@/components/SiteNav";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

type Series = {
  name: string; unit: string; frequency: string; publisher: string; url: string; license: string; annual_method?: string;
  cross_check?: { against: string; url?: string; points_compared?: number; max_abs_diff?: number; tolerance?: number; passed?: boolean };
  annual: Record<string, number>;
};
type Doc = { retrieved: string; series: Record<string, Series> };

const title = "Official U.S. and scientific data series by year, cross-checked";
const description =
  "Unemployment, interest rates, GDP, population, federal debt, CO2, global temperature and exchange rates by year, straight from the agencies that publish them and checked against a second copy.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/official") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/official") },
};

function load(): Doc | null {
  const f = path.join(process.cwd(), "..", "data", "extras", "official.json");
  return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf-8")) : null;
}

const a = "underline underline-offset-2 hover:text-foreground";

export default function OfficialPage() {
  const d = load();
  if (!d) return null;
  const ids = Object.keys(d.series);
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/official</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: title,
          description,
          url: canonical("/official"),
          isAccessibleForFree: true,
          creator: { "@type": "Organization", name: SITE.name, url: SITE.base },
          distribution: ids.map((id) => ({ "@type": "DataDownload", encodingFormat: "application/json", contentUrl: canonical(`/api/official/${id}.json`) })),
          breadcrumb: breadcrumb([{ name: "Official data", path: "/official" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Official data by year</h1>
        <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
          Each series comes from the agency that publishes it and is checked against a second copy of the same data
          before it goes out. A series that failed its check was left out. Every value also appears on that year&rsquo;s{" "}
          <a className={a} href="/api/facts/1985.json">facts record</a> and in <a className={a} href="/asof">the world on a date</a>.
          Index: <a className={a} href="/api/official/index.json">/api/official/index.json</a>. Retrieved {d.retrieved}.
        </p>
        <ul className="mb-10 text-sm text-foreground/85">
          {ids.map((id) => (<li key={id}><a className={a} href={`#${id}`}>{d.series[id].name}</a></li>))}
        </ul>
        {ids.map((id) => {
          const s = d.series[id];
          const ys = Object.keys(s.annual).sort((x, y) => +y - +x);
          return (
            <section key={id} id={id} className="mb-10">
              <h2 className="mb-1 text-lg text-foreground">{s.name}</h2>
              <p className="mb-1 text-xs text-muted-foreground">
                {s.unit}. Source: <a className={a} href={s.url}>{s.publisher}</a> ({s.license}).
                {s.annual_method ? ` Annual value: ${s.annual_method}.` : ""}
              </p>
              {s.cross_check && (
                <p className="mb-2 text-xs text-muted-foreground">
                  Checked against {s.cross_check.url ? <a className={a} href={s.cross_check.url}>{s.cross_check.against}</a> : s.cross_check.against}
                  {s.cross_check.points_compared != null ? `: ${s.cross_check.points_compared} values compared` : ""}
                  {s.cross_check.max_abs_diff != null ? `, largest difference ${s.cross_check.max_abs_diff}` : ""}.
                </p>
              )}
              <p className="mb-2 text-xs"><a className={a} href={`/api/official/${id}.json`}>/api/official/{id}.json</a></p>
              <div className="grid grid-cols-3 gap-x-4 text-sm tabular-nums text-foreground/85 sm:grid-cols-4">
                {ys.map((y) => (<span key={y}><span className="text-muted-foreground">{y}</span> {s.annual[y].toLocaleString("en-US")}</span>))}
              </div>
            </section>
          );
        })}
      </article>
    </main>
  );
}
