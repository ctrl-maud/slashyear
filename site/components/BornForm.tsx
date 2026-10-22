"use client";

import { useState } from "react";

const MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
  "september", "october", "november", "december"];

export default function BornForm({ first, last }: { first: number; last: number }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  return (
    <form
      className="mb-10 flex flex-wrap items-center gap-2 border border-border p-4 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
        if (!m) return setError("Pick a date.");
        const y = parseInt(m[1], 10);
        if (y < first || y > last) return setError(`Dates from ${first} to ${last} are covered.`);
        window.location.href = `/born/${y}#${MONTHS[parseInt(m[2], 10) - 1]}-${parseInt(m[3], 10)}`;
      }}
    >
      <label className="text-foreground" htmlFor="birthday">Your birthday</label>
      <input
        id="birthday"
        type="date"
        min={`${first}-01-01`}
        max={`${last}-12-31`}
        className="border border-border bg-background px-2 py-1"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setError("");
        }}
      />
      <button className="border border-border px-3 py-1 hover:bg-muted" type="submit">
        Show me
      </button>
      {error && <span className="text-muted-foreground">{error}</span>}
    </form>
  );
}
