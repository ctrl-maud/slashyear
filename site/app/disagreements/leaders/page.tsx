import SiteNav from "@/components/SiteNav";
import { Leaders } from "@/components/Ledger";
import { ledger } from "@/lib/disagreements";
import { breadcrumb, canonical, JsonLd, OG_IMAGE } from "@/lib/seo";

const title = "Leaders' terms where Wikipedia and Wikidata disagree";
const description =
  "Heads of state and government whose term in Wikipedia's lists of state leaders doesn't match the same office's dates in Wikidata, with both sources quoted and linked.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/disagreements/leaders") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/disagreements/leaders") },
};

export default function LeaderDisagreements() {
  const d = ledger();
  if (!d) return null;
  const s = d.sections.leaders;
  return (
    <main className="min-h-screen">
      <SiteNav>
        <a className="text-base text-muted-foreground hover:text-foreground" href="/disagreements">/disagreements</a>
        <span className="text-base text-foreground">/leaders</span>
      </SiteNav>
      <JsonLd data={{ "@context": "https://schema.org", "@type": "WebPage", name: title, description, url: canonical("/disagreements/leaders"),
        breadcrumb: breadcrumb([{ name: "Where the sources disagree", path: "/disagreements" }, { name: "Leaders", path: "/disagreements/leaders" }]) }} />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">{s.title}</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Rule: {s.rule}. Rows are ordered by how far apart the two sources are. None of these holder-years is
          published on the <a className="underline underline-offset-2 hover:text-foreground" href="/leaders">leaders pages</a>.
        </p>
        <Leaders rows={s.rows} />
      </article>
    </main>
  );
}
