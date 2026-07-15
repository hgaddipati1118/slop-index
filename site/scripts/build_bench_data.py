import pathlib as _pl
_ROOT = _pl.Path(__file__).resolve().parents[2]  # repo root
"""Assemble the benchmark results into one JSON for the page:
overall + per-axis Slop Index, rank-spread ranges, tie groups, prices, Pangram.
"""
import json, os, re, sys, pathlib
sys.path.insert(0, str(_ROOT/"harness"))
import providers  # for PRICES

ROOT = _ROOT
log = (ROOT / "runs/full-merged-score.log").read_text().splitlines()

NAMES = {'claude-sonnet-5':'Sonnet 5','claude-opus-4-8':'Opus 4.8','claude-haiku-4-5':'Haiku 4.5',
  'claude-fable-5':'Fable 5','gpt-5.6-luna':'GPT-5.6 Luna','gpt-5.6-sol':'GPT-5.6 Sol','gpt-5.6-terra':'GPT-5.6 Terra',
  'gpt-5.4-mini':'GPT-5.4 Mini','gemini-3.1-pro-preview':'Gemini 3.1 Pro','gemini-3.5-flash':'Gemini 3.5 Flash',
  'grok-4.5':'Grok 4.5','kimi-k2p6':'Kimi K2.6','deepseek-v4-pro':'DeepSeek V4','glm-5.2':'GLM-5.2',
  'qwen3.7-max':'Qwen3.7 Max','minimax-m3':'MiniMax M3','mistral-large':'Mistral Large','muse-spark-1.1':'Muse Spark'}
LAB = {'claude-sonnet-5':'Anthropic','claude-opus-4-8':'Anthropic','claude-haiku-4-5':'Anthropic','claude-fable-5':'Anthropic',
  'gpt-5.6-luna':'OpenAI','gpt-5.6-sol':'OpenAI','gpt-5.6-terra':'OpenAI','gpt-5.4-mini':'OpenAI',
  'gemini-3.1-pro-preview':'Google','gemini-3.5-flash':'Google','grok-4.5':'xAI','kimi-k2p6':'Moonshot',
  'deepseek-v4-pro':'DeepSeek','glm-5.2':'Zhipu','qwen3.7-max':'Alibaba','minimax-m3':'MiniMax',
  'mistral-large':'Mistral','muse-spark-1.1':'Meta'}

models = {}
sec = None
for ln in log:
    if re.search(r'email\s+essay\s+slack\s+social\s+OVERALL', ln): sec='overall'; continue
    if re.search(r'conciseness\s+templating\s+rhythm\s+tells', ln): sec='axes'; continue
    if ln.startswith('sensitivity') or ln.startswith('SLOP INDEX — RANK'): sec=None
    m = re.match(r'\s*([a-z0-9.\-]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$', ln)
    if sec=='overall' and m and m.group(1) in NAMES:
        k=m.group(1); models.setdefault(k,{})
        models[k].update(dict(email=float(m[2]),essay=float(m[3]),slack=float(m[4]),
                              social=float(m[5]),overall=float(m[6])))
    m2 = re.match(r'\s*([a-z0-9.\-]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$', ln)
    if sec=='axes' and m2 and m2.group(1) in NAMES:
        k=m2.group(1); models.setdefault(k,{})
        models[k].update(dict(conciseness=float(m2[2]),templating=float(m2[3]),
                              rhythm=float(m2[4]),tells=float(m2[5])))

# rank spread: "  1  mistral-large   40.6   ranks 1"  /  "ranks 2–3"
for ln in log:
    m = re.match(r'\s*(\d+)\s+([a-z0-9.\-]+)\s+([\d.]+)\s+ranks?\s+([\d–\-]+)\s*$', ln)
    if m and m.group(2) in NAMES:
        k=m.group(2)
        models[k]['rank']=int(m[1]); models[k]['spread']=m[4].replace('-','–')

# tie groups
groups=[]
for ln in log:
    g=re.match(r'\s*group \d+:\s*(.+)$', ln)
    if g: groups.append([s.strip() for s in g.group(1).split(',')])

rows=[]
for k,v in models.items():
    pin,pout = providers.PRICES.get(k,(None,None))
    rows.append({"id":k,"name":NAMES[k],"lab":LAB.get(k,''),
        "overall":v.get('overall'),"email":v.get('email'),"essay":v.get('essay'),
        "slack":v.get('slack'),"social":v.get('social'),
        "conciseness":v.get('conciseness'),"templating":v.get('templating'),
        "rhythm":v.get('rhythm'),"tells":v.get('tells'),
        "rank":v.get('rank'),"spread":v.get('spread'),
        "price_in":pin,"price_out":pout,
        "blended":round((pin+pout)/2,2) if pin is not None else None,
        "pangram":100})
rows.sort(key=lambda r:r['rank'] or 99)

data={"models":rows,"tie_groups":groups,
      "meta":{"n_models":len(rows),"n_outputs":19928,"scenarios":112,
              "domains":["email","social","essay","slack"],
              "weights":{"conciseness":0.35,"templating":0.30,"rhythm":0.20,"tells":0.15},
              "pangram_note":"15 of 18 models browser-scored on pangram.com (v3.3.2); every one = 100% AI, High confidence"}}
out=ROOT/"site/public/bench.json"
out.write_text(json.dumps(data,indent=1))
print(f"wrote {len(rows)} models, {len(groups)} tie groups -> {out}")
for r in rows: print(f"  #{r['rank']:>2} {r['name']:<16} slop {r['overall']:>5} ({r['spread']})  ${r['blended']}/M")
