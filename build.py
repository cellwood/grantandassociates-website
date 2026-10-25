"""Build the grantandassociates.com static site.

  python3 build.py              # preview build into docs/
  python3 build.py --production # same, for publishing (adds analytics if configured)

Sources: src/pages/*.md (one per page; "__" in a filename stands for "/"),
src/insights/*.md (articles), src/data/*.json (navigation, quotes, redirects, settings),
src/assets/ (CSS, images). Standard library only.
"""
import html, json, re, shutil, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC, OUT = ROOT / "src", ROOT / "docs"
DATA = {p.stem: json.loads(p.read_text()) for p in (SRC / "data").glob("*.json")}
SITE = DATA["site"]
PRODUCTION = "--production" in sys.argv

# ---------- Markdown (small subset) ----------

def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}" loading="lazy">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{m.group(2)}"{" rel=\"noopener\"" if m.group(2).startswith("http") else ""}>{m.group(1)}</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    return t

def markdown(md):
    out, para, lst, quote = [], [], None, []
    def flush():
        nonlocal para, lst, quote
        if para: out.append("<p>" + inline(" ".join(para)) + "</p>"); para = []
        if lst: out.append(f"<{lst[0]}>" + "".join(f"<li>{inline(i)}</li>" for i in lst[1]) + f"</{lst[0]}>"); lst = None
        if quote: out.append("<blockquote>" + markdown("\n".join(quote)) + "</blockquote>"); quote = []
    for line in md.split("\n"):
        s = line.rstrip()
        if not s.strip(): flush(); continue
        if s.startswith(">"):
            if para or lst: flush()
            quote.append(s[1:].lstrip()); continue
        if quote: flush()
        if s.lstrip().startswith("<") and not s.lstrip().startswith("<http"):
            flush(); out.append(s); continue
        m = re.match(r"(#{1,4}) (.*)", s)
        if m:
            flush(); n = len(m.group(1)); txt = m.group(2)
            anchor = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>|\[|\]\([^)]*\)", "", txt).lower()).strip("-")
            out.append(f'<h{n} id="{anchor}">{inline(txt)}</h{n}>'); continue
        m = re.match(r"\s*(-|\d+\.) (.*)", s)
        if m:
            kind = "ul" if m.group(1) == "-" else "ol"
            if para: flush()
            if lst and lst[0] != kind: flush()
            if not lst: lst = (kind, [])
            lst[1].append(m.group(2)); continue
        if s == "---": flush(); out.append("<hr>"); continue
        if lst and line.startswith("  "): lst[1][-1] += " " + s.strip(); continue
        if lst: flush()
        para.append(s.strip())
    flush()
    return "\n".join(out)

def read_page(path):
    raw = path.read_text()
    fm, body = {}, raw
    if raw.startswith("---\n"):
        head, body = raw[4:].split("\n---\n", 1)
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1); v = v.strip()
                fm[k.strip()] = json.loads(v) if v[:1] in "[{\"" else v
    return fm, body

# ---------- Layout ----------

LOGO = (Path(SRC / "assets" / "logo.svg").read_text())

def nav_html(current):
    items = []
    for item in DATA["nav"]:
        active = current == item["url"] or (current.startswith(item["url"]) and item["url"] != "/")
        cls = ' class="active"' if active else ""
        if "children" in item:
            kids = "".join(f'<li><a href="{c["url"]}"{" aria-current=page" if c["url"] == current else ""}>{c["label"]}</a></li>' for c in item["children"])
            items.append(f'<li class="has-sub"><a href="{item["url"]}"{cls}>{item["label"]}</a><ul class="sub">{kids}</ul></li>')
        else:
            extra = ' class="cta"' if item.get("cta") else cls
            items.append(f'<li><a href="{item["url"]}"{extra}>{item["label"]}</a></li>')
    return "<ul>" + "".join(items) + "</ul>"

def quote_html(key):
    q = DATA["quotes"].get(key)
    if not q: return ""
    return (f'<figure class="quote"><blockquote>{inline(q["text"])}</blockquote>'
            f'<figcaption><strong>{q["name"]}</strong><br>{q["role"]}</figcaption></figure>')

def related_html(urls):
    if not urls: return ""
    titles = {p["url"]: p["short"] for p in PAGES}
    links = "".join(f'<li><a href="{u}">{titles.get(u, u)}</a></li>' for u in urls)
    return f'<nav class="related" aria-label="Related"><h2>Related</h2><ul>{links}</ul></nav>'

