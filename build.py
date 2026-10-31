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
FAVICON = (Path(SRC / "assets" / "favicon.svg").read_text())

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

BASE = SITE["url"].rstrip("/")
ORG, JUDY = BASE + "/#org", BASE + "/about/#judy"

def schema_ld(fm, url, title, desc, canonical, article):
    """JSON-LD for search engines and AI answers: who Judy and the firm are, what each page is, and where it sits."""
    org = {"@type": "ProfessionalService", "@id": ORG, "name": SITE["name"], "url": SITE["url"], "foundingDate": "1997",
           "description": SITE["description"], "telephone": SITE["phone_e164"], "logo": BASE + "/assets/logo.svg",
           "image": BASE + "/assets/img/share.jpg", "founder": {"@id": JUDY}, "areaServed": "San Francisco Bay Area and nationwide",
           "knowsAbout": ["Media training", "Presentation training", "Public speaking coaching", "Executive coaching", "Speechwriting", "TV talent coaching"]}
    judy = {"@type": "Person", "@id": JUDY, "name": "Judy Grant", "jobTitle": "Principal", "worksFor": {"@id": ORG},
            "url": BASE + "/about/", "image": BASE + "/assets/img/judy-grant-portrait.jpg",
            "description": DATA["schema"]["judy_description"], "knowsAbout": org["knowsAbout"]}
    graph = []
    if url == "/":
        graph += [org, judy, {"@type": "WebSite", "@id": BASE + "/#site", "url": SITE["url"], "name": SITE["name"], "publisher": {"@id": ORG}}]
    elif url == "/about/":
        graph += [org, judy, {"@type": "ProfilePage", "url": canonical, "name": title, "mainEntity": {"@id": JUDY}}]
    elif article:
        graph.append({"@type": "Article", "headline": fm["headline"], "description": desc, "url": canonical,
                      "mainEntityOfPage": canonical, "author": {"@type": "Person", "@id": JUDY, "name": "Judy Grant", "url": BASE + "/about/"},
                      "publisher": {"@id": ORG, "@type": "ProfessionalService", "name": SITE["name"]}, "articleSection": fm.get("topic", ""),
                      **({"datePublished": fm["date"]} if fm.get("date") else {}), **({"image": BASE + fm["image"]} if fm.get("image") else {})})
    elif url.startswith(("/coaching-training/", "/speaking-for-impact/")):
        graph.append({"@type": "Service", "name": re.sub(r" ·.*| \|.*", "", title), "description": desc, "url": canonical,
                      "provider": {"@id": ORG, "@type": "ProfessionalService", "name": SITE["name"]}, "areaServed": org["areaServed"]})
    # breadcrumbs: Home › parent section › this page
    parts = [p for p in url.strip("/").split("/") if p]
    if parts and not url.endswith(".html"):
        names = {p["url"]: p["short"] for p in PAGES}
        crumbs = [("Home", "/")] + [(names.get("/" + "/".join(parts[:i + 1]) + "/") or (fm.get("headline") if i == len(parts) - 1 else None), "/" + "/".join(parts[:i + 1]) + "/") for i in range(len(parts))]
        crumbs = [c for c in crumbs if c[0]]
        if len(crumbs) > 1:
            graph.append({"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": re.sub(r"<[^>]+>", "", n), "item": BASE + u} for i, (n, u) in enumerate(crumbs)]})
    if not graph: return ""
    return '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False) + "</script>\n"

def page_html(fm, content, url, article=False):
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
    if article: layout += " article"
    if fm.get("wide"): layout = "home"
    ld = schema_ld(fm, url, title, desc, canonical, article)
    image = BASE + (fm.get("image") or "/assets/img/share.jpg")
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
<meta property="og:type" content="{'article' if article else 'website'}">
<meta property="og:site_name" content="{SITE['name']}">
<meta property="og:image" content="{image}">
<meta name="twitter:card" content="summary_large_image">
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
IMG_DIR = SRC / "assets" / "img" / "insights"

def plain(md):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"<[^>]+>|[*#>_]", "", t)
    return re.sub(r"\s+", " ", t).strip()

def excerpt(body, limit=300):
    paras = [plain(p) for p in body.split("\n\n") if p.strip() and not p.lstrip().startswith(("#", "!", "<", "-", "1."))]
    text = " ".join(p for p in paras if p)
    if len(text) <= limit: return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > 120 else cut.rsplit(" ", 1)[0] + "…"

def img_width(path):
    import struct
    try: d = open(path, "rb").read(65536)
    except OSError: return 0
    if d[:8] == b"\x89PNG\r\n\x1a\n": return struct.unpack(">I", d[16:20])[0]
    if d[:3] == b"GIF": return struct.unpack("<H", d[6:8])[0]
    i = 2
    while i < len(d) - 9:
        if d[i] != 0xFF: i += 1; continue
        m = d[i + 1]
        if m in (0xC0, 0xC1, 0xC2): return struct.unpack(">H", d[i + 7:i + 9])[0]
        i += 2 + struct.unpack(">H", d[i + 2:i + 4])[0]
    return 0

