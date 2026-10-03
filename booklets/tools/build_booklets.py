from pathlib import Path
import html
import re
import shutil
import sys

try:
    import fitz
    from PIL import Image
except ImportError:
    print("Missing packages. Run: python -m pip install pymupdf pillow")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "pdfs"
BOOK_DIR = ROOT / "books"
INDEX = ROOT / "index.html"

def slugify(name):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return s or "book"

def render_pdf(pdf_path, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc, 1):
        target = out_dir / f"page-{i:03d}.webp"
        if target.exists():
            continue
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        png_tmp = out_dir / f".page-{i:03d}.png"
        pix.save(png_tmp)
        with Image.open(png_tmp) as im:
            im.save(target, "WEBP", quality=88, method=6)
        png_tmp.unlink()
    doc.close()

def make_book_html(title, slug, page_count):
    labels = []
    for i in range(page_count):
        labels.append(f'<input type="radio" name="page" id="p{i}" {"checked" if i == 0 else ""}>')
    pages = []
    for i in range(page_count):
        nxt = min(i + 1, page_count - 1)
        prev = max(i - 1, 0)
        pages.append(f"""
<section class="sheet sheet-{i+1}">
  <img src="page-{i+1:03d}.webp" alt="{html.escape(title)} — page {i+1}">
  <label class="hotspot left" for="p{prev}" aria-label="Previous page"></label>
  <label class="hotspot right" for="p{nxt}" aria-label="Next page"></label>
</section>""")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — PVR Walk</title>
<link rel="stylesheet" href="../../style.css">
</head>
<body class="reader">
<a class="back" href="../../index.html">← Booklets</a>
<main>
  <h1>{html.escape(title)}</h1>
  <div class="book" style="--pages:{page_count}">
    {''.join(labels)}
    <div class="stack">{''.join(pages)}</div>
  </div>
  <p class="hint">Click the right or left side of a page to turn it.</p>
</main>
</body>
</html>"""

def main():
    PDFs = sorted(PDF_DIR.glob("*.pdf"))
    if not PDFs:
        print(f"No PDF files found in {PDF_DIR}")
        return

    BOOK_DIR.mkdir(exist_ok=True)
    cards = []

    for pdf in PDFs:
        title = pdf.stem.replace("_", " ").replace("-", " ").strip().title()
        slug = slugify(pdf.stem)
        out = BOOK_DIR / slug
        print(f"Building: {pdf.name}")
        render_pdf(pdf, out)
        count = len(list(out.glob("page-*.webp")))
        (out / "index.html").write_text(make_book_html(title, slug, count), encoding="utf-8")
        cards.append((title, slug, count))

    cards_html = "\n".join(
        f'<a class="card" href="books/{slug}/index.html"><div class="cover"><img src="books/{slug}/page-001.webp" alt=""></div><h2>{html.escape(title)}</h2><span>{count} pages</span></a>'
        for title, slug, count in cards
    )

    INDEX.write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PVR Walk — Booklets</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header><h1>PVR Walk</h1><p>Booklets</p></header>
<main class="library">{cards_html}</main>
</body>
</html>""", encoding="utf-8")

    print(f"\nBuilt {len(cards)} booklet(s). Open: {INDEX}")

if __name__ == "__main__":
    main()
