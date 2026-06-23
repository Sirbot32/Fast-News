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


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        net = urlparse(url).netloc
        return net[4:] if net.startswith("www.") else net
    except Exception:
        return ""


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
    dom = html.escape(_domain(story["link"]))

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
    return f"""
    <article class="story" data-cats="{cats}">
      <div class="rank">{story['rank']}</div>
      <div class="body">
        <h2><a href="{link}" target="_blank" rel="noopener">{title}</a></h2>
        <div class="meta">
          <span class="coverage" title="Covered by {badge} distinct sources">🔥 {badge} {badge_label}</span>
          <span class="dot">·</span>
          <span class="time">{html.escape(story['ago'])}</span>
          <span class="dot">·</span>
          <span class="domain">{dom}</span>
        </div>
        {summary_html}
        <div class="sources">{sources}</div>
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
    cat_buttons = '<button class="cat active" data-cat="*">All</button>' + "".join(
        f'<button class="cat" data-cat="{html.escape(c)}">{html.escape(c)}</button>' for c in cats
    )
    stories_html = "\n".join(_render_story(s) for s in data) or \
        '<p class="empty">No stories yet. Run <code>python3 main.py</code> with network access.</p>'

    generated = now.strftime("%a %d %b %Y, %H:%M UTC")
    note = ""
    if sample_mode:
        note = ('<div class="note">Showing <strong>sample data</strong> — '
                'live feeds were unreachable. Run again with network access for real news.</div>')
    elif errors:
        note = (f'<div class="note">{len(errors)} feed(s) skipped this run '
                f'({html.escape(", ".join(n for n, _ in errors))}).</div>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fast-News — the week that mattered</title>
<style>
  :root {{
    --bg:#0f1115; --card:#181b22; --card2:#1f232c; --text:#e8eaed;
    --muted:#9aa3b2; --accent:#ff6a3d; --line:#2a2f3a; --link:#7fb1ff;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{ --bg:#f5f6f8; --card:#fff; --card2:#f0f2f5; --text:#16181d;
      --muted:#5b6472; --accent:#e8541f; --line:#e3e6eb; --link:#1a5fd0; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
    font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  header {{ position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
    padding:16px 20px; z-index:5; }}
  .wrap {{ max-width:760px; margin:0 auto; }}
  .brand {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }}
  .brand h1 {{ margin:0; font-size:22px; letter-spacing:-0.5px; }}
  .brand .accent {{ color:var(--accent); }}
  .brand .tag {{ color:var(--muted); font-size:13px; }}
  .gen {{ color:var(--muted); font-size:12px; margin-top:4px; }}
  .cats {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }}
  .cat {{ background:var(--card2); color:var(--text); border:1px solid var(--line);
    border-radius:999px; padding:5px 14px; font-size:13px; cursor:pointer; }}
  .cat.active {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
  main {{ padding:18px 20px 60px; }}
  .note {{ background:var(--card2); border:1px solid var(--line); border-radius:10px;
    padding:10px 14px; font-size:13px; color:var(--muted); margin-bottom:16px; }}
  .story {{ display:flex; gap:14px; background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:14px 16px; margin-bottom:12px; }}
  .rank {{ font-size:20px; font-weight:700; color:var(--muted); min-width:28px; text-align:right; }}
  .body {{ flex:1; min-width:0; }}
  .story h2 {{ margin:0 0 6px; font-size:17px; line-height:1.35; }}
  .story h2 a {{ color:var(--text); text-decoration:none; }}
  .story h2 a:hover {{ color:var(--link); }}
  .meta {{ font-size:12.5px; color:var(--muted); display:flex; gap:7px; align-items:center; flex-wrap:wrap; }}
  .coverage {{ color:var(--accent); font-weight:600; }}
  .dot {{ opacity:.5; }}
  .summary {{ margin:8px 0 0; font-size:14.5px; color:var(--text); opacity:.92; }}
  .sources {{ font-size:12.5px; color:var(--muted); margin-top:6px; }}
  .read {{ display:inline-block; margin-top:8px; font-size:13px; font-weight:600;
    color:var(--accent); text-decoration:none; }}
  .read:hover {{ text-decoration:underline; }}
  .also {{ margin-top:8px; font-size:13px; }}
  .also summary {{ cursor:pointer; color:var(--link); }}
  .also ul {{ margin:8px 0 0; padding-left:16px; }}
  .also li {{ margin:4px 0; }}
  .also a {{ color:var(--text); text-decoration:none; }}
  .also a:hover {{ color:var(--link); }}
  .also .src {{ color:var(--muted); font-size:12px; }}
  .empty {{ color:var(--muted); }}
  footer {{ text-align:center; color:var(--muted); font-size:12px; padding:24px; }}
  footer a {{ color:var(--muted); }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="brand">
      <h1>Fast<span class="accent">·</span>News</h1>
      <span class="tag">the week that mattered, ranked by how many outlets carried it</span>
    </div>
    <div class="gen">Updated {generated} · {len(data)} stories</div>
    <div class="cats">{cat_buttons}</div>
  </div>
</header>
<main class="wrap">
  {note}
  {stories_html}
</main>
<footer class="wrap">
  Fast-News · importance = cross-source coverage · <a href="data.json">data.json</a>
</footer>
<script>
  const buttons = document.querySelectorAll('.cat');
  const stories = document.querySelectorAll('.story');
  buttons.forEach(b => b.addEventListener('click', () => {{
    buttons.forEach(x => x.classList.remove('active'));
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
