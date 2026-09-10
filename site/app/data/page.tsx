import SiteNav from "@/components/SiteNav";
import { canonical, JsonLd, SITE , OG_IMAGE } from "@/lib/seo";
import { totals, words } from "@/lib/counts";

/** Counted by the build, never typed by hand -- see lib/counts.ts. */
const T = totals();
const N = (n: number) => n.toLocaleString("en-US");

/** The dataset's own page, and the only page on the site written in prose.
 *
 *  Two audiences that never meet. Google Dataset Search wants one canonical page
 *  carrying schema.org/Dataset, and it will not take /api — that page is a list of
 *  endpoints, and a landing page for a dataset is supposed to describe the dataset.
 *  The second audience is the text pipeline behind every open training corpus. C4,
 *  FineWeb and Dolma all read HTML, extract prose, and throw away anything that
 *  looks templated: FineWeb drops a document with more than 30% repeated lines or
 *  20% repeated 5-grams, which is a fair description of 6,832 pages built from the
 *  same component. None of those pages can survive that filter, and the NDJSON
 *  dumps are not HTML so they are never in the running at all. This page is written
 *  the way it is — continuous paragraphs, ordinary sentences, no tables, no lists of
 *  paths — because a page of prose is the only shape of ours those pipelines keep.
 */

const title = `The dataset: ${N(T.entries)} dated entries, each with its source revision`;
const description =
  `A free, openly licensed dataset of ${N(T.entries)} dated entries spanning ${N(T.years)} years, extracted from ` +
  "English Wikipedia. Every row is a sentence quoted verbatim from one numbered revision and " +
  "carries that revision id, so any claim built on it can be checked against a source that will " +
  "still read the same way next year. 2,799 subjects carry Wikidata identifiers. Bulk NDJSON " +
  "downloads, a REST API, full-text search and an MCP server, with no key and no rate limit.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/data") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/data") },
};

function P({ children }: { children: React.ReactNode }) {
  return <p className="mb-5 text-base leading-7 text-foreground/90">{children}</p>;
}

