
/** The bar that is on every page. It carries the cross-links that make the site a
 *  connected graph rather than a heap of orphans: the year directory, the calendar, the
 *  subject threads and the century hierarchy. */
export default function SiteNav({ children }: { children?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-background">
      {/* Four links plus the year box do not fit on a phone in one row: without wrapping,
          "On this day" broke over three lines and "Centuries" ran off the screen. */}
      <div className="mx-auto flex max-w-2xl flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3">
        {children}
        <nav className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 whitespace-nowrap text-sm text-muted-foreground">
          <a className="hover:text-foreground" href="/">
            Years
          </a>
          <a className="hover:text-foreground" href="/on">
            On this day
          </a>
          <a className="hover:text-foreground" href="/topic">
            Subjects
          </a>
          <a className="hover:text-foreground" href="/timeline">
            Timelines
          </a>
          <a className="hover:text-foreground" href="/century">
            Centuries
          </a>
          <a className="hover:text-foreground" href="/data">
            Data
          </a>
        </nav>
      </div>
    </header>
  );
}