def page_html(fm, content, url):
    title = fm.get("title") or SITE["name"]
    desc = fm.get("description", SITE["description"])
    canonical = SITE["url"].rstrip("/") + url
    hero = ""
    if fm.get("hero"):
        hero = f'<section class="hero"><div class="wrap"><p class="eyebrow">{fm.get("eyebrow", "")}</p><h1>{inline(fm["hero"])}<span class="bang" aria-hidden="true">!</span></h1>{"<p class=lede>" + inline(fm["lede"]) + "</p>" if fm.get("lede") else ""}</div></section>'
    aside = ""
    if fm.get("quote") or fm.get("related"):
        aside = f'<aside class="side">{quote_html(fm.get("quote", ""))}{related_html(fm.get("related", []))}{'' if url.startswith('/contact/') else '<p class="side-cta"><a class="button" href="/contact/">Contact Judy</a></p>'}</aside>'
    layout = "home" if url == "/" else ("with-side" if aside else "single")
    ld = ""
    if url == "/":
        ld = '<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "ProfessionalService", "name": SITE["name"],
            "url": SITE["url"], "foundingDate": "1997", "description": SITE["description"],
            "founder": {"@type": "Person", "name": "Judy Grant"}, "telephone": SITE["phone_e164"],
            "areaServed": "San Francisco Bay Area and nationwide"}) + "</script>"
    analytics = SITE.get("analytics_snippet", "") if PRODUCTION else ""
    robots = "" if PRODUCTION else '<meta name="robots" content="noindex">'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
{robots}
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE['name']}">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@400;500;600&family=Libre+Franklin:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
{ld}{analytics}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="/" aria-label="Grant and Associates home">{LOGO}</a>
    <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="main-nav" aria-label="Menu"><span></span><span></span><span></span></button>
    <nav class="main-nav" id="main-nav" aria-label="Main">{nav_html(url)}</nav>
  </div>
</header>
{hero}
<main id="main" class="wrap {layout}">
<article class="content">
{content}
</article>
{aside}
</main>
<footer class="site-footer">
  <div class="wrap footer-inner">
    <div>
      <p class="footer-name">{SITE['name']}</p>
      <p>{SITE['tagline']}</p>
      <p class="small">Prefer to call? <a href="tel:{SITE['phone_e164']}">{SITE['phone']}</a></p>
    </div>
    <nav aria-label="Footer"><ul>
      <li><a href="/coaching-training/">Coaching &amp; Training</a></li>
      <li><a href="/speaking-for-impact/">Speaking for Impact®</a></li>
      <li><a href="/about/">About Judy Grant</a></li>
      <li><a href="/insights/">Insights</a></li>
      <li><a href="/contact/">Contact</a></li>
    </ul></nav>
  </div>
  <div class="wrap legal small">
    <p>© 1997–<span data-year>{date.today().year}</span> Grant and Associates. All rights reserved. Speaking for Impact® is a registered trademark of Grant and Associates. · <a href="/privacy/">Privacy</a></p>
  </div>
</footer>
<script>document.querySelectorAll('[data-year]').forEach(e=>e.textContent=new Date().getFullYear());
var t=document.querySelector('.menu-toggle');t.addEventListener('click',function(){{var o=document.body.classList.toggle('nav-open');t.setAttribute('aria-expanded',o)}});</script>
</body>
</html>
"""

# ---------- Pages ----------

def url_for(path):
    stem = path.stem
    if stem == "index": return "/"
    return "/" + stem.replace("__", "/") + "/"

PAGES = []
for p in sorted((SRC / "pages").glob("*.md")):
    fm, body = read_page(p)
    url = fm.get("url") or url_for(p)
    h1 = re.search(r"^# (.*)", body, re.M)
    PAGES.append({"path": p, "fm": fm, "body": body, "url": url, "short": fm.get("short") or (h1.group(1) if h1 else fm.get("title", url))})

ARTICLES = []
for p in sorted((SRC / "insights").glob("*.md")):
    fm, body = read_page(p)
    slug = p.stem
    h1 = re.search(r"^# (.*)", body, re.M)
    ARTICLES.append({"path": p, "fm": fm, "body": body, "url": f"/insights/{slug}/", "title": h1.group(1) if h1 else slug, "slug": slug})

def write(url_or_file, text):
    target = OUT / (url_or_file.strip("/") + "/index.html" if url_or_file.endswith("/") else url_or_file.lstrip("/"))
    if url_or_file == "/": target = OUT / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)

def insights_list():
    groups = {}
    for a in ARTICLES:
        groups.setdefault(a["fm"].get("topic", "Speaking tips"), []).append(a)
    order = DATA["site"]["insight_topics"]
    out = []
    for topic in order + [t for t in groups if t not in order]:
        if topic not in groups: continue
        items = "".join(f'<li><a href="{a["url"]}">{inline(a["title"])}</a>{"<span>" + inline(a["fm"]["summary"]) + "</span>" if a["fm"].get("summary") else ""}</li>' for a in sorted(groups[topic], key=lambda a: a["title"]))
        out.append(f'<section class="topic"><h2>{topic}</h2><ul class="article-list">{items}</ul></section>')
    return "\n".join(out)

def form_html():
    fid = SITE.get("formspree_id", "")
    live = bool(fid) and fid != "FORM_ID"
    note = "" if live else '<p class="notice">Preview: this form is not connected yet, so it will not send. It will deliver to Judy once the form service is set up.</p>'
    return f"""{note}<form class="contact-form" action="https://formspree.io/f/{fid or 'FORM_ID'}" method="POST"{'' if live else ' onsubmit="return false"'}>
