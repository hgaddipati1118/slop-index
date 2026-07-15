"""Export the permanent raw vote log from Upstash to a local JSONL file.

The live votes persist in Upstash Redis (durable, survives redeploys), but for a
real dataset you want an offline, version-controllable copy. Run this any time to
snapshot every vote to runs/votes/votes-<date>.jsonl, then commit / push it.

  cd slop-game && vercel env pull .env.local --environment=production --yes
  cd ../harness && KV_REST_API_URL=... KV_REST_API_TOKEN=... python3 export_votes.py
  # or: source ../slop-game/.env.local first

Each record: {t(ms), m(mode), w(winner), l(loser), s(scenario), fp(fingerprint),
v(hashed voter key), d(dwell ms)}.
"""
import json
import os
import pathlib
import time
import urllib.request

URL = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
TOK = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
OUT = pathlib.Path(__file__).resolve().parent.parent / "runs" / "votes"


def cmd(*args):
    req = urllib.request.Request(
        f"{URL}/pipeline",
        data=json.dumps([list(args)]).encode(),
        headers={"Authorization": f"Bearer {TOK}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())[0]["result"]


def main():
    if not (URL and TOK):
        raise SystemExit("Set KV_REST_API_URL and KV_REST_API_TOKEN "
                         "(vercel env pull .env.local, then source it).")
    n = int(cmd("LLEN", "votes:log") or 0)
    print(f"{n} raw votes in the log")
    if not n:
        return
    rows, step = [], 1000
    for start in range(0, n, step):
        chunk = cmd("LRANGE", "votes:log", start, start + step - 1)
        rows.extend(json.loads(x) for x in chunk)
        print(f"  pulled {len(rows)}/{n}")
    # also snapshot the aggregate board for convenience
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M")
    path = OUT / f"votes-{stamp}.jsonl"
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} votes -> {path}")
    # quick sanity tallies
    from collections import Counter
    wins = Counter(r["w"] for r in rows)
    games = Counter()
    for r in rows:
        games[r["w"]] += 1; games[r["l"]] += 1
    print("\nwin rate by model (from raw log):")
    for m, g in sorted(games.items(), key=lambda kv: -wins[kv[0]] / max(kv[1], 1)):
        print(f"  {m:<24} {wins[m]:>4}/{g:<4} = {wins[m] / max(g, 1):.0%}")


if __name__ == "__main__":
    main()
