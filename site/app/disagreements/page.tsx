import SiteNav from "@/components/SiteNav";
import { LifeYears, Nobel } from "@/components/Ledger";
import { ledger } from "@/lib/disagreements";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

const title = "Where the sources disagree: Wikipedia vs Wikidata vs the Nobel Prize record";
const description =
  "The dates slashyear refused to publish because two sources it checks against each other disagree: leaders' terms, birth and death years, and Nobel Prizes, with what each source says and where.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/disagreements") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/disagreements") },
};

const a = "underline underline-offset-2 hover:text-foreground";

export default function Disagreements() {
  const d = ledger();
  if (!d) return null;
  const s = d.sections;
  const modern = s.life_years.rows.filter((r) => !r.approximate && r.wikipedia_says >= 1700).sort((x, y) => x.wikipedia_says - y.wikipedia_says);
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/disagreements</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: "Where historical sources disagree",
          description,
          url: canonical("/disagreements"),
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          isAccessibleForFree: true,
          creator: { "@type": "Organization", name: SITE.name, url: SITE.base },
          distribution: [{ "@type": "DataDownload", encodingFormat: "application/json", contentUrl: canonical("/api/disagreements.json") }],
          breadcrumb: breadcrumb([{ name: "Where the sources disagree", path: "/disagreements" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Where the sources disagree</h1>
        <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
          slashyear checks its dates against a second, independent source. This page lists the cases where the
          two disagree. Each row shows what each source says and links to the exact revision or record. It
          doesn&rsquo;t say which one is right. Some rows are errors in Wikipedia and some are errors in Wikidata,
          and the links are there so anyone can check. Leaders&rsquo; terms and Nobel Prizes go out only where the
          sources agree. Birth and death lines are still quoted on year pages as Wikipedia prints them.
        </p>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          The whole ledger is at <a className={a} href="/api/disagreements.json">/api/disagreements.json</a>. Full lists:{" "}
          <a className={a} href="/disagreements/leaders">leaders&rsquo; terms</a> ·{" "}
          <a className={a} href="/disagreements/births-deaths">birth and death years</a> ·{" "}
          <a className={a} href="/disagreements/birth-death-days">birth and death days</a>.
        </p>

        <h2 className="mb-1 mt-8 text-lg text-foreground">Births and deaths since 1700, firm dates only</h2>
        <p className="mb-4 text-xs text-muted-foreground">{s.life_years.rule}.</p>
        <LifeYears rows={modern} />

        <h2 className="mb-1 mt-10 text-lg text-foreground">Nobel Prizes</h2>
        <p className="mb-4 text-xs text-muted-foreground">{s.nobel.rule}.</p>
        <Nobel rows={s.nobel.rows} />

        <h2 className="mb-1 mt-10 text-lg text-foreground">The rest</h2>
        <ul className="text-sm leading-relaxed text-foreground/85">
          <li><a className={a} href="/disagreements/leaders">{s.leaders.title}</a></li>
          <li><a className={a} href="/disagreements/births-deaths">{s.life_years.title}</a></li>
          <li><a className={a} href="/disagreements/birth-death-days">{s.life_days.title}</a></li>
        </ul>
      </article>
    </main>
  );
}
