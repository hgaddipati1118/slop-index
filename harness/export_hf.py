"""Export the Slop Index as a Hugging Face dataset folder.

Writes hf-dataset/ with:
  data/outputs.parquet   one row per generation (error rows dropped)
  data/models.parquet    per-model mechanical axes, prices and live crowd Elo
  data/scenarios.jsonl   the 112 writing tasks
  README.md              dataset card (written separately, kept in the folder)

Run: uv run --with pyarrow python harness/export_hf.py <run-id>   e.g. full-merged-v5
"""
import json, os, sys, urllib.request
import pyarrow as pa, pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "hf-dataset", "data")


def main(run_id):
    os.makedirs(OUT, exist_ok=True)
    bench = json.load(open(os.path.join(ROOT, "slop-game/public/bench.json")))
    names = {m["id"]: (m["name"], m["lab"]) for m in bench["models"]}

    rows = []
    for line in open(os.path.join(ROOT, "runs", run_id, "outputs.jsonl")):
        r = json.loads(line)
        if "error" in r or not r.get("text"):
            continue
        u = r.get("usage") or {}
        rows.append({
            "scenario_id": r["scenario_id"], "domain": r["domain"], "category": r["category"],
            "model": r["model"], "model_name": names.get(r["model"], (r["model"],))[0],
            "lab": names.get(r["model"], (None, None))[1], "sample": r["sample"],
            "system_prompt": r["system"], "user_prompt": r["user_prompt"], "text": r["text"],
            "length_target_words": r["length_target"],
            "output_tokens": u.get("completion_tokens") or u.get("output_tokens"),
        })
    pq.write_table(pa.Table.from_pylist(rows), os.path.join(OUT, "outputs.parquet"), compression="zstd")

    crowd = json.loads(urllib.request.urlopen("https://theslopindex.com/api/leaderboard?mode=v1").read())
    elo = {c["model"]: c for c in crowd["rows"]}
    keep = ("overall", "email", "social", "essay", "slack", "conciseness", "templating", "rhythm", "tells",
            "price_in", "price_out")
    models = [{"model": m["id"], "model_name": m["name"], "lab": m["lab"],
               **{f"mech_{k}" if k not in ("price_in", "price_out") else k: m.get(k) for k in keep},
               "crowd_elo": elo.get(m["id"], {}).get("elo"), "crowd_games": elo.get(m["id"], {}).get("games", 0)}
              for m in bench["models"]]
    pq.write_table(pa.Table.from_pylist(models), os.path.join(OUT, "models.parquet"))

    with open(os.path.join(OUT, "scenarios.jsonl"), "w") as f:
        for d in ("email", "slack", "social", "essay"):
            for s in json.load(open(os.path.join(ROOT, "scenarios/pilot", f"{d}.json"))):
                f.write(json.dumps(s) + "\n")
    print(f"{len(rows):,} outputs, {len(models)} models, crowd votes {crowd.get('totalVotes')}")


if __name__ == "__main__":
    main(sys.argv[1])
