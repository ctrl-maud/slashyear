import SiteNav from "@/components/SiteNav";
import AsOf from "@/components/AsOf";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

const title = "The world on any date: events, leaders, prices and the No. 1 song";
const description =
  "Pick a date and see what the sourced record holds for it: what happened that day, who was in office that year, the Billboard No. 1, prices, exchange rates and world population, each with its source.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/asof") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/asof") },
};

export default function AsOfPage() {
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/asof</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebApplication",
          name: title,
          description,
          url: canonical("/asof"),
          applicationCategory: "ReferenceApplication",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([{ name: "The world on a date", path: "/asof" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">The world on a date</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          One date, everything the record holds for it. Each line is quoted from a numbered Wikipedia revision or
          taken from the agency that publishes the figure, and anything the sources don&rsquo;t cover is left out. The
          same answer is at <a className="underline underline-offset-2 hover:text-foreground" href="/api/asof/1969-07-20">/api/asof/1969-07-20</a> and
          in the MCP tool <code>get_world_on_date</code>.
        </p>
        <AsOf />
      </article>
    </main>
  );
}
