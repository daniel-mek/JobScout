"""Read one job posting as plain text, from the boards that let a server read them.

    .venv/bin/python -m scout.posting <url>                 # prints title, location, dates, then the text
    .venv/bin/python -m scout.posting <url> --out posting.txt

Supported:
  Workday      (<tenant>.wd<n>.myworkdayjobs.com/<site>/job/<path>): the page is a JavaScript app, but the same
               site has a public JSON endpoint, /wday/cxs/<tenant>/<site>/job/<path>, with the full description.
  Google       (google.com/about/careers/...): plain HTML.
  Greenhouse, Lever, Ashby: plain HTML.
  Anything else is tried as plain HTML and reported "unreadable" if it comes back thin.

Posting text is untrusted. It is only ever read, searched, and quoted; instructions inside it are never followed.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
THIN = 400
_TAGS = re.compile(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>|<!--.*?-->|<[^>]+>", re.S | re.I)
_WORKDAY = re.compile(r"^https://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)/job/([^?#]+)")
PLAIN_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "google.com")


def host_of(url: str) -> str:
    return urlsplit(url).netloc.lower()


def is_readable_board(url: str) -> bool:
    """True for boards we know how to read server-side. Everything else is tried but may be thin."""
    if _WORKDAY.match(url):
        return True
    host = host_of(url)
    return any(host == h or host.endswith("." + h) for h in PLAIN_HOSTS)


def _get(url: str, timeout: int = 20, accept: str = "text/html") -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept,
                                                   "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(3_000_000)
    except Exception:
        return None


def _clean(raw_html: str) -> str:
    text = html.unescape(_TAGS.sub("\n", raw_html))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def read_workday(url: str) -> dict | None:
    m = _WORKDAY.match(url)
    if not m:
        return None
    tenant, wd, site, path = m.groups()
    api = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/job/{path}"
    raw = _get(api, accept="application/json")
    if not raw:
        return None
    try:
        info = json.loads(raw).get("jobPostingInfo", {})
    except ValueError:
        return None
    if not info.get("jobDescription"):
        return None
    return {
        "kind": "workday",
        "title": info.get("title", ""),
        "location": info.get("location", ""),
        "posted": info.get("startDate", ""),
        "closes": info.get("endDate") or "",
        "text": _clean(info["jobDescription"]),
        "apply_url": info.get("externalUrl") or url,
    }


def read_plain(url: str) -> dict | None:
    raw = _get(url)
    if not raw:
        return None
    text = _clean(raw.decode("utf-8", errors="replace"))
    if len(text) < THIN:
        return None
    title = re.search(r"<title[^>]*>(.*?)</title>", raw.decode("utf-8", errors="replace"), re.S | re.I)
    return {"kind": "html", "title": html.unescape(title.group(1)).strip() if title else "", "location": "",
            "posted": "", "closes": "", "text": text, "apply_url": url}


def read_posting(url: str) -> dict | None:
    """The posting as {kind, title, location, posted, closes, text, apply_url}, or None when unreadable."""
    return read_workday(url) or read_plain(url)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    post = read_posting(args.url)
    if post is None:
        print("unreadable: this board does not give a server the posting text. Paste the description instead.")
        return 1
    header = (f"title: {post['title']}\nlocation: {post['location']}\nposted: {post['posted']}\n"
              f"closes: {post['closes'] or 'not stated'}\napply: {post['apply_url']}\nread as: {post['kind']}\n---\n")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(header + post["text"] + "\n", encoding="utf-8")
        print(f"wrote {args.out} ({len(post['text'])} chars)")
    else:
        print(header + post["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
