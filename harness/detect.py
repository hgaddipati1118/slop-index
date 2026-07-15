"""Stage 2: score outputs with Pangram. Pulls EVERY field so the go/no-go gate
can test all four candidate sources of resolution:

  1. ai_likelihood            (continuous document confidence)
  2. fraction_ai / _ai_assisted / _human   (three-way text mix)
  3. window score distribution (do any windows dip toward human?)
  4. flagged rate             (tail statistic)

Requires PANGRAM_API_KEY. Also scores the human baseline sample (calibration:
false-positive rate on genuinely pre-AI human writing) when --baseline is given.

Usage:
  PANGRAM_API_KEY=... python3 detect.py --run-id pilot-20260714-0930
  PANGRAM_API_KEY=... python3 detect.py --run-id X --baseline baselines/human_sample.jsonl
"""
import argparse
import json
import os
import pathlib
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
API = "https://text.api.pangramlabs.com"


def score(text, key):
    req = urllib.request.Request(
        API,
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json", "x-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def slim(d):
    """Keep every field that could carry ranking resolution."""
    windows = d.get("windows") or []
    return {
        "ai_likelihood": d.get("ai_likelihood"),
        "prediction": d.get("prediction"),
        "fraction_ai": d.get("fraction_ai"),
        "fraction_ai_assisted": d.get("fraction_ai_assisted"),
        "fraction_human": d.get("fraction_human"),
        "max_ai_likelihood": d.get("max_ai_likelihood"),
        "avg_ai_likelihood": d.get("avg_ai_likelihood"),
        "n_windows": len(windows),
        "window_scores": [w.get("ai_likelihood", w.get("score")) for w in windows],
        "window_labels": [w.get("label") for w in windows],
        "raw_keys": sorted(d.keys()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--baseline", help="jsonl of pre-AI human texts for FPR calibration")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    key = os.environ.get("PANGRAM_API_KEY")
    if not key:
        sys.exit("PANGRAM_API_KEY not set. Buy credits at pangram.com/pricing "
                 "($0.05 per 1k words; this pilot needs roughly $5-15).")

    outdir = RUNS / args.run_id
    rows = [json.loads(l) for l in (outdir / "outputs.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r.get("text") and not r.get("error")]

    items = [{"kind": "model", "row": r, "text": r["text"]} for r in rows]
    if args.baseline:
        for l in pathlib.Path(args.baseline).read_text().splitlines():
            b = json.loads(l)
            items.append({"kind": "human", "row": b, "text": b["text"]})

    print(f"scoring {len(items)} texts with Pangram "
          f"({sum(len(i['text'].split()) for i in items):,} words)")

    def run(item):
        for attempt in range(3):
            try:
                d = score(item["text"], key)
                r = dict(item["row"])
                r["kind"] = item["kind"]
                r["pangram"] = slim(d)
                if attempt == 0 and item is items[0]:
                    print("  sample response keys:", r["pangram"]["raw_keys"])
                return r
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    r = dict(item["row"])
                    r["kind"] = item["kind"]
                    r["pangram_error"] = str(e)[:200]
                    return r
                time.sleep(2 * (attempt + 1))

    scored, errs = [], 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(run, i) for i in items]
        for n, f in enumerate(as_completed(futs), 1):
            r = f.result()
            errs += bool(r.get("pangram_error"))
            scored.append(r)
            if n % 25 == 0 or n == len(items):
                print(f"  {n}/{len(items)} ({errs} errors)", flush=True)

    path = outdir / "scored.jsonl"
    with path.open("w") as f:
        for r in scored:
            f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(scored)} -> {path}")
    if errs:
        print(f"  ! {errs} scoring errors (check key/quota)")


if __name__ == "__main__":
    main()
