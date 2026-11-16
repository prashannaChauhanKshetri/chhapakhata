"""Build the printable user guide (PDF) from docs/user-guide/en.md.

    make user-guide
    # or: cd backend && uv run --with markdown python ../scripts/build-user-guide.py

Writes docs/user-guide/ChhapaKhata-User-Guide.pdf: a cover page, a table of
contents with page numbers, one chapter per section, A4, in the app's fonts
and colours.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

import markdown
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "user-guide" / "en.md"
TARGET = ROOT / "docs" / "user-guide" / "ChhapaKhata-User-Guide.pdf"
FONTS = (ROOT / "backend" / "fonts").as_uri()
LOGO = (ROOT / "frontend" / "public" / "brand" / "logo-mark.svg").as_uri()

CSS = """
@font-face { font-family: Inter; font-weight: 400; src: url("FONTS/inter-latin-400-normal.woff"); }
@font-face { font-family: Inter; font-weight: 500; src: url("FONTS/inter-latin-500-normal.woff"); }
@font-face { font-family: Inter; font-weight: 600; src: url("FONTS/inter-latin-600-normal.woff"); }
@font-face { font-family: Inter; font-weight: 700; src: url("FONTS/inter-latin-700-normal.woff"); }
@font-face { font-family: Noto; font-weight: 400;
  src: url("FONTS/noto-sans-devanagari-devanagari-400-normal.woff"); }

@page {
  size: A4;
  margin: 20mm 18mm 20mm 18mm;
  @bottom-left { content: "ChhapaKhata user guide"; font: 8pt Inter; color: #94A3B8; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 8pt Inter;
    color: #94A3B8; }
}
@page cover { margin: 0; @bottom-left { content: none; } @bottom-right { content: none; } }

html { font-family: Inter, Noto, sans-serif; color: #0F172A; font-size: 10.5pt; line-height: 1.55; }
body { margin: 0; }

/* Cover */
.cover { page: cover; height: 297mm; display: flex; flex-direction: column;
  justify-content: center; padding: 0 24mm; background: #0F172A; color: #F8FAFC;
  page-break-after: always; }
.cover img { width: 30mm; height: 30mm; margin-bottom: 10mm; }
.cover .brand { font-size: 34pt; font-weight: 700; letter-spacing: -0.5pt; }
.cover .brand span { color: #FDBA74; }
.cover .title { font-size: 20pt; font-weight: 500; margin-top: 4mm; color: #E2E8F0; }
.cover .for { margin-top: 14mm; font-size: 11pt; color: #CBD5E1; }
.cover .rule { width: 40mm; height: 2pt; background: #EA580C; margin: 8mm 0; }
.cover .meta { font-size: 9.5pt; color: #94A3B8; }

/* Contents */
.contents { page-break-after: always; }
.contents h2 { border: 0; margin-top: 0; }
.contents ol { list-style: none; padding: 0; margin: 0; }
.contents li { display: flex; padding: 2.4mm 0; border-bottom: 0.5pt solid #E2E8F0; }
.contents li a { color: #0F172A; text-decoration: none; flex: 1; }
.contents li a::after { content: target-counter(attr(href), page); float: right;
  color: #64748B; font-variant-numeric: tabular-nums; }

/* Chapters */
h1 { display: none; }
h2 { font-size: 17pt; font-weight: 700; color: #0F172A; margin: 0 0 4mm;
  padding-bottom: 2.5mm; border-bottom: 2pt solid #EA580C; page-break-before: always;
  bookmark-level: 1; }
.intro h2 { page-break-before: avoid; }
h3 { font-size: 12.5pt; font-weight: 600; color: #9A3412; margin: 7mm 0 2mm;
  page-break-after: avoid; bookmark-level: 2; }
p { margin: 0 0 3mm; orphans: 3; widows: 3; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1mm; }
strong { font-weight: 600; }
code { font-family: Inter, sans-serif; background: #F1F5F9; border-radius: 2pt;
  padding: 0 1.5pt; font-size: 9.5pt; }
hr { display: none; }
a { color: #C2410C; text-decoration: none; }

table { width: 100%; border-collapse: collapse; margin: 2mm 0 5mm; font-size: 9.5pt; }
th { text-align: left; background: #F8FAFC; color: #334155; font-weight: 600;
  border-top: 0.75pt solid #CBD5E1; border-bottom: 0.75pt solid #CBD5E1; padding: 2mm 2.5mm; }
td { border-bottom: 0.5pt solid #E2E8F0; padding: 2mm 2.5mm; vertical-align: top; }
tr { page-break-inside: avoid; }
"""


def build() -> Path:
    text = SOURCE.read_text(encoding="utf-8")
    text = re.sub(r"^# .*\n", "", text, count=1)  # the cover carries the title
    # Nested lists are indented 2 or 3 spaces (GitHub style); Python-Markdown needs 4.
    text = re.sub(r"^ {2,3}(?=\S)", "    ", text, flags=re.MULTILINE)
    intro, _, rest = text.partition("\n## ")
    md = markdown.Markdown(extensions=["tables", "toc", "sane_lists"])
    body = md.convert("## " + rest) if rest else md.convert(text)
    intro_html = markdown.markdown(intro, extensions=["tables", "sane_lists"])

    chapters = [t for t in md.toc_tokens if t["level"] == 2]  # type: ignore[attr-defined]
    contents = "".join(
        f'<li><a href="#{t["id"]}">{html.escape(t["name"])}</a></li>' for t in chapters
    )
    today = dt.date.today()
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>ChhapaKhata user guide</title><style>{CSS.replace("FONTS", FONTS)}</style></head><body>
<section class="cover">
  <img src="{LOGO}" alt="">
  <div class="brand">Chhapa<span>Khata</span></div>
  <div class="title">User guide</div>
  <div class="rule"></div>
  <div class="for">For the owner, front desk and production staff</div>
  <div class="meta">Orders · Production · Bills and payments · Customer accounts · Stock ·
    Reports · Imports · Backups</div>
  <div class="meta" style="margin-top: 4mm">Edition {today:%B %Y}</div>
</section>
<section class="contents intro">
  <h2>Contents</h2>
  <ol>{contents}</ol>
</section>
<section class="intro"><h2>About this guide</h2>{intro_html}</section>
{body}
</body></html>"""
    HTML(string=page, base_url=str(ROOT)).write_pdf(TARGET)
    return TARGET


if __name__ == "__main__":
    out = build()
    print(f"Wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
