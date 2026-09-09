import { notFound } from "next/navigation";
import SiteNav from "@/components/SiteNav";
import CrossEntry from "@/components/CrossEntry";
import { readTopicCentury, topicCenturyParams } from "@/lib/cross";
import { breadcrumb, canonical, JsonLd, SITE, trim } from "@/lib/seo";

export const dynamicParams = false;

export function generateStaticParams() {
  return topicCenturyParams();
}

function describe(p: NonNullable<ReturnType<typeof readTopicCentury>>) {
  const head = `${p.topic.label} in the ${p.century.label}: ${p.count.toLocaleString()} sourced entries from ${p.span[0]} to ${p.span[1]}`;
  return trim(`${head}. ${p.items[0].year_label} — ${p.items[0].text}`);
}

export async function generateMetadata({ params }: { params: Promise<{ topic: string; century: string }> }) {
  const { topic, century } = await params;
  const p = readTopicCentury(topic, century);
  if (!p) return { title: SITE.name };
  const title = `${p.topic.label} in the ${p.century.label} — a sourced timeline`;
  const description = describe(p);
  const url = canonical(`/topic/${p.topic.slug}/${p.century.slug}`);
  return {
    title, description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "article" },
    twitter: { title, description },
  };
}

export default async function TopicCentury({ params }: { params: Promise<{ topic: string; century: string }> }) {
  const { topic, century } = await params;
  const p = readTopicCentury(topic, century);
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
          name: `${p.topic.label} in the ${p.century.label}`,
          description: describe(p),
          url: canonical(`/topic/${p.topic.slug}/${p.century.slug}`),
          inLanguage: "en",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          about: { "@type": "Thing", name: `${p.topic.label} in the ${p.century.label}` },
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Subjects", path: "/topic" },
            { name: p.topic.label, path: `/topic/${p.topic.slug}` },
            { name: p.century.label, path: `/topic/${p.topic.slug}/${p.century.slug}` },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">
          {p.topic.label} in the {p.century.label}
        </h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          {p.count.toLocaleString()} sourced entries, {p.span[0]} to {p.span[1]}, oldest first.
          Also see{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href={`/topic/${p.topic.slug}`}>
            {p.topic.label} across every century
          </a>{" "}
          or{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href={`/century/${p.century.slug}`}>
            everything else in the {p.century.label}
          </a>
          .
        </p>

        <ul className="mb-10 flex flex-col gap-3">
          {p.items.map((item, k) => (
            <CrossEntry item={item} key={k} />
          ))}
        </ul>

        <nav className="mb-10 flex justify-between text-sm" aria-label="Same subject, nearby centuries">
          {p.prev ? (
            <a className="underline underline-offset-2 hover:text-foreground" href={`/topic/${p.topic.slug}/${p.prev.slug}`}>
              ← {p.prev.label}
            </a>
          ) : <span />}
          {p.next ? (
            <a className="underline underline-offset-2 hover:text-foreground" href={`/topic/${p.topic.slug}/${p.next.slug}`}>
              {p.next.label} →
            </a>
          ) : <span />}
        </nav>

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
