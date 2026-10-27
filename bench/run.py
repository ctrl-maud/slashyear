#!/usr/bin/env python3
"""Query models on SlashYear-Bench items (closed book, no tools).

Each model's endpoint URL, deployment name and key come from the environment variables
named in MODELS. Raw responses are appended to
results/raw/<model>.jsonl; a rerun skips ids that already have a completed
response, so the script resumes after interruption.

Usage: python3 run.py [--models gpt-6-luna,gpt-6.1-sol,gpt-6-astra] [--limit N] [--workers 8]
"""
import argparse
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "results", "raw")
INSTRUCTIONS = "Answer from memory. Be concise; give only the answer."
MAX_OUTPUT_TOKENS = 4000

MODELS = {
    # name -> (url env, model env, key env)
    "gpt-6-luna": ("LUNA_URL", "LUNA_MODEL", "AZ_KEY"),
    "gpt-6.1-sol": ("SOL_URL", "SOL_MODEL", "AZ_KEY"),
    "gpt-6-astra": ("ASTRA_URL", "ASTRA_MODEL", "ASTRA_KEY"),
}


def output_text(resp):
    if isinstance(resp.get("output_text"), str):
        return resp["output_text"]
    parts = []
    for o in resp.get("output") or []:
        if o.get("type") == "message":
            for c in o.get("content") or []:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    parts.append(c["text"])
    return "".join(parts)


def call(url, model, key, question, max_tokens):
    body = {"model": model, "instructions": INSTRUCTIONS, "input": question,
            "max_output_tokens": max_tokens}
    # HARD RULE: closed book. Never send tools of any kind.
    assert "tools" not in body and "tool_choice" not in body
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def ask(url, model, key, item, max_retries=7):
    last_err = None
    max_tokens = MAX_OUTPUT_TOKENS
    for attempt in range(max_retries):
        try:
            resp = call(url, model, key, item["question"], max_tokens)
            text = output_text(resp)
            inc = (resp.get("incomplete_details") or {}).get("reason")
            if not text.strip() and inc == "max_output_tokens" and max_tokens < 16000:
                max_tokens = 16000   # reasoning ate the budget; retry once with more room
                continue
            return {"id": item["id"], "model": model, "ok": True, "status": resp.get("status"),
                    "incomplete": inc, "output_text": text, "usage": resp.get("usage"),
                    "resp_id": resp.get("id"), "attempts": attempt + 1, "ts": time.time()}
        except urllib.error.HTTPError as e:
            msg = e.read()[:500].decode("utf-8", "replace")
            last_err = f"HTTP {e.code}: {msg}"
            if e.code not in (408, 409, 429) and e.code < 500:
                break   # client error (e.g. content filter): don't retry
            ra = e.headers.get("retry-after") if e.headers else None
            wait = float(ra) if ra and ra.replace(".", "").isdigit() else min(60, 2 ** attempt)
        except Exception as e:  # timeouts, connection resets
            last_err = f"{type(e).__name__}: {e}"
            wait = min(60, 2 ** attempt)
        time.sleep(wait + random.random())
    return {"id": item["id"], "model": model, "ok": False, "error": last_err, "ts": time.time()}


def run_model(name, items, workers, lock_print):
    url_env, model_env, key_env = MODELS[name]
    url, model, key = os.environ.get(url_env), os.environ.get(model_env), os.environ.get(key_env)
    if not (url and model and key):
        print(f"[{name}] missing env {url_env}/{model_env}/{key_env}; skipping", flush=True)
        return
    path = os.path.join(RAW, f"{name}.jsonl")
    done = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("ok"):
                    done.add(r["id"])
    todo = [it for it in items if it["id"] not in done]
    print(f"[{name}] {len(done)} cached, {len(todo)} to run", flush=True)
    wlock = threading.Lock()
    n_ok = n_err = 0
    consecutive_err = 0
    abort = threading.Event()
    with open(path, "a") as out, ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {}
        for it in todo:
            futs[ex.submit(lambda it=it: None if abort.is_set() else ask(url, model, key, it))] = it
        for fut in as_completed(futs):
            r = fut.result()
            if r is None:
                continue
            with wlock:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
            if r["ok"]:
                n_ok += 1
                consecutive_err = 0
            else:
                n_err += 1
                consecutive_err += 1
                if consecutive_err >= 25 and not abort.is_set():
                    print(f"[{name}] 25 consecutive errors, giving up on this model. last: {r['error']}", flush=True)
                    abort.set()
            if (n_ok + n_err) % 100 == 0:
                print(f"[{name}] {n_ok} ok / {n_err} err", flush=True)
    print(f"[{name}] finished: {n_ok} ok, {n_err} errors this run", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--items", default=os.path.join(HERE, "items.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    with open(args.items) as f:
        items = [json.loads(l) for l in f]
    if args.limit:
        items = items[:args.limit]
    names = [m for m in args.models.split(",") if m]
    lock = threading.Lock()
    threads = [threading.Thread(target=run_model, args=(n, items, args.workers, lock)) for n in names]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
