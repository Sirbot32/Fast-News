#!/usr/bin/env python3
"""Fast-News — build a static "week that mattered" news page.

Usage:
  python3 main.py                 # fetch live feeds, build site/, fall back to
                                  # sample data if nothing is reachable
  python3 main.py --sample        # force offline sample data
  python3 main.py --serve         # build, then serve site/ at localhost:8000
  python3 main.py --days 3        # only consider the last 3 days
  python3 main.py --max 40        # cap number of stories shown

Stdlib only — no pip install required.
"""

from __future__ import annotations

import argparse
import http.server
import functools
import socketserver
import sys
import webbrowser
from datetime import datetime, timezone

from fastnews.config import load_feeds, SITE_DIR
from fastnews.fetch import fetch_all
from fastnews.rank import rank
from fastnews.build import build_site
from fastnews.sample_data import load_sample


def _serve(directory: str, port: int = 8000) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}/"
        print(f"Serving {directory} at {url}  (Ctrl+C to stop)")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build the Fast-News static site.")
    p.add_argument("--sample", action="store_true", help="force offline sample data")
    p.add_argument("--days", type=int, default=7, help="time window in days (default 7)")
    p.add_argument("--max", type=int, default=60, help="max stories to show (default 60)")
    p.add_argument("--threshold", type=float, default=0.5,
                   help="headline similarity threshold for clustering (0-1)")
    p.add_argument("--serve", action="store_true", help="serve site/ after building")
    p.add_argument("--port", type=int, default=8000, help="port for --serve")
    p.add_argument("--open", action="store_true", help="open the built page in a browser")
    args = p.parse_args(argv)

    errors: list[tuple[str, str]] = []
    sample_mode = args.sample

    if args.sample:
        articles, now = load_sample()
        print(f"Sample mode: {len(articles)} fixture articles.")
    else:
        feeds = load_feeds()
        print(f"Fetching {len(feeds)} feeds (last {args.days} days)…")
        result = fetch_all(feeds, days=args.days)
        articles, errors = result.articles, result.errors
        now = datetime.now(timezone.utc)
        for name, msg in errors:
            print(f"  ! {name}: {msg}", file=sys.stderr)
        print(f"  {len(articles)} articles from "
              f"{len(feeds) - len(errors)}/{len(feeds)} feeds.")
        if not articles:
            print("No live articles reachable — falling back to sample data.",
                  file=sys.stderr)
            articles, now = load_sample()
            sample_mode = True

    clusters = rank(articles, threshold=args.threshold, now=now)
    if args.max and len(clusters) > args.max:
        clusters = clusters[: args.max]

    index = build_site(clusters, now=now, errors=errors, sample_mode=sample_mode)
    print(f"Built {len(clusters)} ranked stories -> {index}")
    top = clusters[:5]
    if top:
        print("\nTop stories:")
        for i, cl in enumerate(top, 1):
            print(f"  {i}. [{cl.source_count}x] {cl.representative.title}")

    if args.serve:
        _serve(SITE_DIR, port=args.port)
    elif args.open:
        try:
            webbrowser.open(f"file://{index}")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
