"use client";

import { useEffect, useMemo, useState } from "react";

type Clue = { text: string; cite: { url: string; title: string; revid: number } };
type Puzzle = { number: number; date: string; year: number; clues: Clue[] };
type Saved = { guesses: number[]; done: boolean };

const MAX = 6;

function localISO(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function mark(guess: number, year: number) {
  const off = Math.abs(guess - year);
  const square = off === 0 ? "🟩" : off <= 10 ? "🟨" : off <= 50 ? "🟧" : "🟥";
  return { square, arrow: off === 0 ? "" : guess < year ? "⬆️" : "⬇️", off };
}

/** Five sourced lines from one year, one revealed per wrong guess. The answer ships in the
 *  day's JSON since a static site has nowhere else to keep it. */
export default function Game({ start, days }: { start: string; days: number }) {
  const [date, setDate] = useState<string | null>(null);
  const [puzzle, setPuzzle] = useState<Puzzle | null>(null);
  const [missing, setMissing] = useState(false);
  const [saved, setSaved] = useState<Saved>({ guesses: [], done: false });
  const [input, setInput] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const h = /^#(\d{4}-\d{2}-\d{2})$/.exec(window.location.hash);
    const today = localISO();
    setDate(h && h[1] >= start && h[1] <= today ? h[1] : today);
  }, [start]);

  useEffect(() => {
    if (!date) return;
    setPuzzle(null);
    setMissing(false);
    fetch(`/api/play/${date.slice(0, 7)}.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((m: { puzzles: Puzzle[] }) => {
        const p = m.puzzles.find((x) => x.date === date);
        if (!p) throw new Error("no puzzle");
        setPuzzle(p);
        const raw = localStorage.getItem(`play:${p.number}`);
        setSaved(raw ? JSON.parse(raw) : { guesses: [], done: false });
      })
      .catch(() => setMissing(true));
  }, [date]);

  const archive = useMemo(() => {
    const out: string[] = [];
    const s = new Date(start + "T12:00:00");
    const today = localISO();
    for (let i = 0; i < days; i++) {
      const d = localISO(new Date(s.getTime() + i * 86400000));
      if (d > today) break;
      out.push(d);
    }
    return out.reverse();
  }, [start, days]);

  if (missing) return <p className="text-sm text-muted-foreground">No puzzle is published for {date}.</p>;
  if (!puzzle) return <p className="text-sm text-muted-foreground">Loading today&rsquo;s puzzle…</p>;

  const won = saved.guesses.includes(puzzle.year);
  const over = won || saved.guesses.length >= MAX;
  const shown = over ? puzzle.clues.length : Math.min(puzzle.clues.length, saved.guesses.length + 1);

  const guess = (e: React.FormEvent) => {
    e.preventDefault();
    const n = parseInt(input, 10);
    if (Number.isNaN(n) || over) return;
    const guesses = [...saved.guesses, n];
    const next = { guesses, done: guesses.includes(puzzle.year) || guesses.length >= MAX };
    setSaved(next);
    localStorage.setItem(`play:${puzzle.number}`, JSON.stringify(next));
    setInput("");
    if (next.done && date === localISO()) {
      const stats = JSON.parse(localStorage.getItem("play:stats") ?? '{"played":0,"won":0,"streak":0,"last":0}');
      stats.played += 1;
      if (guesses.includes(puzzle.year)) {
        stats.won += 1;
        stats.streak = stats.last === puzzle.number - 1 ? stats.streak + 1 : 1;
      } else stats.streak = 0;
      stats.last = puzzle.number;
      localStorage.setItem("play:stats", JSON.stringify(stats));
    }
  };

  const share = () => {
    const rows = saved.guesses.map((g) => {
      const m = mark(g, puzzle.year);
      return m.square + m.arrow;
    });
    const text = `slashyear #${puzzle.number} ${won ? saved.guesses.length : "X"}/${MAX}\n${rows.join(" ")}\nhttps://slashyear.com/play`;
    navigator.clipboard?.writeText(text).then(() => setCopied(true));
  };

  const stats = typeof window !== "undefined" ? JSON.parse(localStorage.getItem("play:stats") ?? "null") : null;

  return (
    <div>
      <p className="mb-4 text-xs text-muted-foreground">
        Puzzle #{puzzle.number} · {puzzle.date} · guess {Math.min(saved.guesses.length + 1, MAX)} of {MAX}
      </p>
      <ol className="mb-6 flex flex-col gap-3">
        {puzzle.clues.slice(0, shown).map((c, i) => (
          <li className="border-l-2 border-border pl-3 text-sm leading-relaxed text-foreground/90" key={i}>
            <span className="mr-2 text-xs text-muted-foreground">Clue {i + 1}</span>
            {c.text}
            {over && (
              <a className="ml-1 align-super text-[10px] text-muted-foreground hover:underline" href={c.cite.url} target="_blank" rel="noreferrer nofollow">
                source
              </a>
            )}
          </li>
        ))}
      </ol>

      {saved.guesses.length > 0 && (
        <ul className="mb-6 flex flex-wrap gap-2 text-sm">
          {saved.guesses.map((g, i) => {
            const m = mark(g, puzzle.year);
            return (
              <li className="border border-border px-2 py-1 tabular-nums" key={i}>
                {m.square} {g} {m.arrow && <span title={m.arrow === "⬆️" ? "later" : "earlier"}>{m.arrow === "⬆️" ? "later" : "earlier"}</span>}
              </li>
            );
          })}
        </ul>
      )}

      {!over ? (
        <form className="mb-8 flex items-center gap-2" onSubmit={guess}>
          <input
            aria-label="Your guess"
            inputMode="numeric"
            placeholder="Year"
            className="w-28 border border-border bg-background px-2 py-1 text-sm"
            value={input}
            onChange={(e) => setInput(e.target.value.replace(/[^0-9]/g, "").slice(0, 4))}
          />
          <button className="border border-border px-3 py-1 text-sm hover:bg-muted" type="submit">
            Guess
          </button>
          <span className="text-xs text-muted-foreground">🟩 exact · 🟨 within 10 · 🟧 within 50 · 🟥 further</span>
        </form>
      ) : (
        <div className="mb-8 border border-border p-4 text-sm">
          <p className="mb-2 text-base text-foreground">
            {won ? `Got it in ${saved.guesses.length}.` : "Out of guesses."} The year was{" "}
            <a className="underline underline-offset-2" href={`/${puzzle.year}`}>{puzzle.year}</a>.
          </p>
          {stats && date === localISO() && (
            <p className="mb-2 text-muted-foreground">
              Played {stats.played} · won {stats.won} · streak {stats.streak}
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            <button className="border border-border px-3 py-1 hover:bg-muted" onClick={share} type="button">
              {copied ? "Copied" : "Share result"}
            </button>
            <a className="px-1 py-1 underline underline-offset-2" href={`/${puzzle.year}`}>Everything from {puzzle.year} →</a>
          </div>
        </div>
      )}

      {archive.length > 1 && (
        <details className="text-sm text-muted-foreground">
          <summary className="cursor-pointer">Earlier puzzles</summary>
          <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
            {archive.map((d) => (
              <li key={d}>
                <a
                  className="underline-offset-2 hover:underline"
                  href={`#${d}`}
                  onClick={() => setDate(d)}
                >
                  {d}
                </a>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
