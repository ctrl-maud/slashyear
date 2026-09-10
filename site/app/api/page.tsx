import SiteNav from "@/components/SiteNav";
import { canonical, JsonLd, SITE , OG_IMAGE } from "@/lib/seo";

const title = "API, bulk download and MCP server — sourced history as data";
const description =
  "Free, static, CORS-open JSON for every year, day, subject and timeline; the whole corpus as a gzipped download; and an MCP server for models. No key, no rate limit, no signup.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/api") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/api") },
};

function Row({ path, note }: { path: string; note: string }) {
  return (
    <li className="text-sm leading-relaxed text-foreground/85">
      <a
        className="underline underline-offset-2 hover:text-foreground"
        href={path}
      >
        <code>{path}</code>
      </a>
      <span className="text-muted-foreground"> — {note}</span>
    </li>
  );
}

export default function Api() {
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/year</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: "slashyear — the year-by-year historical record, sourced line by line",
          description:
            "Every dated entry published on slashyear.com: a sentence quoted verbatim from a " +
            "numbered English Wikipedia revision, with that revision id, the article title and " +
            "the section it came from. Years, calendar days, subjects and per-subject timelines.",
          url: canonical("/api"),
          sameAs: canonical("/"),
          license: "https://creativecommons.org/licenses/by-sa/4.0/",
          isAccessibleForFree: true,
          creator: { "@type": "Organization", name: "slashyear", url: SITE.base },
          keywords: ["history", "timeline", "chronology", "events", "Wikipedia", "open data"],
          temporalCoverage: "-3000/2025",
          distribution: [
            {
              "@type": "DataDownload",
              name: "All entries (NDJSON, gzipped)",
              encodingFormat: "application/x-ndjson",
              contentUrl: canonical("/dump/events.ndjson.gz"),
            },
            {
              "@type": "DataDownload",
              name: "Year records (NDJSON, gzipped)",
              encodingFormat: "application/x-ndjson",
              contentUrl: canonical("/dump/years.ndjson.gz"),
            },
            {
              "@type": "DataDownload",
              name: "Subject timelines (NDJSON, gzipped)",
              encodingFormat: "application/x-ndjson",
              contentUrl: canonical("/dump/entities.ndjson.gz"),
            },
            {
              "@type": "DataDownload",
              name: "Frictionless data package",
              encodingFormat: "application/json",
              contentUrl: canonical("/dump/datapackage.json"),
            },
          ],
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">
          API, bulk download and MCP
        </h1>
        <p className="mb-6 text-sm leading-relaxed text-muted-foreground">
          Everything on this site is also a static JSON file. No key, no rate limit, no account,
          CORS open to any origin. Each entry carries the exact Wikipedia revision id its sentence
          was quoted from, so anything you build on it can be checked back to a source rather than
          taken on trust.
        </p>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          That last part is the whole point of taking this rather than scraping an encyclopedia
          article. An article is a moving target: quote it today and the sentence may not be there
          next year, which makes the citation worthless. A revision id never changes.
        </p>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            Endpoints
          </h2>
          <ul className="flex flex-col gap-3">
            <Row path="/api/year/1066.json" note="one year: lead, sections, entries, citations" />
            <Row path="/api/date/september-7.json" note="one calendar day across every year" />
            <Row path="/api/years.json" note="the index of every published year" />
            <Row path="/api/dates.json" note="the index of all 366 dates" />
            <Row path="/api/century/11th-century.json" note="one century: its decades, subjects and highlights" />
            <Row path="/api/decade/1060s.json" note="one decade: its years and their leading entries" />
            <Row path="/api/topic/science-and-discovery.json" note="one subject across every century" />
            <Row path="/api/topic/science-and-discovery/17th-century.json" note="one subject inside one century" />
            <Row path="/api/cross.json" note="the index of every century, decade and subject" />
            <Row path="/api/index.json" note="the endpoint list, as JSON" />
            <Row path="/api/openapi.json" note="OpenAPI 3.1 document" />
          </ul>
          <h3 className="mb-3 mt-8 text-sm font-medium text-foreground">Subject timelines</h3>
          <ul className="flex flex-col gap-3">
            <Row path="/api/entity/constantinople.json" note="one subject: every dated entry naming it, in order, with its Wikidata id" />
            <Row path="/api/entities.json" note="the index of every subject that has a timeline" />
            <Row path="/api/search?q=plague&from=1300&to=1400" note="subjects matching a query and their dated entries — the one endpoint that computes" />
          </ul>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Years use astronomical numbering, the same as the URLs: <code>/api/year/-43.json</code>{" "}
            is 44 BCE. The subject and century slugs are the ones in the page URLs, so anything you
            can read you can also fetch. There is also a{" "}
            <a className="underline underline-offset-2 hover:text-foreground" href="/embed">
              one-tag embed
            </a>{" "}
            if you only want today&rsquo;s entries on a page.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            Take the whole thing
          </h2>
          <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
            You do not have to crawl this site to have it. The entire corpus is three gzipped
            newline-delimited JSON files, refreshed with every build, free for any use including
            training and redistribution. Downloading them is cheaper for you and for us than
            fetching several thousand pages, and it is the version we would rather you cited.
          </p>
          <ul className="flex flex-col gap-3">
            <Row path="/dump/events.ndjson.gz" note="every dated entry, one JSON object per line" />
            <Row path="/dump/years.ndjson.gz" note="one record per year, with its source revision" />
            <Row path="/dump/entities.ndjson.gz" note="one record per subject timeline" />
            <Row path="/dump/datapackage.json" note="Frictionless data package describing all three" />
            <Row path="/llms.txt" note="what this site is, for a machine that found it on its own" />
          </ul>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            MCP server
          </h2>
          <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
            <code>{`${SITE.base}/mcp`}</code> is a Model Context Protocol server over streamable
            HTTP. No key, no account, no session. Point any MCP client at it and a model gets five
            tools — <code>search_history</code>, <code>get_year</code>, <code>get_day</code>,{" "}
            <code>get_timeline</code>, <code>list_subjects</code> — that return rows carrying the
            revision id each sentence came from, so the answer it writes can cite something that
            will still say the same thing next year.
          </p>
          <pre className="overflow-x-auto rounded border border-border bg-foreground/5 p-4 text-xs leading-relaxed">
            <code>{`claude mcp add --transport http slashyear ${SITE.base}/mcp`}</code>
          </pre>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            Example
          </h2>
          <pre className="overflow-x-auto rounded border border-border bg-foreground/5 p-4 text-xs leading-relaxed">
            <code>{`curl -s ${SITE.base}/api/date/september-7.json \\
  | jq '.groups[0].items[0]'`}</code>
          </pre>
        </section>

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          The text is English Wikipedia&rsquo;s, reused under{" "}
          <a
            className="underline underline-offset-2 hover:text-foreground"
            href="https://creativecommons.org/licenses/by-sa/4.0/"
            target="_blank"
            rel="noreferrer nofollow"
          >
            CC BY-SA 4.0
          </a>
          , so anything you publish from it carries the same licence and needs the same
          attribution. The per-entry <code>cite</code> object is that attribution.{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="/">
            Back to the directory
          </a>
          .
        </footer>
      </article>
    </main>
  );
}
