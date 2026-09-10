import AskBox from "@/components/AskBox";
import SiteNav from "@/components/SiteNav";
import { breadcrumb, canonical, JsonLd, SITE } from "@/lib/seo";

const title = "Ask History — a sourced answer to a question about the past";
const description =
  "Ask how one thing led to another and get a chronological answer built only from dated entries published on this site, every sentence cited to the Wikipedia revision it was frozen from.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/ask") },
  openGraph: { title, description, url: canonical("/ask") },
};

export default function Ask() {
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebPage",
          name: title,
          description,
          url: canonical("/ask"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Ask History", path: "/ask" },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Ask History</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Ask a question that spans years rather than one that has a single answer — how one
          thing led to another, what two places were doing at the same time, what followed an
          event. The answer is assembled only from the dated entries this site already
          publishes, and every sentence is numbered back to the one it came from. Where the
          record does not connect two things, it says so instead of guessing.
        </p>
        <AskBox />
        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          The model arranges sourced sentences; it is not asked what it knows, and it is
          instructed not to add anything the sources do not say. That is a real limit, not a
          disclaimer: a question the 121,493 published entries do not cover will get a short
          answer saying so. The whole index is open without a question at{" "}
          <a className="underline underline-offset-2" href="/api/search?q=eruption">
            /api/search
          </a>
          , and in bulk at{" "}
          <a className="underline underline-offset-2" href="/dump/datapackage.json">
            /dump
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
