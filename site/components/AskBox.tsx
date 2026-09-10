"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";

/* The Turnstile site key is public by design — it ships in the HTML of every site that
 * uses one. It is hardcoded rather than read from a build variable so that a deploy from
 * a clean checkout can never silently produce a page whose captcha never loads. */
const SITEKEY = "0x4AAAAAAEugLtjhRly709jG";

type Source = {
  n: number;
  year: number;
  year_label: string;
  date: string | null;
  text: string;
  page: string;
  wikipedia: string;
  revision: number;
};

type Answer = {
  question: string;
  answer: string;
  sources: Source[];
  matched: number;
  cached?: boolean;
};

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      reset: (id?: string) => void;
    };
  }
}

const EXAMPLES = [
  "How did the decline of the Ottoman Empire shape modern Syria?",
  "What happened to Krakatoa, and what followed it?",
  "Trace the printing press from its invention to its spread",
  "What was happening in Japan while Rome was falling?",
];

/** Renders the answer with its [3] markers turned into links down to the source list. */
function Rendered({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n{2,}/).map((para, i) => (
        <p className="mb-4 leading-relaxed text-foreground/90" key={i}>
          {para.split(/(\[\d{1,2}\])/).map((bit, j) => {
            const m = bit.match(/^\[(\d{1,2})\]$/);
            if (!m) return <span key={j}>{bit}</span>;
            return (
              <a
                className="text-muted-foreground align-super text-[0.7em] underline underline-offset-2 hover:text-foreground"
                href={`#s${m[1]}`}
                key={j}
              >
                {m[1]}
              </a>
            );
          })}
        </p>
      ))}
    </>
  );
}

export default function AskBox() {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [ready, setReady] = useState(false);
  const holder = useRef<HTMLDivElement>(null);
  const widget = useRef<string | null>(null);
  const token = useRef<string | null>(null);

  /* Turnstile in managed mode is invisible for an ordinary visitor: it settles on its own
   * and only ever shows a box to something that looks automated. It is rendered once and
   * reset after each ask, because a token is single-use. */
  const mount = useCallback(() => {
    if (!window.turnstile || !holder.current || widget.current) return;
    widget.current = window.turnstile.render(holder.current, {
      sitekey: SITEKEY,
      /* Left at the default appearance on purpose. "interaction-only" hides the widget
       * until a challenge is needed, and a visitor who IS challenged then has nothing on
       * screen to complete — the Ask button simply never works for them and they have no
       * way to know why. A small always-visible box is the honest trade. */
      callback: (t: string) => {
        token.current = t;
        setReady(true);
      },
      "expired-callback": () => {
        token.current = null;
        setReady(false);
        window.turnstile?.reset(widget.current ?? undefined);
      },
      "error-callback": () => setReady(false),
    });
  }, []);

  useEffect(() => {
    if (window.turnstile) mount();
  }, [mount]);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question, token: token.current }),
      });
      const d = await r.json();
      if (!r.ok) setError(d.error || "Something went wrong.");
      else setAnswer(d);
    } catch {
      setError("The request did not go through. Try again.");
    } finally {
      setBusy(false);
      token.current = null;
      setReady(false);
      window.turnstile?.reset(widget.current ?? undefined);
    }
  }

  return (
    <>
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        strategy="afterInteractive"
        onLoad={mount}
      />

      <form
        className="border border-border"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(q);
        }}
      >
        <label className="sr-only" htmlFor="ask">
          Your question
        </label>
        <textarea
          id="ask"
          rows={3}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={300}
          placeholder="Ask about anything that happened, and how it led to something else."
          className="w-full resize-none bg-transparent p-4 text-base text-foreground outline-none placeholder:text-muted-foreground"
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void ask(q);
          }}
        />
        <div className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-2">
          <div ref={holder} />
          <span className="text-xs text-muted-foreground">{300 - q.length} characters left</span>
          <button
            type="submit"
            disabled={busy}
            className="ml-auto border border-border px-4 py-1.5 text-sm text-foreground hover:bg-muted disabled:opacity-50"
          >
            {busy ? "Reading the sources…" : "Ask"}
          </button>
        </div>
      </form>

      {!answer && !busy && (
        <ul className="mt-4 flex flex-col gap-1.5 text-sm">
          {EXAMPLES.map((x) => (
            <li key={x}>
              <button
                className="text-left text-muted-foreground underline underline-offset-2 hover:text-foreground"
                onClick={() => {
                  setQ(x);
                  void ask(x);
                }}
                type="button"
              >
                {x}
              </button>
            </li>
          ))}
        </ul>
      )}

      {!ready && busy && null}

      {error && (
        <p className="mt-6 border border-border bg-muted p-4 text-sm text-foreground/90">{error}</p>
      )}

      {answer && (
        <section className="mt-8">
          <Rendered text={answer.answer} />
          {answer.sources.length > 0 && (
            <>
              <h2 className="mb-3 mt-10 border-t border-border pt-4 text-sm text-muted-foreground">
                Every sentence above came from one of these. Each is frozen to the Wikipedia
                revision it was read from, so it says the same thing tomorrow.
              </h2>
              <ol className="flex flex-col gap-3 text-sm">
                {answer.sources.map((s) => (
                  <li className="text-foreground/85" id={`s${s.n}`} key={s.n}>
                    <span className="text-muted-foreground">[{s.n}]</span>{" "}
                    <a className="underline underline-offset-2" href={s.page}>
                      {s.date ? `${s.date}, ${s.year_label}` : s.year_label}
                    </a>{" "}
                    — {s.text}{" "}
                    <a
                      className="text-muted-foreground underline underline-offset-2 hover:text-foreground"
                      href={s.wikipedia}
                      rel="nofollow noopener"
                    >
                      source
                    </a>
                  </li>
                ))}
              </ol>
            </>
          )}
        </section>
      )}
    </>
  );
}