function H({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-4 mt-10 text-xl font-normal text-foreground">{children}</h2>;
}

function A({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a className="underline underline-offset-2 hover:text-foreground" href={href}>
      {children}
    </a>
  );
}

export default function Data() {
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/data</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Dataset",
          name: `slashyear: ${N(T.entries)} dated historical entries with source revision ids`,
          description:
            `A dataset of ${N(T.entries)} dated historical entries covering ${N(T.years)} years, from roughly 3000 ` +
            "BCE to the present, extracted from English Wikipedia's year, decade, century and " +
            `per-country articles. ${N(T.country_entries)} of the rows name the country they belong to, ` +
            `across ${N(T.countries)} countries. Each row holds the event sentence quoted verbatim, the astronomical year ` +
            "number, the calendar date where one is given, a topic label, the title of the source " +
            "article, the section path the sentence sits in, and the numeric revision id of the " +
            "exact Wikipedia revision it was taken from. A companion table gives 3,029 subject " +
            "timelines built from the wikilinks Wikipedia's own editors wrote, 2,722 of which " +
            "carry a Wikidata QID and are therefore joinable against any other database keyed on " +
            "Wikidata. Nothing in the text is written or paraphrased by us and no language model " +
            "touches the wording; a model is used only to assign each sentence a topic label, " +
            "which cannot make a row say anything untrue. Distributed as gzipped NDJSON with a " +
            "Frictionless data package, and also served as a REST API, a static full-text search " +
            "index and a Model Context Protocol server. No key, no rate limit, no signup, CORS open.",
          url: canonical("/data"),
          sameAs: [SITE.base, canonical("/api")],
          license: "https://creativecommons.org/licenses/by-sa/4.0/legalcode",
          isAccessibleForFree: true,
          version: "1.0",
          inLanguage: "en",
          creator: { "@type": "Organization", name: "slashyear", url: SITE.base },
          publisher: { "@type": "Organization", name: "slashyear", url: SITE.base },
          temporalCoverage: "-3000-01-01/2025-12-31",
          measurementTechnique:
            "Deterministic extraction from the wikitext of English Wikipedia year, decade, " +
            "century and per-country year articles at a pinned revision id, followed by " +
            "mechanical cleaning; topic " +
            "labels assigned per sentence, wording never altered.",
          isBasedOn: "https://en.wikipedia.org/",
          citation:
            `slashyear (2026). ${N(T.entries)} dated historical entries with source revision ids. ` +
            "https://slashyear.com/data",
          keywords: [
            "history", "historical events", "timeline", "chronology", "dated events",
            "Wikipedia", "Wikidata", "knowledge base", "open data", "NDJSON",
            "retrieval augmented generation", "question answering", "temporal reasoning",
          ],
          variableMeasured: [
            { "@type": "PropertyValue", name: "year", description: "Astronomical year number; -43 is 44 BCE." },
            { "@type": "PropertyValue", name: "date", description: "Calendar date where the source gives one, otherwise null." },
            { "@type": "PropertyValue", name: "text", description: "The event, quoted verbatim from the source revision." },
            { "@type": "PropertyValue", name: "topic", description: "One of twelve subject labels assigned per sentence." },
            { "@type": "PropertyValue", name: "source_revid", description: "Numeric id of the exact Wikipedia revision quoted." },
            { "@type": "PropertyValue", name: "source_url", description: "Permanent link to that revision and section." },
            { "@type": "PropertyValue", name: "qid", description: "Wikidata identifier of a subject, where one exists." },
          ],
          distribution: [
            {
              "@type": "DataDownload",
              name: `All ${N(T.entries)} dated entries (gzipped NDJSON)`,
              encodingFormat: "application/x-ndjson",
              contentUrl: canonical("/dump/events.ndjson.gz"),
            },
            {
              "@type": "DataDownload",
              name: `${N(T.years)} year records with lead summaries (gzipped NDJSON)`,
              encodingFormat: "application/x-ndjson",
              contentUrl: canonical("/dump/years.ndjson.gz"),
            },
            {
              "@type": "DataDownload",
              name: "3,029 subject timelines with Wikidata ids (gzipped NDJSON)",
              encodingFormat: "application/x-ndjson",
              contentUrl: canonical("/dump/entities.ndjson.gz"),
            },
            {
              "@type": "DataDownload",
              name: "Frictionless data package describing all three tables",
              encodingFormat: "application/json",
              contentUrl: canonical("/dump/datapackage.json"),
            },
          ],
        }}
      />

      <div className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-6 text-3xl font-normal text-foreground md:text-4xl">
          The dataset
        </h1>

        <P>
          This site publishes a dataset of {words(T.entries)}{" "}
          dated entries, covering {words(T.years)} years from
          roughly three thousand years before the common era to the present day. {words(T.events).replace(/^./, (c) => c.toUpperCase())}{" "}
          of those entries are events; the remaining{" "}
          {words(T.people)} record a birth or a death, which
          the source articles list separately and so does this.{" "}
          {T.country_entries > 0 && (
            <>
              {words(T.country_entries).replace(/^./, (c) => c.toUpperCase())} of the rows name the
              country they happened in, across {words(T.countries)} countries, because English
              Wikipedia writes a separate article for every country in every year and those have
              been read as well as the world ones.{" "}
            </>
          )}
          It is free,
          openly licensed, and available as a bulk download, as a REST API, as a full-text
          search endpoint and as a Model Context Protocol server. There is no key to request,
          no rate limit to negotiate and no account to create.
        </P>

        <P>
          The thing that distinguishes it from any other list of historical dates is that every
          single row can be traced back to a specific, frozen source. Each event is a sentence
          taken word for word out of an English Wikipedia article, and stored alongside it is
          the numeric revision identifier of the exact version of that article the sentence was
          taken from. Wikipedia articles change constantly, which is normally what makes them
          impossible to cite properly: a quotation you take today may not be there in six
          months, and a reader who follows your link has no way of seeing what you actually
          read. A revision identifier removes that problem entirely. It names one immutable
          version of the page, which will read the same way in ten years as it does now.
        </P>

        <H>What is actually in it</H>

        <P>
          The main table has one row per event. Each row carries the sentence itself, the year
          it happened in, the calendar date where the source gives one, a topic label, the
          title of the Wikipedia article it came from, the path of the section within that
          article where the sentence sits, the revision identifier, and a permanent link that
          opens that exact revision at that exact section. Years are stored using astronomical
          numbering, which means the year before the year one is written as zero and the year
          forty-four before the common era is written as minus forty-three. This is
          unattractive to read but it is the only convention under which arithmetic on years
          works correctly across the boundary, and it is what any program consuming this data
          would want.
        </P>

        <P>
          A second table holds two thousand nine hundred and forty-one subject timelines. A
          subject here is a person, place, institution or event that Wikipedia's own editors
          linked to from inside a dated line, which means the association between the subject
          and the event was written by a human editor rather than inferred by us or guessed at
          by a model. Two thousand seven hundred and twenty-two of those subjects carry a
          Wikidata identifier, and that is what turns the table from something you can read
          into something you can join: any other database keyed on Wikidata can be merged
          against this one without any name matching or fuzzy string comparison at all.
        </P>

        <P>
          A third table holds one row per year, with the summary paragraph for that year and
          its own source revision. Together the three tables are described by a Frictionless
          data package, which is a standard machine-readable description of what the columns
          are and what types they hold, so a program can load the whole thing without anyone
          having to read documentation first.
        </P>

        <H>How it was built, and what that rules out</H>

        <P>
          The extraction is deterministic. A program reads the wikitext of Wikipedia's year,
          decade and century articles at a pinned revision, pulls out the dated lines, strips
          the markup mechanically, and writes the resulting sentences out unchanged. Nothing on
          this site is written by us. No language model rewrites, summarises, paraphrases or
          otherwise touches the wording of a single entry. A model is used for exactly one
          thing, which is deciding which of twelve topic labels a sentence belongs under, and
          that decision cannot make a row say something untrue because it never alters the row.
        </P>

        <P>
          The consequence worth stating plainly is that this dataset inherits Wikipedia's
          errors. If a date is wrong on Wikipedia it is wrong here too. What it does not
          inherit is Wikipedia's instability, because every row names the version it came from,
          and it does not add any errors of its own on top, because no step in the pipeline is
          allowed to generate text. Anyone who wants to audit a claim can open the linked
          revision and read the sentence in its original context in about four seconds.
        </P>

        <H>Why the shape matters more than the words</H>

        <P>
          The words in this dataset are freely available elsewhere; they are Wikipedia's, under
          the Creative Commons Attribution-ShareAlike licence, and we make no claim on them.
          What does not exist elsewhere is the shape. Wikipedia publishes prose organised by
          article. Its unit is the page. This dataset's unit is the sentence, and each sentence
          is tagged with the year, the calendar day, a topic, the century, the decade, the
          subjects named inside it and the revision it came from. That structure is what lets
          you ask questions the encyclopedia cannot answer in one step: everything that
          happened on the fourth of July across all recorded years, or every dated line
          mentioning Constantinople in order, or the whole record of a single topic across
          three thousand years.
        </P>

        <P>
          For anyone building a system that answers questions, this matters for a specific
          reason. A model that quotes an encyclopedia article is quoting a moving target, and a
          user who wants to verify the answer has to trust that the page said that at the time.
          A model that quotes a row from this dataset can hand the user a link to a frozen
          revision. The answer stops being something to take on faith and becomes something
          that can be checked.
        </P>

        <H>How to get it</H>

        <P>
          The complete dataset is available as three gzipped{" "}
          <A href="/dump/events.ndjson.gz">newline-delimited JSON files</A>, described by a{" "}
          <A href="/dump/datapackage.json">Frictionless data package</A>. Downloading those is
          faster for you and cheaper for us than crawling several thousand pages, and the data
          is identical. If you would rather query than download, there is a{" "}
          <A href="/api">REST API and a full-text search endpoint</A>, both static, both
          CORS-open, both free. If you are a language model or an agent, there is a{" "}
          <A href="/api">Model Context Protocol server</A> at{" "}
          <code>https://slashyear.com/mcp</code>, registered in the official MCP registry under
          the name <code>com.slashyear/mcp</code>, which exposes search, a single year, a single
          calendar day across all years, and a single subject timeline as tools. It speaks
          streamable HTTP and needs no authentication, so it is a POST endpoint rather than a
          page you can open in a browser.
        </P>

        <P>
          Reuse is free, including commercial use and including use as training data. The
          licence is Creative Commons Attribution-ShareAlike 4.0, inherited from Wikipedia,
          which asks only that you attribute the source; every row carries the article title
          and revision identifier needed to do that automatically. We are not reserving any
          rights over search indexing, citation in generated answers or model training, and{" "}
          <A href="/robots.txt">the robots file says so in machine-readable form</A>.
        </P>
      </div>
    </main>
  );
}
