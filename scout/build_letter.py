"""Turn a cover letter written in plain Markdown into a one-page PDF.

    .venv/bin/python scout/build_letter.py applications/<folder>/cover-letter.md

The Markdown file has a small header block, then the body as ordinary paragraphs:

    name: Jeremiah Sleman
    contact: (555) 123-4567 | you@example.com | linkedin.com/in/you
    date: October 15, 2026
    to: Hiring Team, Acme
    closing: Sincerely
    ---
    First paragraph...

    Second paragraph...

The PDF lands next to the .md with the same stem. Refuses more than one page, and refuses em or en dashes.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "scout" / "templates"
DASHES = re.compile("[\\u2013\\u2014]")


def parse_letter(text: str) -> dict:
    if "\n---" not in text:
        sys.exit("cover letter needs a header block ending in a line with ---")
    header, body = text.split("\n---", 1)
    fields = {}
    for line in header.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip().lower()] = v.strip()
    for key in ("name", "contact", "date"):
        if key not in fields:
            sys.exit(f"cover letter header is missing {key}:")
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    return {
        "name": fields["name"],
        "contact": [c.strip() for c in fields["contact"].split("|")],
        "date": fields["date"],
        "to": fields.get("to", ""),
        "closing": fields.get("closing", "Sincerely"),
        "paragraphs": paragraphs,
    }


def build(md_path: Path) -> Path:
    text = md_path.read_text(encoding="utf-8")
    if DASHES.search(text):
        sys.exit(f"{md_path}: contains an em or en dash. Replace it with a comma, colon, or hyphen.")
    data = parse_letter(text)
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    html = env.get_template("letter.html").render(**data)
    pdf_path = md_path.with_suffix(".pdf")
    document = HTML(string=html, base_url=str(TEMPLATE_DIR)).render()
    document.write_pdf(pdf_path)
    pages = len(document.pages)
    words = sum(len(p.split()) for p in data["paragraphs"])
    print(f"{pdf_path}  [{'OK' if pages == 1 else f'FAIL: {pages} pages'}]  {words} words")
    if pages != 1:
        sys.exit(1)
    return pdf_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("letters", nargs="+", type=Path)
    args = ap.parse_args()
    for p in args.letters:
        build(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
