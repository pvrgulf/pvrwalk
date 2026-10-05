from pathlib import Path
import html
import re
import shutil
import sys

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


def desktop_state_css(page_count):
    leaf_count = (page_count + 1) // 2
    lines = [
        "/* Generated desktop physical-leaf rules */",
        ".desktop-shell .book-leaf {",
        "    position: absolute;",
        "    left: 50%;",
        "    top: 0;",
        "    width: 50%;",
        "    height: 100%;",
        "    transform-origin: left center;",
        "    transform-style: preserve-3d;",
        "    transition: transform 950ms cubic-bezier(.18,.72,.18,1), opacity 120ms linear;",
        "    will-change: transform;",
        "    border-radius: 0 7px 7px 0;",
        "    box-shadow: 10px 12px 26px rgba(0,0,0,.38);",
        "}",
        ".desktop-shell .book-leaf .leaf-face {",
        "    position: absolute;",
        "    inset: 0;",
        "    overflow: hidden;",
        "    backface-visibility: hidden;",
        "    -webkit-backface-visibility: hidden;",
        "    border: 1px solid rgba(80,64,35,.55);",
        "    background: #f7f1e5;",
        "}",
        ".desktop-shell .book-leaf .leaf-back {",
        "    transform: rotateY(180deg);",
        "    border-radius: 7px 0 0 7px;",
        "}",
        ".desktop-shell .book-leaf img {",
        "    display: block;",
        "    width: 100%;",
        "    height: 100%;",
        "    object-fit: contain;",
        "    background: #e9dfc9;",
        "}",
        "",
    ]

    for state in range(1, leaf_count + 1):
        for leaf in range(1, leaf_count + 1):
            angle = "0deg" if leaf >= state else "-180deg"
            opacity = "1" if leaf <= state else "0"
            z_index = 1000 if leaf == state else leaf_count - leaf + 1
            lines.extend([
                f".desktop-shell > input:nth-of-type({state}):checked ~ .desktop-stage .book-leaf.leaf-{leaf} {{",
                f"    transform: rotateY({angle});",
                f"    opacity: {opacity};",
                f"    z-index: {z_index};",
                "}",
                "",
            ])
    return "\n".join(lines)


def mobile_state_css(page_count):
    lines = [
        "/* Generated mobile single-page rules */",
        ".mobile-shell .mobile-sheet { opacity: 0; transform: translateX(0); }",
        "",
    ]
    for page in range(1, page_count + 1):
        lines.extend([
            f".mobile-shell > input:nth-of-type({page}):checked ~ .mobile-stage .mobile-sheet.page-{page} {{",
            "    opacity: 1;",
            "    transform: translateX(0);",
            "}",
            "",
        ])
        if page > 1:
            lines.extend([
                f".mobile-shell > input:nth-of-type({page}):checked ~ .mobile-stage .mobile-sheet.page-{page - 1} {{",
                "    opacity: 0; transform: translateX(-4%);",
                "}",
                "",
            ])
    return "\n".join(lines)


