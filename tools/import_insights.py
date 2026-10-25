"""One-time import: evergreen blog posts from the playbook archive into src/insights/.

  python3 tools/import_insights.py <playbook repo path>
Drops dates, reader comments, "Share your thoughts" sections and subscribe prompts; rewrites old links and images.
"""
import json, re, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PB = Path(sys.argv[1])
DB = PB / "archive" / "blog-database"
UP = PB / "archive" / "images" / "blog" / "wp-uploads-complete"
OUT = ROOT / "src" / "insights"; IMG = ROOT / "src" / "assets" / "img" / "insights"
EXCLUDE = {"speak-for-impact-3", "lost-opportunity-netflixs-reed-hastings-blows-the-apology-part-i", "lost-opportunity-netflixs-reed-hastings-blows-the-apology-part-ii",
           "new-years-resolutions-with-a-twist", "top-5-new-years-resolutions-for-executives-in-2013", "the-benefits-of-being-seen-learning-from-marissa-mayer",
           "watch-janet-napolitano-exemplify-the-speaking-strength-clarity", "extra-extra-2", "the-first-lady-of-humor"}
TOPIC = {
 "Speaking Strengths™": ["be-an-all-star-speak-from-your-strengths-3", "do-you-speak-with-command", "do-you-speak-with-clarity", "speaking-hiccups"],
 "Media and video": ["executives-get-ready-for-video", "lookin-good-on-video-conference-calls", "virtual-communication", "are-you-giving-a-best-picture-performancevjvfct98wkny"],
 "Nerves and voice": ["anxiety-impedes-peak-performance", "alleviate-anxiety-tip-1-energize-your-brain", "alleviate-anxiety-tip-2-support-your-voice", "alleviate-anxiety-tip-3-breathe", "rapid-speak-is-a-liability", "fast-delivery-can-mean-fast-failure"],
 "Leadership communication": ["speak-often-its-good-for-business-great-for-your-career", "do-you-want-to-become-leadership-material", "books-to-expand-your-view-of-leadership", "top-7-good-reads-for-communicators", "managing-interruptions-and-managing-to-interrupt"],
}
SLUGFIX = {"are-you-giving-a-best-picture-performancevjvfct98wkny": "best-picture-performance", "be-an-all-star-speak-from-your-strengths-3": "speak-from-your-strengths"}
REDIRECTS = json.loads((ROOT / "src" / "data" / "redirects.json").read_text()) if (ROOT / "src" / "data" / "redirects.json").exists() else {}
topic_of = {s: t for t, ss in TOPIC.items() for s in ss}
OUT.mkdir(parents=True, exist_ok=True); IMG.mkdir(parents=True, exist_ok=True)
index = []
for f in sorted(DB.glob("2*.md")):
    slug = f.stem[11:]
    if slug in EXCLUDE: continue
    raw = f.read_text()
    fm_txt, body = raw[4:].split("\n---\n", 1)
    fm = {k: json.loads(v) for k, v in re.findall(r"^(\w+): (.*)$", fm_txt, re.M)}
    body = body.split("\n## Reader comments")[0]
    body = re.split(r"\n#{2,4} *Share (your|you) thoughts.*", body, flags=re.I)[0]
    paras = [p for p in body.split("\n\n") if not re.search(r"subscribe to (this|our) blog|commenting on this post|comment (on|to) this post|share your (thoughts|observations|experiences?) (in|by) (a )?comment", p, re.I)]
    body = "\n\n".join(paras).strip() + "\n"
    def img(m):
        name = m.group(2).rsplit("/", 1)[-1]
        if (UP / name).exists(): shutil.copy(UP / name, IMG / name); return f"![{m.group(1)}](/assets/img/insights/{name})"
        return ""
    body = re.sub(r"!\[([^\]]*)\]\((https?://(?:www\.)?grantandassociates\.com/blog/wp-content/uploads/[^)]+)\)", img, body)
    def link(m):
        url = m.group(2)
        path = re.sub(r"^https?://(www\.)?grantandassociates\.com", "", url)
        if path in REDIRECTS: return f"[{m.group(1)}]({REDIRECTS[path]})"
        if path.startswith("/blog"): return m.group(1)
        return m.group(0)
    body = re.sub(r"\[([^\]]*)\]\(([^)\s]+)\)", link, body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)|[*#>]", lambda m: m.group(1) or "", body.split("\n", 2)[2] if body.startswith("# ") else body)
    first = next((p.strip() for p in text.split("\n\n") if len(p.strip()) > 60), "")
    summary = re.sub(r"\s+", " ", first)[:150].rsplit(" ", 1)[0] + "…" if len(first) > 150 else first
    new = SLUGFIX.get(slug, slug)
    meta = {"topic": topic_of.get(slug, "Presentation skills"), "description": fm.get("meta_description") or summary, "summary": summary, "source": f.name}
    (OUT / f"{new}.md").write_text("---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items()) + "\n---\n" + body)
    index.append((meta["topic"], new))
print(len(index), "articles"); [print(" ", t, "|", s) for t, s in sorted(index)]
