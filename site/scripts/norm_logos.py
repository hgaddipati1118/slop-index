"""Normalize fetched brand SVGs to clean monochrome inline SVGs (fill=currentColor)
and write public/logos.json keyed by the lab names used in bench.json."""
import re, json, pathlib

# lab (as in bench.json) -> fetched file basename
MAP = {
  "Anthropic":"Anthropic","OpenAI":"OpenAI","Google":"Google","xAI":"xAI",
  "Moonshot":"Moonshot","DeepSeek":"DeepSeek","Zhipu":"Zhipu","Alibaba":"Qwen",
  "MiniMax":"MiniMax","Mistral":"Mistral","Meta":"Meta",
}
TMP = pathlib.Path("/tmp")

def norm(svg):
    svg = re.sub(r"<\?xml.*?\?>", "", svg, flags=re.S)
    svg = re.sub(r"<title>.*?</title>", "", svg, flags=re.S)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"<style.*?</style>", "", svg, flags=re.S)
    # viewBox
    m = re.search(r'viewBox="([^"]+)"', svg)
    vb = m.group(1) if m else "0 0 24 24"
    # inner content between <svg ...> and </svg>
    inner = re.sub(r"^.*?<svg[^>]*>", "", svg, flags=re.S)
    inner = re.sub(r"</svg>.*$", "", inner, flags=re.S)
    # strip hardcoded colors so it inherits currentColor; drop class refs
    inner = re.sub(r'\sfill="(?!none)[^"]*"', "", inner)
    inner = re.sub(r'\sstroke="(?!none)[^"]*"', "", inner)
    inner = re.sub(r'\sclass="[^"]*"', "", inner)
    inner = re.sub(r"\s+", " ", inner).strip()
    return f'<svg viewBox="{vb}" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{inner}</svg>'

out = {}
for lab, base in MAP.items():
    f = TMP / f"logo_{base}.svg"
    if not f.exists():
        print("MISSING", lab, base); continue
    out[lab] = norm(f.read_text())

dest = _ROOT/ "site/public/logos.json"
dest.write_text(json.dumps(out))
print(f"wrote {len(out)} logos -> {dest}")
for k,v in out.items(): print(f"  {k:<12} {len(v)} chars")