def sharp(src, min_w=480):
    return src if img_width(SRC / src.lstrip("/").replace("assets/", "assets/", 1)) >= min_w else None

def full_size(src):
    name = src.rsplit("/", 1)[-1]
    big = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", name)
    return src.replace(name, big) if big != name and (IMG_DIR / big).exists() else src

for p in sorted((SRC / "insights").glob("*.md")):
    fm, body = read_page(p)
    slug = p.stem
    h1 = re.search(r"^# (.*)", body, re.M)
    body_wo_h1 = re.sub(r"^# .*\n", "", body, count=1, flags=re.M)
    img = re.search(r"!\[([^\]]*)\]\((/assets/img/insights/[^)]+)\)", body_wo_h1)
    lead = None
    if img and body_wo_h1.find(img.group(0)) < 400 and sharp(full_size(img.group(2))):  # a sharp image at the top becomes the lead image
        lead = {"src": full_size(img.group(2)), "alt": img.group(1)}
        body_wo_h1 = body_wo_h1.replace(img.group(0), "", 1)
    words = len(plain(body_wo_h1).split())
    ARTICLES.append({"path": p, "fm": fm, "body": body_wo_h1, "url": f"/insights/{slug}/", "title": h1.group(1) if h1 else slug,
                     "slug": slug, "lead": lead, "card_img": lead["src"] if lead else (sharp(full_size(img.group(2))) if img else None),
                     "excerpt": excerpt(body_wo_h1, 210), "minutes": max(1, round(words / 220)), "topic": fm.get("topic", "Presentation skills")})

def topic_slug(t): return re.sub(r"[^a-z0-9]+", "-", t.lower().replace("™", "")).strip("-")

def card_html(a, show_excerpt=True):
    media = f'<img src="{a["card_img"] or "/assets/mark-tile.svg"}" alt="" loading="lazy">'
    ex = f'<p>{html.escape(a["excerpt"])}</p>' if show_excerpt else ""
    return (f'<article class="post-card"><a class="post-media" href="{a["url"]}" tabindex="-1" aria-hidden="true">{media}</a>'
            f'<div class="post-body"><p class="post-topic">{a["topic"]}</p><h3><a href="{a["url"]}">{inline(a["title"])}</a></h3>{ex}'
            f'<p class="post-meta">{a["minutes"]} min read · <a href="{a["url"]}">Read more →</a></p></div></article>')

def write(url_or_file, text):
    target = OUT / (url_or_file.strip("/") + "/index.html" if url_or_file.endswith("/") else url_or_file.lstrip("/"))
    if url_or_file == "/": target = OUT / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)

def insights_list():
    order = DATA["site"]["insight_topics"]
    topics = [t for t in order if any(a["topic"] == t for a in ARTICLES)]
    chips = "".join(f'<a href="#{topic_slug(t)}">{t}</a>' for t in topics)
    guides = [a for a in ARTICLES if a["topic"] == "Free guides"]
    out = [f'<nav class="chips" aria-label="Topics">{chips}</nav>']
    for t in topics:
        items = sorted([a for a in ARTICLES if a["topic"] == t], key=lambda a: (a["card_img"] is None, a["title"]))
        out.append(f'<section class="topic" id="{topic_slug(t)}"><h2>{t}</h2><div class="post-grid">' + "".join(card_html(a) for a in items) + "</div></section>")
    return "\n".join(out)

