"use client";

import { useState } from "react";

import SiteNav from "./SiteNav";

/** Accepts what a person would actually type: 1066, 490BC, 490 BCE, 44 b.c., -489. */
export function parseYearInput(raw: string): number | null {
  const s = raw.trim().toLowerCase().replace(/[.\s]/g, "");
  if (!s) return null;
  const bce = /(bc|bce)$/.test(s);
  const digits = s.replace(/(bc|bce|ad|ce)$/, "");
  if (!/^-?\d{1,4}$/.test(digits)) return null;
  const n = parseInt(digits, 10);
  if (Number.isNaN(n) || n === 0) return null;
  // Site URLs use astronomical numbering: 3000 BCE is -2999.
  if (bce) return -(Math.abs(n) - 1);
  return n;
}

export default function YearNav({ value }: { value?: string }) {
  const [text, setText] = useState(value ?? "");

  return (
    <SiteNav>
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const y = parseYearInput(text);
          // A full navigation, not the app router: the site ships no RSC payloads,
          // so there is nothing for a client-side transition to fetch.
          if (y !== null) window.location.assign(`/${y}`);
        }}
      >
        <label htmlFor="year-input" className="sr-only">
          Year
        </label>
        <span className="select-none text-muted-foreground" aria-hidden="true">
          /
        </span>
        <input
          id="year-input"
          type="text"
          placeholder="e.g. 1066, 490BC"
          className="w-36 border-b border-transparent bg-transparent text-base text-foreground outline-none focus:border-foreground"
          autoComplete="off"
          spellCheck={false}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          type="submit"
          className="text-sm text-muted-foreground hover:text-foreground"
          aria-label="Go to year"
        >
          Go
        </button>
      </form>
    </SiteNav>
  );
}
