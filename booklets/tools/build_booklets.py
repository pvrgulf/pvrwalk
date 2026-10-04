from pathlib import Path
import html
import re
import shutil
import sys
from urllib.parse import quote

try:
    import pymupdf
    from PIL import Image
except ImportError:
    print("Missing packages. Run: python -m pip install pymupdf pillow")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "pdfs"
BOOK_DIR = ROOT / "books"
INDEX = ROOT / "index.html"
CSS_FILE = ROOT / "style.css"


def slugify(name):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "book"


def render_pdf(pdf_path, output_dir):
    document = pymupdf.open(pdf_path)
    try:
        for number, page in enumerate(document, start=1):
            target = output_dir / f"page-{number:03d}.webp"

            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(1.5, 1.5),
                alpha=False,
            )

            temporary = output_dir / f".page-{number:03d}.png"
            pixmap.save(temporary)

            with Image.open(temporary) as image:
                image.save(target, "WEBP", quality=88, method=6)

            temporary.unlink()
    finally:
        document.close()


def page_turn_css(page_count):
    lines = [
        "/* Generated page-turn rules */",
        ".reader-shell > input:first-of-type:checked ~ .book-stage .page-stack .sheet {",
        "    transform: rotateY(0deg);",
        "}",
        "",
    ]

    for page in range(2, page_count + 1):
        lines.extend([
            f".reader-shell > input:nth-of-type({page}):checked ~ .book-stage .page-stack "
            f".sheet:nth-child(-n+{page - 1}) {{",
            "    transform: rotateY(-180deg);",
            "}",
            "",
        ])

    return "\n".join(lines)


def reader_html(title, page_count, pdf_name):
    inputs = []
    sheets = []
    left_pages = []
    left_page_css = []

    for page in range(1, page_count + 1):
        checked = " checked" if page == 1 else ""
        inputs.append(
            f'<input type="radio" name="page" id="page-{page}"{checked}>'
        )

        previous_page = max(1, page - 1)
        next_page = min(page_count, page + 1)
        z_index = page_count - page + 1

        if page > 1:
            left_pages.append(f"""
                <div class="left-page left-page-{page}" aria-label="Page {page - 1}" style="z-index: {page};">
                    <img src="page-{page - 1:03d}.webp"
                         alt="{html.escape(title)} — page {page - 1}">
                </div>
""")
            left_page_css.append(
                f".reader-shell > input:nth-of-type({page}):checked "
                f"~ .book-stage .left-page-{page} {{ "
                "opacity: 1; visibility: visible; "
                "transition-delay: 330ms, 0s; }"
            )

        sheets.append(f"""
            <section class="sheet" aria-label="Page {page}" style="z-index: {z_index};">
                <img src="page-{page:03d}.webp"
                     alt="{html.escape(title)} — page {page}">
                <label class="hotspot left"
                       for="page-{previous_page}"
                       aria-label="Previous page"></label>
                <label class="hotspot right"
                       for="page-{next_page}"
                       aria-label="Next page"></label>
            </section>
""")

    # Each radio state gets its own control row. CSS reveals only the row
    # belonging to the selected page.
    controls = []
    for page in range(1, page_count + 1):
        previous_page = max(1, page - 1)
        next_page = min(page_count, page + 1)
        controls.append(f"""
            <div class="reader-controls state-controls state-{page}">
                <label class="reader-control" for="page-{previous_page}">
                    ← Previous
                </label>
                <span class="page-count">{page} / {page_count}</span>
                <label class="reader-control" for="page-{next_page}">
                    Next →
                </label>
                <a class="pdf-control"
                   href="{html.escape(quote(pdf_name))}"
                   target="_blank"
                   rel="noopener">
                    Open / Print PDF
                </a>
            </div>
""")

    state_css = []
    for page in range(1, page_count + 1):
        state_css.append(
            f".reader-shell > input:nth-of-type({page}):checked "
            f"~ .state-controls.state-{page} {{ display: flex; }}"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} — PVR Walk</title>
    <link rel="stylesheet" href="../../style.css">
    <style>
{page_turn_css(page_count)}

.state-controls {{
    display: none;
}}

{chr(10).join(state_css)}

{chr(10).join(left_page_css)}
    </style>
</head>
<body>
    <header class="reader-header">
        <a class="back" href="../../index.html">← Booklets</a>
        <h1 class="reader-title">{html.escape(title)}</h1>
        <p class="reader-subtitle">
            Click the page edge or use the controls below.
        </p>
    </header>

    <main class="reader-main">
        <div class="reader-shell">
            {''.join(inputs)}

            <div class="book-stage">
                {''.join(left_pages)}
                <div class="page-stack">
                    {''.join(sheets)}
                </div>
            </div>

            {''.join(controls)}
        </div>

        <p class="reader-hint">
            The reader is entirely HTML and CSS. JavaScript is not required.
        </p>
    </main>
</body>
</html>
"""


def library_html(books):
    buttons = []

    for title, slug, page_count in books:
        buttons.append(f"""
            <a class="booklet-button" href="books/{slug}/index.html">
                <span class="booklet-title">{html.escape(title)}</span>
                <span class="booklet-meta">{page_count} pages</span>
                <span class="booklet-arrow" aria-hidden="true">→</span>
            </a>
""")

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PVR Walk — Booklets</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="site-header">
        <h1>PVR Walk</h1>
        <p>Booklets</p>
    </header>

    <main class="booklet-list">
        {''.join(buttons)}
    </main>
</body>
</html>
"""


def main():
    PDF_DIR.mkdir(exist_ok=True)
    BOOK_DIR.mkdir(exist_ok=True)

    pdfs = sorted(PDF_DIR.glob("*.pdf"))

    if not pdfs:
        print(f"No PDF files found in: {PDF_DIR}")
        return

    books = []

    for pdf in pdfs:
        title = pdf.stem.replace("_", " ").replace("-", " ").strip().title()
        slug = slugify(pdf.stem)
        output = BOOK_DIR / slug

        print(f"Building: {pdf.name}")

        if output.exists():
            shutil.rmtree(output)

        output.mkdir(parents=True)

        render_pdf(pdf, output)

        # Keep a copy of the original PDF alongside the generated pages.
        copied_pdf = output / pdf.name
        shutil.copy2(pdf, copied_pdf)

        page_count = len(list(output.glob("page-*.webp")))

        (output / "index.html").write_text(
            reader_html(title, page_count, pdf.name),
            encoding="utf-8",
        )

        books.append((title, slug, page_count))

    INDEX.write_text(library_html(books), encoding="utf-8")

    print()
    print(f"Built {len(books)} booklet(s).")
    print(f"Open: {INDEX}")
    print("Original PDFs copied into their book folders.")
    print("Runtime viewer uses no JavaScript.")


if __name__ == "__main__":
    main()
