import SiteNav from "@/components/SiteNav";
import { LifeYears } from "@/components/Ledger";
import { ledger } from "@/lib/disagreements";
import { breadcrumb, canonical, JsonLd, OG_IMAGE } from "@/lib/seo";

const title = "Birth and death dates where Wikipedia and Wikidata disagree";
const description =
  "People whose birth or death Wikipedia's year articles file under a different year or day than Wikidata gives, with the article revision and both dates.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/disagreements/births-deaths") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/disagreements/births-deaths") },
};

export default function LifeDisagreements() {
  const d = ledger();
  if (!d) return null;
  const y = d.sections.life_years;
  const rows = y.rows.filter((r) => !r.approximate).sort((a, b) => b.wikipedia_says - a.wikipedia_says);
  const approx = y.rows.length - rows.length;
  return (
    <main className="min-h-screen">
      <SiteNav>
        <a className="text-base text-muted-foreground hover:text-foreground" href="/disagreements">/disagreements</a>
        <span className="text-base text-foreground">/births-deaths</span>
      </SiteNav>
      <JsonLd data={{ "@context": "https://schema.org", "@type": "WebPage", name: title, description, url: canonical("/disagreements/births-deaths"),
        breadcrumb: breadcrumb([{ name: "Where the sources disagree", path: "/disagreements" }, { name: "Births and deaths", path: "/disagreements/births-deaths" }]) }} />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">{title}</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Only rows where the person is the subject of the sentence are kept, so &ldquo;grandson of X&rdquo; never counts
          as a date for X. The {approx} rows where the article itself marks the date as approximate are left off this
          page and kept in <a className="underline underline-offset-2 hover:text-foreground" href="/api/disagreements.json">the JSON</a>.
          Same year but a different day: <a className="underline underline-offset-2 hover:text-foreground" href="/disagreements/birth-death-days">birth and death days</a>.
        </p>
        <h2 className="mb-1 text-lg text-foreground">Different years</h2>
        <p className="mb-4 text-xs text-muted-foreground">{y.rule}. Newest first.</p>
        <LifeYears rows={rows} />
      </article>
    </main>
  );
}
