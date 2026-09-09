/** One place for everything a search engine reads but a reader never sees.
 *
 *  The site's problem is specific: every sentence on a year page is quoted verbatim
 *  from the Wikipedia article of the same name, so to a crawler a year page looks like
 *  a copy of a page that already outranks it by twenty years of inbound links. Nothing
 *  here changes that. What it does is make the parts that ARE ours legible — the
 *  cross-cut date pages, the citation down to a revision id, the link graph between
 *  years and days — and stop the avoidable losses: no canonical, duplicate boilerplate
 *  descriptions on 2,960 pages, and www serving the same page as the apex.
 */
export const SITE = {
  base: "https://slashyear.com",
  name: "slashyear",
  blurb:
    "Every recorded year, and every calendar day, as sourced entries — each sentence quoted from a specific Wikipedia revision you can open.",
};

/** URLs are canonical without a trailing slash, except /404/, which is served from a
 *  directory index because the bare 404.html has to stay the not-found page. */
export const canonical = (path: string) => SITE.base + path;

export function trim(text: string, max = 155): string {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  const cut = flat.slice(0, max);
  return cut.slice(0, cut.lastIndexOf(" ")).replace(/[,;:—–-]+$/, "") + "…";
}

export function JsonLd({ data }: { data: unknown }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  );
}

export function breadcrumb(trail: { name: string; path: string }[]) {
  return {
    "@type": "BreadcrumbList",
    itemListElement: trail.map((t, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: t.name,
      item: canonical(t.path),
    })),
  };
}
