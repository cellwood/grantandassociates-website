"""Build the content doc tabs from the new site's source (src/pages, src/insights).

  python3 tools/content-doc/gen.py tabs                -> [{key, title, parent}] in doc order (JSON)
  python3 tools/content-doc/gen.py index                -> tools/content-doc/index.json (Index & rules tab requests)
  python3 tools/content-doc/gen.py requests ids.json    -> tools/content-doc/requests/<key>.json per tab
  python3 tools/content-doc/gen.py preview <key>        -> the blocks for one tab, as text
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  (read_page, url_for, DATA)

OUT = Path(__file__).resolve().parent
BASE = "https://grantandassociates.com"
QUOTES = build.DATA["quotes"]
LABELS = {"/": "Home", "/coaching-training/": "Coaching & Training", "/who-we-serve/": "Who We Serve"}
for _i in build.DATA["nav"]:
    LABELS.setdefault(_i["url"], html.unescape(_i["label"]))
    for _c in _i.get("children", []): LABELS.setdefault(_c["url"], html.unescape(_c["label"]))
OLD = {}
for old, new in build.DATA["redirects"].items():
    OLD.setdefault(new, []).append(old)

NEW_PAGES = {"who-we-serve", "insights", "contact__thanks"}  # no old-site page behind them
STATUS_NOTE = {"🟡": "Edited from the old site's text. Please review.",
               "🔴": "New for this site. Please review."}

def u16(s): return len(s.encode("utf-16-le")) // 2

def short_title(s, limit=46):
    """Docs tab names max out at 50 characters (the status emoji takes 3)."""
    if u16(s) <= limit: return s
    for sep in (": ", " - "):
        if sep in s and (20 if sep == ": " else 8) <= len(s.split(sep)[0]) and u16(s.split(sep)[0]) <= limit: return s.split(sep)[0]
    out = ""
    for w in s.split():
        if u16(out + " " + w) > limit - 1: break
        out = (out + " " + w).strip()
    return out + "…"

def absu(h):
    if h.startswith(("http", "mailto:", "tel:")): return h
    return BASE + (h if h.startswith("/") else "/" + h)

# ---------- doc order ----------

def page_path(url):
    if url == "/": return ROOT / "src/pages/index.md"
    return ROOT / "src/pages" / (url.strip("/").replace("/", "__") + ".md")

def tab_list():
    seen, tabs = set(), []
    def add(path, parent=None):
        key = "page:" + path.stem
        if key in seen: return
        seen.add(key); fm, _ = build.read_page(path)
        st = "🔴" if path.stem in NEW_PAGES else "🟡"
        url = fm.get("url") or build.url_for(path)
        name = LABELS.get(url) or html.unescape(fm.get("short") or re.sub(r"\s*·.*", "", fm["title"]))
        tabs.append({"key": key, "path": str(path), "title": f"{st} {name}", "status": st, "parent": parent})
    add(page_path("/"))
    for item in build.DATA["nav"]:
        add(page_path(item["url"]))
        for c in item.get("children", []):
            add(page_path(c["url"]), "page:" + page_path(item["url"]).stem)
        if item["url"] == "/insights/":
            for a in sorted(build.ARTICLES, key=lambda a: (a["topic"], a["title"])):
                st = "🔴" if a["fm"].get("source", "").endswith(".pdf") or "(20" in a["fm"].get("source", "") else "🟡"
                tabs.append({"key": "post:" + a["slug"], "path": str(a["path"]), "title": f"{st} {short_title(re.sub(r'[*_]', '', a['title']))}",
                             "status": st, "parent": "page:insights"})
    for p in sorted((ROOT / "src/pages").glob("*.md")):
        add(p, "page:contact" if p.stem == "contact__thanks" else None)
    return tabs

# ---------- site markdown -> doc blocks ----------

def strip_tags(s): return html.unescape(re.sub(r"<[^>]+>", "", s))

def quote_text(key):
    q = QUOTES.get(key)
    return f'[Testimonial] “{q["text"]}” {q["name"]}, {q["role"]}' if q else f"[Testimonial: {key}]"

def to_plain_md(body):
    """Turn the site's markdown-with-HTML into plain markdown lines the doc can show."""
    s = re.sub(r"\]\(\s*([^)\s]+)\s*\)", r"](\1)", body)  # stray spaces inside link targets
    s = re.sub(r"\{\{quote:(\w+)\}\}", lambda m: "\n" + quote_text(m.group(1)) + "\n", s)
    s = s.replace("{{contact_form}}", "\n[Contact form: Name, Email, Organization (optional), Message. Sends to judy@grantandassociates.com.]\n")
    s = s.replace("{{insights}}", "\n[The list of Insights articles appears here, grouped by topic. It is built from the article tabs under this one.]\n")
    s = re.sub(r'<a class="svc" href="([^"]+)">(?:<img[^>]*>)?<span>(.*?)<small>(.*?)</small></span></a>',
               lambda m: f"\n- [{strip_tags(m.group(2))}]({m.group(1)}): {strip_tags(m.group(3))}\n", s)
    s = re.sub(r'<a class="button[^"]*" href="([^"]+)">(.*?)</a>', lambda m: f"\n[Button] [{strip_tags(m.group(2))}]({m.group(1)})\n", s)
    s = re.sub(r'<h(\d)>(.*?)</h\1>', lambda m: "\n" + "#" * int(m.group(1)) + " " + re.sub(r'<a href="([^"]+)">(.*?)</a>', r"[\2](\1)", m.group(2)) + "\n", s)
    s = re.sub(r'<a href="([^"]+)"><img [^>]*alt="([^"]*)"[^>]*></a>', lambda m: f"\n[Book cover: {m.group(2).replace('Cover of ', '')}]\n", s)
    s = re.sub(r'<img [^>]*src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>', lambda m: f"\n[Photo: {m.group(2) or 'no description'} ({Path(m.group(1)).name})]\n", s)
    s = re.sub(r'<img [^>]*alt="([^"]*)"[^>]*src="([^"]+)"[^>]*>', lambda m: f"\n[Photo: {m.group(1) or 'no description'} ({Path(m.group(2)).name})]\n", s)
    s = re.sub(r'<a href="([^"]+)">(.*?)</a>', r"[\2](\1)", s)
    s = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", s)
    s = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", s, flags=re.S)
    s = re.sub(r"<li>(.*?)</li>", r"\n- \1\n", s, flags=re.S)
    s = re.sub(r"</?(div|ul|ol|span|small|section|figure|br)[^>]*>", "\n", s)
    s = re.sub(r"\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)", lambda m: f"\n[Photo: {m.group(1) or 'no description'} ({Path(m.group(2)).name}), links to {m.group(3)}]\n", s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", lambda m: f"\n[Photo: {m.group(1) or 'no description'} ({Path(m.group(2)).name})]\n", s)
    return html.unescape(s)

def inline(s):
    s = re.sub(r"\]\((/[^)]*)\)", lambda m: "](" + absu(m.group(1)) + ")", s)
    s = re.sub(r"(?<![*\w])\*(?!\*)([^*\n]+?)(?<!\*)\*(?![*\w])", r"\1", s)  # italics -> plain
    s = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", s)
    return s.strip()

def blocks(md, top=1):
    out = []
    for line in to_plain_md(md).split("\n"):
        line = line.rstrip()
        if not line.strip(): continue
        m = re.match(r"^(#{1,6}) (.*)", line)
        if m:
            out.append((f"H{min(len(m.group(1)) - 1 + top, 6)}", inline(m.group(2)))); continue
        m = re.match(r"^\s*(?:-|\d+\.) (.*)", line)
        if m:
            out.append(("UL", inline(m.group(1)))); continue
        if line.startswith(">"): line = line.lstrip("> ")
        if line.count("**") % 2: line = line.replace("**", "")
        t = inline(line)
        if t: out.append(("P", t))
    return out

def tab_blocks(tab):
    path = Path(tab["path"]); fm, body = build.read_page(path)
    fm = {k: html.unescape(v) if isinstance(v, str) else v for k, v in fm.items()}
    post = tab["key"].startswith("post:")
    url = f"/insights/{path.stem}/" if post else (fm.get("url") or build.url_for(path))
    title = re.sub(r"^# (.*)\n?", "", body, count=1)
    h1 = re.search(r"^# (.*)", body, re.M)
    b = [("P", f"[{STATUS_NOTE[tab['status']]}]"), ("H3", "Page settings"),
         ("UL", f"**Address:** [{url}]({absu(url)})")]
    if post:
        b.append(("UL", f"**SEO title:** {re.sub(r'[*_]', '', h1.group(1)) if h1 else path.stem} · Grant and Associates"))
        b.append(("UL", f"**Topic:** {fm.get('topic', '')}"))
    else:
        b.append(("UL", f"**SEO title:** {fm['title']}"))
    b.append(("UL", f"**Meta description:** {fm.get('description', '')}"))
    if fm.get("summary"): b.append(("UL", f"**Summary on the Insights page:** {fm['summary']}"))
    if fm.get("short") and not post: b.append(("UL", f"**Short name (menus and links):** {fm['short']}"))
    for k, label in (("eyebrow", "Line above the big heading"), ("hero", "Big heading"), ("lede", "Text under the big heading")):
        if fm.get(k): b.append(("UL", f"**{label}:** {fm[k]}"))
    if fm.get("quote"): b.append(("UL", f"**Testimonial beside the text:** {quote_text(fm['quote']).replace('[Testimonial] ', '')}"))
    if fm.get("related"):
        b.append(("UL", "**Related links at the bottom:** " + ", ".join(f"[{u}]({absu(u)})" for u in fm["related"])))
    olds = OLD.get(url, [])
    if olds and not post:
        b.append(("UL", "**Replaces old address(es):** " + ", ".join(olds[:6]) + (" …" if len(olds) > 6 else "")))
    b.append(("H3", "Page text"))
    if h1: b.append(("H1", inline(h1.group(1))))
    b += blocks(body if not h1 else title, top=2 if h1 else 1)
    return b

def parse_inline(text):
    out, bolds, links, pos = "", [], [], 0
    pat = re.compile(r"\*\*(.+?)\*\*|\[([^\]]*)\]\(([^)\s]+)\)")
    for m in pat.finditer(text):
        out += text[pos:m.start()]
        if m.group(1) is not None:
            t2, b2, l2 = parse_inline(m.group(1))
            s = u16(out); out += t2
            bolds.append((s, u16(out))); links += [(s + a, s + b, u) for a, b, u in l2]
        else:
            t2, b2, l2 = parse_inline(m.group(2))
            s = u16(out); out += t2
            bolds += [(s + a, s + b) for a, b in b2]
            links.append((s, u16(out), m.group(3) if m.group(3).startswith("#tab:") else absu(m.group(3))))
        pos = m.end()
    out += text[pos:]
    return out, bolds, links

def tab_requests(tab_id, blks):
    text, paras, cursor = "", [], 1
    for kind, raw in blks:
        t, bolds, links = parse_inline(raw)
        start = cursor + u16(text)
        text += t + "\n"
        paras.append((kind, start, start + u16(t) + 1, bolds, links))
    rng = lambda a, b: {"startIndex": a, "endIndex": b, "tabId": tab_id}
    reqs = [{"insertText": {"location": {"index": 1, "tabId": tab_id}, "text": text}},
            {"updateParagraphStyle": {"range": rng(1, 1 + u16(text)), "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "fields": "namedStyleType"}}]
    i = 0
    while i < len(paras):
        kind, s, e, _, _ = paras[i]
        if kind.startswith("H"):
            reqs.append({"updateParagraphStyle": {"range": rng(s, e), "paragraphStyle": {"namedStyleType": "HEADING_" + kind[1], "keepWithNext": True}, "fields": "namedStyleType,keepWithNext"}})
            i += 1
        elif kind == "UL":
            j = i
            while j + 1 < len(paras) and paras[j + 1][0] == "UL": j += 1
            reqs.append({"createParagraphBullets": {"range": rng(s, paras[j][2]), "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
            i = j + 1
        else:
            i += 1
    for kind, s, e, bolds, links in paras:
        for a, b in bolds:
            reqs.append({"updateTextStyle": {"range": rng(s + a, s + b), "textStyle": {"bold": True}, "fields": "bold"}})
        for a, b, url in links:
            link = {"tabId": url[5:]} if url.startswith("#tab:") else {"url": url}
            reqs.append({"updateTextStyle": {"range": rng(s + a, s + b), "textStyle": {"link": link}, "fields": "link"}})
    return reqs

def index_blocks(tabs, archive_title, ids):
    b = [("H1", "grantandassociates.com – Website Content"),
         ("P", "The text of every page on the new grantandassociates.com, one tab per page. Edit the text here; Claude carries your changes into the site, but only when you ask, and only after you approve a preview."),
         ("H2", "Status key"),
         ("UL", "**🟢 Approved:** matches the site and has been reviewed."),
         ("UL", "**🟡 Edited:** based on the old site's text, changed for the new site (or edited by you since). Please review."),
         ("UL", "**🔴 New:** a page that did not exist on the old site. Please review."),
         ("P", "Click a page name below to open its tab. The status shows in each tab's name and in the list below. When you're happy with a tab, change its emoji to 🟢 (or ask Claude to). When you edit a 🟢 tab, change it to 🟡."),
         ("H2", "Pages")]
    for t in tabs:
        path = Path(t["path"]); fm, _ = build.read_page(path)
        url = f"/insights/{path.stem}/" if t["key"].startswith("post:") else (fm.get("url") or build.url_for(path))
        indent = "    " if t["parent"] else ""
        b.append(("UL", f"{indent}[{t['title']}](#tab:{ids[t['key']]})  {url}"))
    b += [("H2", "Rules"),
          ("UL", "Each tab has **Page settings** (address, SEO title, meta description and so on) and **Page text**, with real headings, bullets and links. Edit them like any document."),
          ("UL", "Text in [square brackets] and comments are notes. They are never published. [Photo: …] shows where a photo sits; [Button] marks a button; [Testimonial] marks a client quote."),
          ("UL", "To remove a page, write [Remove this page] at the top of its tab. Claude retires it and points its address somewhere sensible."),
          ("UL", "To add a page, add a tab named \"🔴 Page name\" and write its text."),
          ("UL", "Insights articles are the tabs under \"Insights\". To add an article, add a tab under it named \"🔴 Article title\"."),
          ("UL", f"The old site's text, exactly as it was in October 2026, is in the tabs under \"{archive_title}\". It is for reference only; nothing there is published."),
          ("H2", "To sync"),
          ("P", "Ask Claude: \"Sync the grantandassociates.com content doc.\" Claude reads every 🟡 and 🔴 tab, compares it with the site, applies the changes following the Grant and Associates playbook, shows you a preview and a list of changes, publishes only when you approve, and then sets the tabs to 🟢."),
          ("P", "Playbook (private): https://github.com/cellwood/grantandassociates-website-playbook")]
    return b

if __name__ == "__main__":
    cmd = sys.argv[1]
    tabs = tab_list()
    if cmd == "tabs":
        print(json.dumps([{k: t[k] for k in ("key", "title", "parent")} for t in tabs], ensure_ascii=False, indent=1))
    elif cmd == "preview":
        t = next(t for t in tabs if t["key"] == sys.argv[2])
        for kind, x in tab_blocks(t): print(kind, x)
    elif cmd == "index":
        ids = json.loads((OUT / "tabids.json").read_text())
        r = tab_requests(sys.argv[2], index_blocks(tabs, sys.argv[3], ids))
        (OUT / "index.json").write_text(json.dumps(r, ensure_ascii=False)); print(len(json.dumps(r)))
    elif cmd == "requests":
        ids = json.loads(Path(sys.argv[2]).read_text())
        d = OUT / "requests"; d.mkdir(exist_ok=True)
        for t in tabs:
            r = tab_requests(ids[t["key"]], tab_blocks(t))
            (d / (t["key"].replace(":", "__") + ".json")).write_text(json.dumps(r, ensure_ascii=False))
            print(f"{len(json.dumps(r, ensure_ascii=False)):6d} {t['title']}")