def reader_html(title, page_count, pdf_name):
    leaf_count = (page_count + 1) // 2
    desktop_inputs = []
    desktop_leaves = []
    desktop_controls = []

    for state in range(1, leaf_count + 1):
        checked = " checked" if state == 1 else ""
        desktop_inputs.append(
            f'<input type="radio" name="desktop-page" id="desktop-page-{state}"{checked}>'
        )

    for leaf in range(1, leaf_count + 1):
        front = leaf * 2 - 1
        back = front + 1
        previous_state = max(1, leaf - 1)
        next_state = min(leaf_count, leaf + 1)

        front_html = f'''
                <div class="leaf-face leaf-front">
                    <img src="page-{front:03d}.webp" alt="{html.escape(title)} — page {front}">
                    <label class="leaf-hotspot-left" for="desktop-page-{previous_state}" aria-label="Previous spread"></label>
                    <label class="leaf-hotspot-right" for="desktop-page-{next_state}" aria-label="Next spread"></label>
                </div>
'''
        if back <= page_count:
            back_html = f'''
                <div class="leaf-face leaf-back">
                    <img src="page-{back:03d}.webp" alt="{html.escape(title)} — page {back}">
                    <label class="leaf-hotspot-left" for="desktop-page-{previous_state}" aria-label="Previous spread"></label>
                    <label class="leaf-hotspot-right" for="desktop-page-{next_state}" aria-label="Next spread"></label>
                </div>
'''
        else:
            back_html = '<div class="leaf-face leaf-back blank-back" aria-hidden="true"></div>'

        desktop_leaves.append(f'''
            <section class="book-leaf leaf-{leaf}" aria-label="Pages {front} and {min(back, page_count)}">
                {front_html}
                {back_html}
            </section>
''')

    for state in range(1, leaf_count + 1):
        previous_state = max(1, state - 1)
        next_state = min(leaf_count, state + 1)
        if state == 1:
            count_label = f"1 / {page_count}"
        else:
            left = state * 2 - 2
            right = min(left + 1, page_count)
            count_label = f"{left}–{right} / {page_count}"
        desktop_controls.append(f'''
            <div class="reader-controls state-controls desktop-state-{state}">
                <label class="reader-control" for="desktop-page-{previous_state}">← Previous</label>
                <span class="page-count">{count_label}</span>
                <label class="reader-control" for="desktop-page-{next_state}">Next →</label>
                <a class="pdf-control" href="../{html.escape(pdf_name)}" target="_blank" rel="noopener">Open / Print PDF</a>
            </div>
''')

    desktop_controls_css = [
        f".desktop-shell > input:nth-of-type({state}):checked ~ .desktop-state-{state} {{ display: flex; }}"
        for state in range(1, leaf_count + 1)
    ]

    mobile_inputs = []
    mobile_sheets = []
    mobile_controls = []
    for page in range(1, page_count + 1):
        checked = " checked" if page == 1 else ""
        mobile_inputs.append(
            f'<input type="radio" name="mobile-page" id="mobile-page-{page}"{checked}>'
        )
        mobile_sheets.append(f'''
            <section class="sheet mobile-sheet page-{page}" aria-label="Page {page}">
                <img src="page-{page:03d}.webp" alt="{html.escape(title)} — page {page}">
                <label class="hotspot left" for="mobile-page-{max(1, page - 1)}" aria-label="Previous page"></label>
                <label class="hotspot right" for="mobile-page-{min(page_count, page + 1)}" aria-label="Next page"></label>
            </section>
''')
        mobile_controls.append(f'''
            <div class="reader-controls state-controls mobile-state-{page}">
                <label class="reader-control" for="mobile-page-{max(1, page - 1)}">← Previous</label>
                <span class="page-count">{page} / {page_count}</span>
                <label class="reader-control" for="mobile-page-{min(page_count, page + 1)}">Next →</label>
                <a class="pdf-control" href="../{html.escape(pdf_name)}" target="_blank" rel="noopener">Open / Print PDF</a>
            </div>
''')

    mobile_controls_css = [
        f".mobile-shell > input:nth-of-type({page}):checked ~ .mobile-state-{page} {{ display: flex; }}"
        for page in range(1, page_count + 1)
    ]

    return f'''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} — PVR Walk</title>
    <link rel="stylesheet" href="../../style.css">
    <style>
{desktop_state_css(page_count)}
{mobile_state_css(page_count)}

.state-controls {{ display: none; }}
{chr(10).join(desktop_controls_css)}
{chr(10).join(mobile_controls_css)}
    </style>
</head>
<body>
    <header class="reader-header">
        <a class="back" href="../../index.html">← Booklets</a>
        <h1 class="reader-title">{html.escape(title)}</h1>
        <p class="reader-subtitle">Click the page edge or use the controls below.</p>
    </header>
    <main class="reader-main">
        <div class="reader-shell desktop-shell">
            {''.join(desktop_inputs)}
            <div class="book-stage desktop-stage">
                <div class="page-stack">
                    {''.join(desktop_leaves)}
                </div>
            </div>
            {''.join(desktop_controls)}
        </div>
        <div class="reader-shell mobile-shell">
            {''.join(mobile_inputs)}
            <div class="book-stage mobile-stage">
                <div class="page-stack">
                    {''.join(mobile_sheets)}
                </div>
            </div>
            {''.join(mobile_controls)}
        </div>
        <p class="reader-hint">The reader is entirely HTML and CSS. JavaScript is not required.</p>
    </main>
</body>
</html>
'''


def library_html(booklets):
    cards = []

    for title, slug, page_count in booklets:
        cards.append(f"""
        <a class="booklet-button" href="books/{slug}/index.html">
            <span class="booklet-title">{html.escape(title)}</span>
            <span class="booklet-meta">{page_count} pages</span>
            <span class="booklet-arrow">→</span>
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
        <p class="eyebrow">PVR Walk</p>
        <h1>Walk Booklets</h1>
        <p class="intro">Choose a walk to open its digital booklet.</p>
    </header>

    <main class="library-main">
        <div class="booklet-list">
            {''.join(cards)}
        </div>
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
