import SiteNav from "@/components/SiteNav";
import { crossIndex } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE , OG_IMAGE } from "@/lib/seo";

const title = "Subjects — one thread of history at a time";
const description =
  "War, science, religion, money, disaster: the same sourced entries re-filed by what they are about, century by century. The subject each sentence belongs to is decided here, not on Wikipedia.";

export const metadata = {
  title, description,
  alternates: { canonical: canonical("/topic") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/topic") },
};

export default function Topics() {
  const { topics } = crossIndex();
  const total = topics.reduce((n, t) => n + t.total, 0);

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: title, description, url: canonical("/topic"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Subjects", path: "/topic" },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Subjects</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {total.toLocaleString()} entries sorted by what they are about rather than when they
          happened. A year page tells you everything about one year; these follow one thread
          across all of them.
        </p>
        <ul className="flex flex-col gap-3">
          {topics.map((t) => (
            <li className="text-sm text-foreground/85" key={t.slug}>
              <a className="underline underline-offset-2 hover:text-foreground" href={`/topic/${t.slug}`}>
                {t.label}
              </a>
              <span className="text-muted-foreground">
                {" "}— {t.total.toLocaleString()} entries across {t.centuries} centuries
              </span>
            </li>
          ))}
        </ul>
        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Births and deaths are left out of these lists: a person is not a subject, and a list of
          them per century is only Wikipedia&rsquo;s own layout again. They stay on the year and
          date pages.
        </footer>
      </article>
    </main>
  );
}
