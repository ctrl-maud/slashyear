import type { LeaderRow, LifeDayRow, LifeYearRow, NobelRow } from "@/lib/disagreements";
import { yearLabel } from "@/lib/disagreements";

const src = "text-xs text-muted-foreground underline-offset-2 hover:underline";

export function LifeYears({ rows }: { rows: LifeYearRow[] }) {
  return (
    <ul className="space-y-3">
      {rows.map((r, i) => (
        <li key={i} className="text-sm leading-relaxed">
          <span className="text-foreground">{r.person}</span>
          <span className="text-muted-foreground"> · {r.kind}</span>
          {r.approximate && <span className="text-muted-foreground"> · the article marks the date as uncertain</span>}
          <br />
          <span className="text-foreground/85">
            Wikipedia&rsquo;s {yearLabel(r.wikipedia_says)} article: &ldquo;{r.wikipedia_text}&rdquo;{" "}
            {r.wikipedia_source && <a className={src} href={r.wikipedia_source.url}>[rev {r.wikipedia_source.revid}]</a>}
          </span>
          <br />
          <span className="text-foreground/85">Wikidata: {r.wikidata_says.map(yearLabel).join(" or ")}</span>
        </li>
      ))}
    </ul>
  );
}

export function LifeDays({ rows }: { rows: LifeDayRow[] }) {
  return (
    <ul className="space-y-3">
      {rows.map((r, i) => (
        <li key={i} className="text-sm leading-relaxed">
          <span className="text-foreground">{r.person}</span>
          <span className="text-muted-foreground"> · {r.kind}, {yearLabel(r.year)} · {r.difference_days} days apart</span>
          <br />
          <span className="text-foreground/85">
            Wikipedia: {r.wikipedia_says}{" "}
            {r.wikipedia_source && <a className={src} href={r.wikipedia_source.url}>[{r.wikipedia_source.title}, rev {r.wikipedia_source.revid}]</a>}
            {" "}· Wikidata: {r.wikidata_says.join(" or ")}
          </span>
          {r.calendar_note && <><br /><span className="text-xs text-muted-foreground">{r.calendar_note}</span></>}
        </li>
      ))}
    </ul>
  );
}

export function Leaders({ rows }: { rows: LeaderRow[] }) {
  return (
    <ul className="space-y-3">
      {rows.map((r, i) => (
        <li key={i} className="text-sm leading-relaxed">
          <span className="text-foreground">{r.person}</span>
          <span className="text-muted-foreground"> · {r.state}</span>
          <br />
          <span className="text-foreground/85">
            Wikipedia&rsquo;s list: &ldquo;{r.wikipedia_quote}&rdquo;{" "}
            {r.wikipedia_source?.url && <a className={src} href={r.wikipedia_source.url}>[{r.wikipedia_source.article}, rev {r.wikipedia_source.revid}]</a>}
          </span>
          <br />
          <span className="text-foreground/85">
            Wikidata: {r.wikidata_says.map((t) => `${t.post} ${t.start}–${t.end}`).join("; ")}{" "}
            <a className={src} href={r.wikidata_url}>[{r.wikidata}]</a>
          </span>
          {r.note && <><br /><span className="text-xs text-muted-foreground">{r.note}</span></>}
        </li>
      ))}
    </ul>
  );
}

export function Nobel({ rows }: { rows: NobelRow[] }) {
  return (
    <ul className="space-y-3">
      {rows.map((r, i) => (
        <li key={i} className="text-sm leading-relaxed text-foreground/85">
          <span className="text-foreground">{r.name}</span>, {r.category} {r.year}
          <br />Nobel Prize API: {r.nobel_api} · Wikidata: {r.wikidata}
          {r.wikidata_item && <><br /><span className="text-xs text-muted-foreground">The API&rsquo;s Wikidata link points to {r.wikidata_item}</span></>}
        </li>
      ))}
    </ul>
  );
}
