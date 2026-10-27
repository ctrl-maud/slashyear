import SiteNav from "@/components/SiteNav";
import CheckClaim from "@/components/CheckClaim";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

const title = "Check a historical claim against the sourced record";
const description =
  "Type a dated sentence and see what the record says: who held an office that year, which song was No. 1, who won a Nobel Prize, or where the record dates an event, with the source of each line.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/check") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/check") },
};

export default function CheckPage() {
  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/check</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebApplication",
          name: title,
          description,
          url: canonical("/check"),
          applicationCategory: "ReferenceApplication",
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([{ name: "Check a claim", path: "/check" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-4 text-3xl font-normal text-foreground md:text-4xl">Check a claim</h1>
        <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
          Leaders, Billboard No. 1 singles and Nobel Prizes are checked against the structured record, which is complete
          enough to say a claim is wrong. Anything else is matched against the dated entries, and the answer only says
          where the record dates sentences that hold the claim&rsquo;s key words. No model writes the verdict.
        </p>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          For programs: <a className="underline underline-offset-2 hover:text-foreground" href="/api/check?claim=Richard%20Nixon%20was%20president%20in%201975">/api/check?claim=…</a> and
          the MCP tool <code>check_claim</code>.
        </p>
        <CheckClaim />
      </article>
    </main>
  );
}
