import SiteNav from "@/components/SiteNav";
import { crossIndex } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE } from "@/lib/seo";

const title = "Countries — the same history, one nation at a time";
const description =
  "English Wikipedia writes a separate article for every country in every year and no index across them. These are those rows, gathered per country and per century, each sentence quoted from the revision it came from.";

export const metadata = {
  title, description,
  alternates: { canonical: canonical("/in") },
  openGraph: { title, description, url: canonical("/in") },
};

export default function Places() {
  const places = crossIndex().places ?? [];
  const total = places.reduce((n, p) => n + p.total, 0);

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: title, description, url: canonical("/in"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Countries", path: "/in" },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Countries</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {total.toLocaleString()} entries that name the country they happened in, across{" "}
          {places.length} of them. A world year article has room for a few dozen lines a year for
          the whole planet, and what fits is mostly written in English about English-speaking
          places. These rows come from the country articles instead, where a year in Japan or
          Brazil or Nigeria gets a page of its own.
        </p>
        <ul className="flex flex-col gap-3">
          {places.map((p) => (
            <li className="text-sm text-foreground/85" key={p.slug}>
              <a className="underline underline-offset-2 hover:text-foreground" href={`/in/${p.slug}`}>
                {p.label}
              </a>
              <span className="text-muted-foreground">
                {" "}— {p.total.toLocaleString()} entries, {p.span[0]} to {p.span[1]}
              </span>
            </li>
          ))}
        </ul>
        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          A country here is the one whose article the sentence was quoted from, not a judgement
          about borders: &ldquo;1969 in Japan&rdquo; is a Wikipedia article, and every row taken
          from it is filed under Japan. Rows quoted from the world year articles carry no country
          at all and are not listed here.
        </footer>
      </article>
    </main>
  );
}