<input type="hidden" name="_subject" value="Website inquiry, grantandassociates.com">
<input type="hidden" name="_next" value="{SITE['url'].rstrip('/')}/contact/thanks/">
<p class="hp"><label>Leave this empty <input type="text" name="_gotcha" tabindex="-1" autocomplete="off"></label></p>
<p><label for="f-name">Name</label><input id="f-name" name="name" autocomplete="name" required></p>
<p><label for="f-email">Email</label><input id="f-email" name="email" type="email" autocomplete="email" required></p>
<p><label for="f-org">Organization <span class="opt">(optional)</span></label><input id="f-org" name="organization" autocomplete="organization"></p>
<p><label for="f-msg">How can Judy help?</label><textarea id="f-msg" name="message" rows="6" required></textarea></p>
<p><button class="button" type="submit">Send message</button></p>
</form>"""

def render(body):
    body = body.replace("{{insights}}", insights_list()).replace("{{contact_form}}", form_html())
    body = re.sub(r"\{\{quote:([\w-]+)\}\}", lambda m: quote_html(m.group(1)), body)
    return markdown(body)

def main():
    if OUT.exists(): shutil.rmtree(OUT)
    shutil.copytree(SRC / "assets", OUT / "assets")
    for pg in PAGES:
        write(pg["url"], page_html(pg["fm"], render(pg["body"]), pg["url"]))
    for a in ARTICLES:
        fm = dict(a["fm"]); fm.setdefault("related", ["/insights/", "/speaking-for-impact/", "/coaching-training/presentation-training/"])
        fm.setdefault("title", f'{re.sub(r"<[^>]+>", "", a["title"])} · Grant and Associates')
        body = a["body"] + '\n\n<p class="back"><a href="/insights/">← All insights</a></p>'
        write(a["url"], page_html(fm, render(body), a["url"]))
    # redirects: meta-refresh pages for directory-style old addresses, plus a _redirects file for hosts that support it
    lines = []
    for old, new in DATA["redirects"].items():
        lines.append(f"{old} {new} 301")
        target = old if old.endswith("/") else old
        page = f'<!doctype html><meta charset="utf-8"><title>Moved</title><link rel="canonical" href="{new}"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url={new}"><p>This page has moved to <a href="{new}">{new}</a>.</p>'
        write(target if target.endswith("/") else target, page)
    (OUT / "_redirects").write_text("\n".join(lines) + "\n")
    # 404, sitemap, robots
    write("/404.html", page_html({"title": "Page not found · Grant and Associates"}, markdown("# Page not found\n\nThat page isn't here. Try the [home page](/) or [Insights](/insights/), or [get in touch](/contact/)."), "/404.html"))
    urls = [p["url"] for p in PAGES if not p["fm"].get("noindex")] + [a["url"] for a in ARTICLES]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{SITE['url'].rstrip('/')}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (OUT / "robots.txt").write_text(("User-agent: *\nAllow: /\nSitemap: " + SITE["url"].rstrip("/") + "/sitemap.xml\n") if PRODUCTION else "User-agent: *\nDisallow: /\n")
    if PRODUCTION and SITE.get("cname"): (OUT / "CNAME").write_text(SITE["cname"] + "\n")
    print(f"Built {len(PAGES)} pages, {len(ARTICLES)} articles, {len(DATA['redirects'])} redirects into {OUT.relative_to(ROOT)}/")

if __name__ == "__main__":
    main()
