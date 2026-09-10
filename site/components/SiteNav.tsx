/** The bar that is on every page.
 *
 *  Grouped by what the reader is trying to do, not by what routes happen to exist. Seven
 *  flat links read as seven unrelated products; every one of them is in fact a way of
 *  entering the same corpus, so they live behind one "Explore" menu. New destinations get
 *  added to a group here, never as another top-level button.
 *
 *  The menu is a <details> element on purpose: the site ships as a static export with no
 *  client runtime on most pages, and <details> opens without JavaScript.
 */
const EXPLORE = [
  { href: "/century", label: "Centuries", hint: "the long view" },
  { href: "/in", label: "Countries", hint: "one place through time" },
  { href: "/topic", label: "Subjects", hint: "one thread through time" },
  { href: "/timeline", label: "Timelines", hint: "curated runs of events" },
  { href: "/on", label: "On this day", hint: "any calendar date" },
  { href: "/data", label: "Data", hint: "download the whole corpus" },
];

export default function SiteNav({ children }: { children?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-background">
      <div className="mx-auto flex max-w-2xl flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3">
        {children}
        <nav className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 whitespace-nowrap text-sm text-muted-foreground">
          <details className="group relative">
            <summary className="cursor-pointer list-none hover:text-foreground [&::-webkit-details-marker]:hidden">
              Explore <span aria-hidden="true">▾</span>
            </summary>
            {/* Right-aligned so the panel never runs off a phone screen. */}
            <div className="absolute right-0 top-full z-20 mt-2 w-60 border border-border bg-background p-2 shadow-sm">
              <ul>
                {EXPLORE.map((item) => (
                  <li key={item.href}>
                    <a
                      className="block px-2 py-1.5 hover:bg-muted hover:text-foreground"
                      href={item.href}
                    >
                      <span className="text-foreground">{item.label}</span>
                      <span className="block text-xs text-muted-foreground">{item.hint}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </details>
          <a className="hover:text-foreground" href="/ask">
            Ask History
          </a>
          <a className="hover:text-foreground" href="/">
            Years
          </a>
        </nav>
      </div>
    </header>
  );
}
