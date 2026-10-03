#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, re, shutil
from pathlib import Path
try:
    import fitz
    from PIL import Image
except ImportError:
    raise SystemExit("PyMuPDF and Pillow are required. Install with: python -m pip install pymupdf pillow")

HERE = Path(__file__).resolve()
BOOKLETS = HERE.parents[1]
PDF_DIR = BOOKLETS / "pdfs"
BOOKS_DIR = BOOKLETS / "books"
INDEX = BOOKLETS / "index.html"
DEFAULT_DPI = 150
WEBP_QUALITY = 85

def slugify(name):
    s = Path(name).stem.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "book"

def title_for(name):
    return re.sub(r"\s+", " ", Path(name).stem.replace("_", " ")).strip()

def state_css(sheet_count):
    rules = []
    for state in range(1, sheet_count):
        for sheet in range(1, state + 1):
            rules.append(
                f"#sheet-{state}:checked ~ .book .sheet.s{sheet} "
                "{ transform: rotateY(-180deg); }"
            )
        rules.append(
            f"#sheet-{state}:checked ~ .book .sheet:nth-of-type({state + 1}) "
            "{ z-index: 1000; }"
        )
    return "\n".join(rules)

def book_html(title, pdf_name, page_count):
    sheet_count = (page_count + 1) // 2
    radios = "\n".join(
        f'<input class="state" type="radio" name="book-state" id="sheet-{i}"'
        f'{" checked" if i == 0 else ""}>'
        for i in range(sheet_count)
    )
    sheets = []
    for n in range(sheet_count):
        odd = n * 2 + 1
        even = odd + 1
        front = f"page-{odd:04d}.webp"
        back = f"page-{even:04d}.webp" if even <= page_count else None
        back_img = (
            f'<img src="pages/{html.escape(back)}" alt="Page {even}">'
            if back else ""
        )
        sheets.append(f"""
        <div class="sheet s{n + 1}">
          <div class="face front">
            <img src="pages/{html.escape(front)}" alt="Page {odd}">
            <span class="spine-shadow" aria-hidden="true"></span>
            <span class="page-edge" aria-hidden="true"></span>
          </div>
          <div class="face back">
            {back_img}
            <span class="spine-shadow" aria-hidden="true"></span>
          </div>
        </div>""")
    controls = []
    for state in range(sheet_count):
        prev_state = max(0, state - 1)
        next_state = min(sheet_count - 1, state + 1)
        controls.append(
            f'<span class="state-controls state-{state}">'
            f'<label for="sheet-{prev_state}" aria-label="Previous page">‹</label>'
            f'<label for="sheet-{next_state}" aria-label="Next page">›</label>'
            f'</span>'
        )
    footer_rules = "\n".join(
        f"#sheet-{i}:checked ~ .reader-footer .state-{i} {{ display:flex; }}"
        for i in range(sheet_count)
    )
    pages_text = f"{page_count} page" if page_count == 1 else f"{page_count} pages"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — Booklet</title>
<link rel="stylesheet" href="../../style.css">
<style>
{state_css(sheet_count)}
{footer_rules}
</style>
</head>
<body class="reader">
<header class="reader-header">
  <a href="../../index.html">← Library</a>
  <div class="reader-title">{html.escape(title)}</div>
  <a href="../../pdfs/{html.escape(pdf_name)}" download>PDF</a>
</header>
<main class="book-stage">
  {radios}
  <div class="book" aria-label="{html.escape(title)}">
    <div class="blank-left" aria-hidden="true"></div>
    {''.join(sheets)}
  </div>
</main>
<footer class="reader-footer">
  {''.join(controls)}
  <span class="counter">{pages_text}</span>
</footer>
</body>
</html>
"""

def render_pdf(pdf_path, out_dir, dpi):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    doc = fitz.open(pdf_path)
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        png_bytes = pix.tobytes("png")
        with Image.open(__import__("io").BytesIO(png_bytes)) as image:
            image.save(out_dir / f"page-{i:04d}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
    count = len(doc)
    doc.close()
    return count

def build(dpi):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(PDF_DIR.glob("*.pdf"), key=lambda p: p.name.lower())
    if not pdfs:
        raise SystemExit(f"No PDFs found in {PDF_DIR}. Copy PDFs there first.")
    for child in BOOKS_DIR.iterdir():
        if child.is_dir(): shutil.rmtree(child)
        else: child.unlink()
    cards = []
    for pdf in pdfs:
        title = title_for(pdf.name)
        slug = slugify(pdf.name)
        book_dir = BOOKS_DIR / slug
        pages_dir = book_dir / "pages"
        print(f"Building: {pdf.name}")
        count = render_pdf(pdf, pages_dir, dpi)
        (book_dir / "index.html").write_text(book_html(title, pdf.name, count), encoding="utf-8")
        shutil.copy2(pages_dir / "page-0001.webp", book_dir / "cover.webp")
        cards.append(f"""
<a class="book-card" href="books/{html.escape(slug)}/index.html">
  <div class="cover"><img src="books/{html.escape(slug)}/cover.webp" alt="Cover of {html.escape(title)}"></div>
  <div class="card-body"><h2 class="card-title">{html.escape(title)}</h2>
  <p class="card-meta">{count} page{"s" if count != 1 else ""}</p></div>
</a>""")
    INDEX.write_text(f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Booklets</title><link rel="stylesheet" href="style.css"></head>
<body>
<header class="site-header"><h1>Booklets</h1><p>Walking guides from Cambo.</p></header>
<main class="library"><div class="library-grid">{''.join(cards)}</div></main>
</body></html>
""", encoding="utf-8")
    print(f"Built {len(pdfs)} booklet(s). Open {INDEX}.")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    args = p.parse_args()
    if not 72 <= args.dpi <= 300:
        raise SystemExit("--dpi should be between 72 and 300.")
    build(args.dpi)
