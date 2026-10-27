import SiteNav from "@/components/SiteNav";
import { LifeDays } from "@/components/Ledger";
import { ledger } from "@/lib/disagreements";
import { breadcrumb, canonical, JsonLd, OG_IMAGE } from "@/lib/seo";

const title = "Birth and death days where Wikipedia and Wikidata disagree";
const description =
  "People whose birth or death day in Wikipedia's year articles differs from the day Wikidata gives, from 1583 on, with the article revision and both dates.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/disagreements/birth-death-days") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/disagreements/birth-death-days") },
};

export default function LifeDayDisagreements() {
  const d = ledger();
  if (!d) return null;
  const dd = d.sections.life_days;
  return (
    <main className="min-h-screen">
      <SiteNav>
        <a className="text-base text-muted-foreground hover:text-foreground" href="/disagreements">/disagreements</a>
        <span className="text-base text-foreground">/birth-death-days</span>
      </SiteNav>
      <JsonLd data={{ "@context": "https://schema.org", "@type": "WebPage", name: title, description, url: canonical("/disagreements/birth-death-days"),
        breadcrumb: breadcrumb([{ name: "Where the sources disagree", path: "/disagreements" }, { name: "Birth and death days", path: "/disagreements/birth-death-days" }]) }} />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">{title}</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Rule: {dd.rule}, from 1583, the first full year of the Gregorian calendar. A gap of 10 to 13 days is the size of the
          Julian/Gregorian difference, so those rows are marked: one source may be giving the old-style date.
        </p>
        <LifeDays rows={dd.rows} />
      </article>
    </main>
  );
}