def more_insights(a):
    same = [x for x in ARTICLES if x["topic"] == a["topic"] and x is not a]
    others = [x for x in ARTICLES if x["topic"] != a["topic"] and x["card_img"]]
    pick = (same + others)[:3]
    return '<section class="more"><h2>More insights</h2><div class="post-grid three">' + "".join(card_html(x, False) for x in pick) + "</div></section>"

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
<p class="form-error" hidden>Sorry, the message didn't go through. Please try again, or call 510.523.1112.</p>
</form>""" + ("" if not live else """
<script>
// Formspree's free plan can't redirect to our own page, so send in the background and go to /contact/thanks/ ourselves.
document.querySelector('.contact-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target, btn = f.querySelector('button'), err = f.querySelector('.form-error');
  btn.disabled = true; err.hidden = true;
  try {
    const r = await fetch(f.action, {method: 'POST', body: new FormData(f), headers: {Accept: 'application/json'}});
    if (r.ok) { location.href = '/contact/thanks/'; return; }
  } catch (_) {}
  err.hidden = false; btn.disabled = false;
});
</script>""")

def render(body):
    body = body.replace("{{insights}}", insights_list())
    body = re.sub(r"\{\{quote:([\w-]+)\}\}", lambda m: quote_html(m.group(1)), body)
    # The form goes in after markdown so its script isn't wrapped in <p> and flattened.
    return re.sub(r"(<p>)?\{\{contact_form\}\}(</p>)?", lambda m: form_html(), markdown(body))

def main():
    if OUT.exists(): shutil.rmtree(OUT)
    shutil.copytree(SRC / "assets", OUT / "assets")
    for pg in PAGES:
        write(pg["url"], page_html(pg["fm"], render(pg["body"]), pg["url"]))
    for a in ARTICLES:
        fm = dict(a["fm"]); fm.setdefault("related", ["/insights/", "/speaking-for-impact/", "/coaching-training/presentation-training/"])
        fm.setdefault("title", f'{re.sub(r"<[^>]+>", "", a["title"])} · Grant and Associates')
        fm["description"] = fm.get("description") or a["excerpt"][:160]
        fm["headline"] = re.sub(r"<[^>]+>", "", a["title"])
        d = re.match(r"(\d{4}-\d{2}-\d{2})-", fm.get("source", ""))
        if d: fm["date"] = d.group(1)
        if a["card_img"]: fm["image"] = a["card_img"]
        head = (f'<header class="post-head"><p class="post-topic"><a href="/insights/#{topic_slug(a["topic"])}">{a["topic"]}</a></p>'
                f'<h1>{inline(a["title"])}</h1><p class="post-meta">By Judy Grant · {a["minutes"]} min read</p></header>')
        lead = f'<figure class="lead"><img src="{a["lead"]["src"]}" alt="{html.escape(a["lead"]["alt"])}"></figure>' if a["lead"] else ""
        content = head + lead + '<div class="prose">' + render(a["body"]) + "</div>" + more_insights(a) + '<p class="back"><a href="/insights/">← All insights</a></p>'
        write(a["url"], page_html(fm, content, a["url"], article=True))
    # redirects: meta-refresh pages for old .html and folder addresses, plus a _redirects file for hosts that support it.
    # GitHub Pages downloads .php files instead of showing them, so old .php addresses are sent on by the 404 page instead.
    lines = []
    for old, new in DATA["redirects"].items():
        lines.append(f"{old} {new} 301")
        if old.endswith(".php"): continue
        page = f'<!doctype html><meta charset="utf-8"><title>Moved</title><link rel="canonical" href="{new}"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url={new}"><p>This page has moved to <a href="{new}">{new}</a>.</p>'
        write(old, page)
    (OUT / "_redirects").write_text("\n".join(lines) + "\n")
    # 404 (also forwards old addresses), sitemap, robots
    moved = json.dumps({o.lower(): n for o, n in DATA["redirects"].items()})
    forward = f'<script>(function(){{var m={moved};var p=location.pathname.toLowerCase();var n=m[p]||m[p.replace(/\\/$/,"")]||m[p+"/"];if(n)location.replace(n);}})();</script>'
    write("/404.html", page_html({"title": "Page not found · Grant and Associates"}, forward + markdown("# Page not found\n\nThat page isn't here. Try the [home page](/) or [Insights](/insights/), or [get in touch](/contact/)."), "/404.html"))
    urls = [p["url"] for p in PAGES if not p["fm"].get("noindex")] + [a["url"] for a in ARTICLES]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{SITE['url'].rstrip('/')}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (OUT / "robots.txt").write_text(("User-agent: *\nAllow: /\nSitemap: " + SITE["url"].rstrip("/") + "/sitemap.xml\n") if PRODUCTION else "User-agent: *\nDisallow: /\n")
    # llms.txt: a plain summary of the site for AI tools (llmstxt.org)
    sec = lambda pre: "".join(f"- [{p['short']}]({BASE}{p['url']}): {p['fm'].get('description', '')}\n" for p in PAGES if p["url"].startswith(pre) and p["url"] != pre and not p["fm"].get("noindex"))
    (OUT / "llms.txt").write_text(f"# {SITE['name']}\n\n> {SITE['description']}\n\n"
        f"Principal: Judy Grant. {DATA['schema']['judy_description']} Phone: {SITE['phone']}. Contact: {BASE}/contact/\n\n"
        f"## About\n\n- [About Judy Grant]({BASE}/about/): {next(p['fm'].get('description', '') for p in PAGES if p['url'] == '/about/')}\n"
        f"- [Speaking for Impact®]({BASE}/speaking-for-impact/): {next(p['fm'].get('description', '') for p in PAGES if p['url'] == '/speaking-for-impact/')}\n"
        f"- [Clients]({BASE}/clients/)\n\n"
        f"## Coaching and training\n\n{sec('/coaching-training/')}\n## Who we serve\n\n{sec('/who-we-serve/')}\n"
        f"## Insights (articles by Judy Grant)\n\n" + "".join(f"- [{re.sub(r'<[^>]+>', '', a['title'])}]({BASE}{a['url']}): {a['excerpt']}\n" for a in ARTICLES))
    if PRODUCTION and SITE.get("cname"): (OUT / "CNAME").write_text(SITE["cname"] + "\n")
    print(f"Built {len(PAGES)} pages, {len(ARTICLES)} articles, {len(DATA['redirects'])} redirects into {OUT.relative_to(ROOT)}/")

if __name__ == "__main__":
    main()
