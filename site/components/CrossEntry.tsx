import type { CrossItem } from "@/lib/cross";
import { hasPlace, placeSlug, yearPath } from "@/lib/cross";
import { readable } from "@/lib/display";

/** One re-filed sentence, as it appears on a topic page: the year it belongs to as a
 *  link back to its own page, the sentence exactly as the source wrote it, and the
 *  revision it was quoted from. */
export default function CrossEntry({ item }: { item: CrossItem }) {
  return (
    <li className="text-sm leading-relaxed text-foreground/85">
      <a
        className="mr-2 tabular-nums text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground hover:decoration-solid"
        href={yearPath(item.year)}
      >
        {item.year_label.replace(/ CE$/, "")}
      </a>
      {readable(item.text)}
      {item.country && hasPlace(item.country) && (
        <a
          className="ml-1 whitespace-nowrap rounded-sm border border-border px-1 text-[10px] text-muted-foreground hover:text-foreground"
          href={`/in/${placeSlug(item.country)}`}
        >
          {item.country}
        </a>
      )}
      <a
        href={item.cite.url}
        target="_blank"
        rel="noreferrer nofollow"
        title={`${item.cite.title} — ${item.cite.section} (revision ${item.cite.revid})`}
        className="ml-1 align-super text-[10px] text-muted-foreground hover:text-foreground hover:underline"
      >
        source
      </a>
    </li>
  );
}
