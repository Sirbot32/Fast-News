"""Render ranked clusters into a static, self-contained site."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone

from .config import SITE_DIR
from .rank import Cluster

# Number of top stories that get a summary blurb shown.
SUMMARY_TOP_N = 5

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_summary(text: str, limit: int = 220) -> str:
    """Turn a raw RSS/Atom description into plain, trimmed summary text.

    Feed blurbs often contain HTML tags, entities, and trailing boilerplate
    ('Continue reading...'). Strip tags, unescape entities, collapse
    whitespace, and truncate at a word boundary.
    """
    if not text:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", text))
    text = _WS_RE.sub(" ", text).strip()
    # Drop common 'read more' tails.
    text = re.sub(r"\s*(Continue reading|Read more|Read full story).*$", "",
                  text, flags=re.IGNORECASE)
    if len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.-")
        text = cut + "…"
    return text


def _ago(dt: datetime, now: datetime) -> str:
    secs = max(0, int((now - dt).total_seconds()))
    if secs < 3600:
        m = secs // 60
        return f"{m}m ago" if m else "just now"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def clusters_to_data(clusters: list[Cluster], now: datetime) -> list[dict]:
    out = []
    for rank_idx, cl in enumerate(clusters, start=1):
        rep = cl.representative
        out.append({
            "rank": rank_idx,
            "title": rep.title,
            "link": rep.link,
            "summary": clean_summary(rep.summary),
            "sources": cl.sources,
            "source_count": cl.source_count,
            "categories": cl.categories,
            "latest": cl.latest.isoformat(),
            "ago": _ago(cl.latest, now),
            "score": round(cl.score, 3),
            "also": [
                {"source": a.source, "title": a.title, "link": a.link}
                for a in cl.articles if a is not rep
            ],
        })
    return out


def _render_story(story: dict) -> str:
    cats = " ".join(html.escape(c) for c in story["categories"])
    badge = story["source_count"]
    badge_label = "source" if badge == 1 else "sources"
    sources = " · ".join(html.escape(s) for s in story["sources"])
    title = html.escape(story["title"])
    link = html.escape(story["link"] or "#")

    # Summary blurb under the top N headlines only.
    summary_html = ""
    if story["rank"] <= SUMMARY_TOP_N and story["summary"]:
        summary_html = f'<p class="summary">{html.escape(story["summary"])}</p>'

    # Explicit "Read full story" link to the source article.
    read_html = ""
    if story["link"]:
        read_html = (f'<a class="read" href="{link}" target="_blank" rel="noopener">'
                     f'Read full story →</a>')

    also_html = ""
    if story["also"]:
        items = "".join(
            f'<li><a href="{html.escape(a["link"] or "#")}" target="_blank" rel="noopener">'
            f'<span class="src">{html.escape(a["source"])}</span> {html.escape(a["title"])}</a></li>'
            for a in story["also"]
        )
        also_html = (
            f'<details class="also"><summary>Also covered by {len(story["also"])} more</summary>'
            f'<ul>{items}</ul></details>'
        )
    meta = f"{sources} · {html.escape(story['ago'])}"
    return f"""
    <article class="story" data-cats="{cats}">
      <div class="count" title="Covered by {badge} {badge_label}">
        <span class="n">{badge}</span><span class="lbl">{badge_label}</span>
      </div>
      <div class="body">
        <h2><a href="{link}" target="_blank" rel="noopener">{title}</a></h2>
        {summary_html}
        <div class="meta">{meta}</div>
        {read_html}
        {also_html}
      </div>
    </article>"""


def render_html(clusters: list[Cluster], now: datetime,
                errors: list[tuple[str, str]] | None = None,
                sample_mode: bool = False) -> str:
    data = clusters_to_data(clusters, now)
    # Category filter buttons from whatever categories actually appear.
    cats: list[str] = []
    for s in data:
        for c in s["categories"]:
            if c not in cats:
                cats.append(c)
    cat_links = '<a class="cat active" data-cat="*">All</a>' + "".join(
        f'<a class="cat" data-cat="{html.escape(c)}">{html.escape(c)}</a>' for c in cats
    )
    stories_html = "\n".join(_render_story(s) for s in data) or \
        '<p class="empty">No stories yet. Run <code>python3 main.py</code> with network access.</p>'

    generated = now.strftime("%d %b %Y, %H:%M UTC")
    note = ""
    if sample_mode:
        note = ('<div class="note">Showing sample data — live feeds were '
                'unreachable. Run again with network access for real news.</div>')
    elif errors:
        note = (f'<div class="note">{len(errors)} feed(s) skipped this run '
                f'({html.escape(", ".join(n for n, _ in errors))}).</div>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fast News</title>
<script>try{{document.documentElement.dataset.theme=localStorage.getItem('theme')||'light';}}catch(e){{}}</script>
<style>
  :root {{
    --bg:#ffffff; --text:#111111; --muted:#6b7280; --line:#e6e6e6;
    --link:#0b57d0; --box:#f3f4f6; --boxtext:#111111;
  }}
  html[data-theme="dark"] {{
    --bg:#15171a; --text:#e9eaec; --muted:#9aa1ab; --line:#2a2d33;
    --link:#7fb1ff; --box:#23262c; --boxtext:#e9eaec;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:680px; margin:0 auto; padding:0 20px; }}
  header {{ border-bottom:1px solid var(--line); padding:18px 0 0; }}
  .bar {{ display:flex; align-items:center; justify-content:space-between; }}
  .logo {{ font-size:22px; font-weight:800; letter-spacing:-0.4px; }}
  .toggle {{ background:none; border:1px solid var(--line); color:var(--muted);
    border-radius:6px; padding:5px 12px; font-size:13px; cursor:pointer; }}
  .toggle:hover {{ color:var(--text); }}
  .sub {{ color:var(--muted); font-size:13px; margin-top:4px; }}
  .cats {{ margin-top:12px; padding-bottom:12px; font-size:14px; }}
  .cat {{ color:var(--muted); text-decoration:none; cursor:pointer; margin-right:14px; }}
  .cat:hover {{ color:var(--text); }}
  .cat.active {{ color:var(--text); font-weight:700; }}
  main {{ padding:8px 0 60px; }}
  .note {{ color:var(--muted); font-size:13px; padding:12px 0; border-bottom:1px solid var(--line); }}
  .story {{ display:flex; gap:16px; padding:18px 0; border-bottom:1px solid var(--line); }}
  .count {{ display:flex; flex-direction:column; align-items:center; justify-content:flex-start;
    min-width:50px; background:var(--box); color:var(--boxtext); border-radius:6px;
    padding:8px 6px; height:fit-content; }}
  .count .n {{ font-size:20px; font-weight:800; line-height:1; }}
  .count .lbl {{ font-size:10.5px; color:var(--muted); margin-top:3px; text-transform:uppercase;
    letter-spacing:.3px; }}
  .body {{ flex:1; min-width:0; }}
  .story h2 {{ margin:0; font-size:18px; line-height:1.35; font-weight:700; }}
  .story h2 a {{ color:var(--text); text-decoration:none; }}
  .story h2 a:hover {{ text-decoration:underline; }}
  .summary {{ margin:6px 0 0; font-size:14.5px; color:var(--muted); }}
  .meta {{ font-size:12.5px; color:var(--muted); margin-top:8px; }}
  .read {{ display:inline-block; margin-top:8px; font-size:13px; color:var(--link);
    text-decoration:none; }}
  .read:hover {{ text-decoration:underline; }}
  .also {{ margin-top:8px; font-size:13px; }}
  .also summary {{ cursor:pointer; color:var(--link); }}
  .also ul {{ margin:8px 0 0; padding-left:16px; }}
  .also li {{ margin:4px 0; }}
  .also a {{ color:var(--text); text-decoration:none; }}
  .also a:hover {{ text-decoration:underline; }}
  .also .src {{ color:var(--muted); font-size:12px; }}
  .empty {{ color:var(--muted); padding:24px 0; }}
  footer {{ color:var(--muted); font-size:12px; padding:24px 0 40px; }}
  footer a {{ color:var(--muted); }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="bar">
      <div class="logo">Fast News</div>
      <button id="themeBtn" class="toggle" type="button">Dark</button>
    </div>
    <div class="sub">Top stories this week · {generated} · {len(data)} stories</div>
    <nav class="cats">{cat_links}</nav>
  </div>
</header>
<main class="wrap">
  {note}
  {stories_html}
</main>
<footer class="wrap">
  Fast News · ranked by how many outlets carried each story · <a href="data.json">data.json</a>
</footer>
<script>
  const btn = document.getElementById('themeBtn');
  function applyTheme(t) {{
    document.documentElement.dataset.theme = t;
    btn.textContent = (t === 'dark') ? 'Light' : 'Dark';
  }}
  applyTheme(document.documentElement.dataset.theme || 'light');
  btn.addEventListener('click', () => {{
    const next = (document.documentElement.dataset.theme === 'dark') ? 'light' : 'dark';
    try {{ localStorage.setItem('theme', next); }} catch (e) {{}}
    applyTheme(next);
  }});

  const links = document.querySelectorAll('.cat');
  const stories = document.querySelectorAll('.story');
  links.forEach(b => b.addEventListener('click', (e) => {{
    e.preventDefault();
    links.forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    const cat = b.dataset.cat;
    stories.forEach(s => {{
      const cats = (s.dataset.cats || '').split(' ');
      s.style.display = (cat === '*' || cats.includes(cat)) ? '' : 'none';
    }});
  }}));
</script>
</body>
</html>"""


def build_site(clusters: list[Cluster], now: datetime | None = None,
               errors: list[tuple[str, str]] | None = None,
               sample_mode: bool = False, out_dir: str = SITE_DIR) -> str:
    now = now or datetime.now(timezone.utc)
    os.makedirs(out_dir, exist_ok=True)
    data = clusters_to_data(clusters, now)
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated": now.isoformat(), "stories": data}, fh,
                  ensure_ascii=False, indent=2)
    index = os.path.join(out_dir, "index.html")
    with open(index, "w", encoding="utf-8") as fh:
        fh.write(render_html(clusters, now, errors=errors, sample_mode=sample_mode))
    return index
