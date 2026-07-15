import pathlib as _pl
_ROOT = _pl.Path(__file__).resolve().parents[2]  # repo root
"""Rebuild site/public/pairs.json across ALL 18 models, balanced.
For each scenario: R rounds of a random perfect matching over the models that
have an output for it, one random sample per model per pair. Reuses the existing
per-scenario `setup` voter-context text.
"""
import json, os, random, collections, pathlib
random.seed(20260714)  # deterministic build

ROOT = _ROOT
GAME = ROOT / "site/public"

# scenario -> setup (voter context) and scenario -> domain from the current file
old = json.loads((GAME / "pairs.json").read_text())
setups = {x["scenario"]: x["setup"] for x in old if x.get("setup")}

# group merged outputs by (scenario, model) -> list of texts
by = collections.defaultdict(lambda: collections.defaultdict(list))
domain = {}
for l in (ROOT / "runs/full-merged/outputs.jsonl").read_text().splitlines():
    if not l.strip():
        continue
    d = json.loads(l)
    t = (d.get("text") or "").strip()
    if not t:
        continue
    by[d["scenario_id"]][d["model"]].append(t)
    domain[d["scenario_id"]] = d["domain"]

R = 3  # matching rounds per scenario -> ~ (models/2)*R pairs each
pairs = []
model_count = collections.Counter()
for scen, models_texts in by.items():
    models = [m for m, ts in models_texts.items() if ts]
    for _ in range(R):
        random.shuffle(models)
        for i in range(0, len(models) - 1, 2):
            ma, mb = models[i], models[i + 1]
            pairs.append({
                "scenario": scen,
                "domain": domain[scen],
                "setup": setups.get(scen, ""),
                "a": {"model": ma, "text": random.choice(models_texts[ma])},
                "b": {"model": mb, "text": random.choice(models_texts[mb])},
            })
            model_count[ma] += 1
            model_count[mb] += 1

random.shuffle(pairs)
(GAME / "pairs.json").write_text(json.dumps(pairs))
print(f"wrote {len(pairs)} pairs across {len(model_count)} models -> {GAME/'pairs.json'}")
for m, n in sorted(model_count.items()):
    print(f"  {n:5d}  {m}")
