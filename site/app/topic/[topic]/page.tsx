import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import CrossEntry from "@/components/CrossEntry";
import { crossIndex, readTopic } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE, trim , OG_IMAGE } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return crossIndex().topics.map((t) => ({ topic: t.slug }));
}

function describe(p: NonNullable<ReturnType<typeof readTopic>>) {
  const span = p.centuries.length
    ? ` from the ${p.centuries[0].label} to the ${p.centuries[p.centuries.length - 1].label}`
    : "";
  return trim(`${p.label} across recorded history: ${p.total.toLocaleString()} sourced entries${span}, each quoted from the Wikipedia revision it came from.`);
}

export async function generateMetadata({ params }: { params: Promise<{ topic: string }> }) {
  const { topic } = await params;
  const p = readTopic(topic);
  if (!p) return { title: SITE.name };
  const title = `${p.label} — a timeline across every recorded century`;
  const description = describe(p);
  const url = canonical(`/topic/${p.slug}`);
  return {
    title, description,
    alternates: { canonical: url },
    openGraph: { title, description, images: OG_IMAGE, url, type: "article" },
    twitter: { card: "summary_large_image", title, description, images: OG_IMAGE },
  };
}

export default async function Topic({ params }: { params: Promise<{ topic: string }> }) {
  const { topic } = await params;
  const p = readTopic(topic);
  if (!p) notFound();

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "CollectionPage",
          name: `${p.label} through history`,
          description: describe(p),
          url: canonical(`/topic/${p.slug}`),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          about: { "@type": "Thing", name: p.label },
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Subjects", path: "/topic" },
            { name: p.label, path: `/topic/${p.slug}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">{p.label}</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {p.total.toLocaleString()} sourced entries filed under {p.label.toLowerCase()}, split by
          century. Each century below opens the full list for that stretch of time.
        </p>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            By century
          </h2>
          <ul className="flex flex-col gap-2">
            {p.centuries.map((c) => (
              <li className="text-sm text-foreground/85" key={c.slug}>
                <a className="underline underline-offset-2 hover:text-foreground" href={`/topic/${p.slug}/${c.slug}`}>
                  {p.label} in the {c.label}
                </a>
                <span className="text-muted-foreground"> — {c.count.toLocaleString()} entries</span>
              </li>
            ))}
          </ul>
        </section>

        {p.highlights.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
              A line from each of the last few centuries
            </h2>
            <ul className="flex flex-col gap-3">
              {p.highlights.map((item, k) => (
                <CrossEntry item={item} key={k} />
              ))}
            </ul>
          </section>
        )}

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Which subject a sentence belongs to is decided here; the sentence itself is English
          Wikipedia&rsquo;s, quoted at the revision linked beside it and reused under{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer nofollow">
            CC BY-SA 4.0
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
