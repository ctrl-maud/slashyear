import SiteNav from "@/components/SiteNav";
import { canonical, JsonLd, SITE, breadcrumb , OG_IMAGE } from "@/lib/seo";

const title = "Embed — put today in history on your own site";
const description =
  "One script tag drops the entries recorded on today's date into any page. No key, no account, no tracking, and it keeps working if we never speak again.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/embed") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/embed") },
};

const TAG = `<script src="${SITE.base}/embed.js" async></script>`;
const OPTS = `<div id="history"></div>
<script src="${SITE.base}/embed.js"
        data-target="#history"
        data-count="5"
        data-date="september-7" async></script>`;

export default function Embed() {
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
          url: canonical("/embed"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([
            { name: "Years", path: "/" },
            { name: "Embed", path: "/embed" },
          ]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Embed</h1>
        <p className="mb-10 text-sm leading-relaxed text-muted-foreground">
          Paste one line where you want it. The widget reads today&rsquo;s date on the
          reader&rsquo;s machine, pulls that day&rsquo;s entries from the{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="/api">
            open API
          </a>
          , and writes them into the page. About a kilobyte, no dependency, no cookie, no
          tracking of any kind.
        </p>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            The whole thing
          </h2>
          <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-border bg-foreground/5 p-4 text-xs leading-relaxed">
            <code>{TAG}</code>
          </pre>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            It renders where the tag sits. It inherits your fonts and colours because it sets
            almost no styles of its own.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 border-b border-border pb-2 text-lg font-medium text-foreground">
            If you want to place it yourself
          </h2>
          <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-border bg-foreground/5 p-4 text-xs leading-relaxed">
            <code>{OPTS}</code>
          </pre>
          <ul className="mt-4 flex flex-col gap-2 text-sm leading-relaxed text-muted-foreground">
            <li><code>data-target</code> — a CSS selector for the element to fill.</li>
            <li><code>data-count</code> — how many entries, spread across the day&rsquo;s span. Default 3.</li>
            <li><code>data-date</code> — pin a fixed day (<code>september-7</code>) instead of today.</li>
          </ul>
        </section>

        <footer className="mt-16 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          The widget prints a small credit line back to the day it used. That link is the whole
          price: the text is English Wikipedia&rsquo;s under{" "}
          <a className="underline underline-offset-2 hover:text-foreground" href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer nofollow">
            CC BY-SA 4.0
          </a>
          , so anything you publish from it carries the same licence and needs attribution — the
          credit line is that attribution.
        </footer>
      </article>
    </main>
  );
}
