import fs from "node:fs";
import path from "node:path";
import Game from "@/components/Game";
import SiteNav from "@/components/SiteNav";
import { breadcrumb, canonical, JsonLd, SITE, OG_IMAGE } from "@/lib/seo";

const title = "Guess the year: a daily history puzzle";
const description =
  "Five real events from one year, revealed one at a time. Guess the year in six tries. A new puzzle every day, every clue quoted from a cited Wikipedia revision.";

export const metadata = {
  title,
  description,
  alternates: { canonical: canonical("/play") },
  openGraph: { title, description, images: OG_IMAGE, url: canonical("/play") },
  twitter: { card: "summary_large_image", title, description, images: OG_IMAGE },
};

export default function Play() {
  const index = JSON.parse(
    fs.readFileSync(path.join(process.cwd(), "..", "data", "extras", "play", "index.json"), "utf8"),
  ) as { start: string; days: number };

  return (
    <main className="min-h-screen">
      <SiteNav>
        <span className="text-base text-foreground">/play</span>
      </SiteNav>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebApplication",
          name: "slashyear: guess the year",
          applicationCategory: "GameApplication",
          operatingSystem: "Any",
          offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
          url: canonical("/play"),
          isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.base },
          breadcrumb: breadcrumb([{ name: "Guess the year", path: "/play" }]),
        }}
      />
      <article className="mx-auto max-w-2xl px-5 py-10">
        <h1 className="mb-2 text-3xl font-normal text-foreground md:text-4xl">Guess the year</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Every clue is a real event from the same year. Each wrong guess tells you whether to go earlier or later
          and reveals another clue. Six guesses. New puzzle every day at midnight your time.
        </p>
        <Game start={index.start} days={index.days} />
      </article>
    </main>
  );
}
