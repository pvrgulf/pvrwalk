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
    # Even-page books need one extra state to turn the final physical leaf
    # over and reveal its reverse face (e.g. page 8).
    state_count = leaf_count + 1 if page_count % 2 == 0 else leaf_count

    lines = [
        "/* Generated desktop physical-leaf rules */",
        ".desktop-shell .book-leaf {",
        "    position: absolute; left: 50%; top: 0;",
        "    width: 50%; height: 100%;",
        "    transform-origin: left center;",
        "    transform-style: preserve-3d;",
        "    transition: transform 950ms cubic-bezier(.18,.72,.18,1);",
        "    will-change: transform;",
        "    border-radius: 0 7px 7px 0;",
        "    box-shadow: 10px 12px 26px rgba(0,0,0,.38);",
        "    opacity: 0;",
        "}",
        ".desktop-shell .book-leaf .leaf-face {",
        "    position: absolute; inset: 0; overflow: hidden;",
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
        "    display: block; width: 100%; height: 100%;",
        "    object-fit: contain; background: #e9dfc9;",
        "}",
        "",
    ]

    # State 1: page 1 alone on the right.
    lines += [
        ".desktop-shell > input:nth-of-type(1):checked ~ .desktop-stage .book-leaf.leaf-1 {",
        "    transform: rotateY(0deg); opacity: 1; z-index: 1000;",
        "}",
        "",
    ]

    # Normal spread states: previous leaf turned left, current leaf on right.
    for state in range(2, leaf_count + 1):
        previous = state - 1
        lines += [
            f".desktop-shell > input:nth-of-type({state}):checked ~ .desktop-stage .book-leaf.leaf-{state} {{",
            "    transform: rotateY(0deg); opacity: 1; z-index: 1000;",
            "}",
            "",
            f".desktop-shell > input:nth-of-type({state}):checked ~ .desktop-stage .book-leaf.leaf-{previous} {{",
            "    transform: rotateY(-180deg); opacity: 1; z-index: 900;",
            "}",
            "",
        ]
        for leaf in range(1, previous):
            lines += [
                f".desktop-shell > input:nth-of-type({state}):checked ~ .desktop-stage .book-leaf.leaf-{leaf} {{",
                "    transform: rotateY(-180deg); opacity: 0; z-index: 1;",
                "}",
                "",
            ]

    # Final state for even-page books: turn the last leaf over so its
    # reverse face becomes the visible left-hand page.
    if page_count % 2 == 0:
        final_state = leaf_count + 1
        for leaf in range(1, leaf_count):
            lines += [
                f".desktop-shell > input:nth-of-type({final_state}):checked ~ .desktop-stage .book-leaf.leaf-{leaf} {{",
                "    transform: rotateY(-180deg); opacity: 0; z-index: 1;",
                "}",
                "",
            ]
        lines += [
            f".desktop-shell > input:nth-of-type({final_state}):checked ~ .desktop-stage .book-leaf.leaf-{leaf_count} {{",
            "    transform: rotateY(-180deg); opacity: 1; z-index: 1000;",
            "}",
            "",
        ]

    return "\n".join(lines)


def mobile_state_css(page_count):
    lines = [
        "/* Generated mobile single-page rules */",
        ".mobile-shell .mobile-sheet { opacity: 0; transform: translateX(0); pointer-events: none; }",
        "",
    ]
    for page in range(1, page_count + 1):
        lines.extend([
            f".mobile-shell > input:nth-of-type({page}):checked ~ .mobile-stage .mobile-sheet.page-{page} {{",
            "    opacity: 1;",
            "    transform: translateX(0);",
            "    pointer-events: auto;",
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

    desktop_state_count = leaf_count + 1 if page_count % 2 == 0 else leaf_count
    for state in range(1, desktop_state_count + 1):
        checked = " checked" if state == 1 else ""
        desktop_inputs.append(
            f'<input type="radio" name="desktop-page" id="desktop-page-{state}"{checked}>'
        )

    for leaf in range(1, leaf_count + 1):
        front = leaf * 2 - 1
        back = front + 1
        previous_state = max(1, leaf - 1)
        next_state = min(leaf_count, leaf + 1)

        # The front face is the right-hand page of a spread.
        # Only its OUTER RIGHT edge advances to the next spread.
        front_html = f"""
                <div class="leaf-face leaf-front">
                    <img src="page-{front:03d}.webp" alt="{html.escape(title)} — page {front}">
                </div>
"""

        if back <= page_count:
            # The back face is the left-hand page of a spread.
            # Only its OUTER LEFT edge goes back to the previous spread.
            back_html = f"""
                <div class="leaf-face leaf-back">
                    <img src="page-{back:03d}.webp" alt="{html.escape(title)} — page {back}">
                </div>
"""
        else:
            back_html = '<div class="leaf-face leaf-back blank-back" aria-hidden="true"></div>'

        desktop_leaves.append(f"""
            <section class="book-leaf leaf-{leaf}" aria-label="Pages {front} and {min(back, page_count)}">
                {front_html}
                {back_html}
            </section>
""")

    for state in range(1, desktop_state_count + 1):
        previous_state = max(1, state - 1)
        next_state = min(desktop_state_count, state + 1)
        if state == 1:
            count_label = "Page 1"
        elif state == desktop_state_count and page_count % 2 == 0:
            count_label = f"Page {page_count}"
        else:
            left = state * 2 - 2
            right = min(left + 1, page_count)
            count_label = f"Page {left}–{right}"
        desktop_controls.append(f'''
            <div class="reader-controls state-controls desktop-state-{state}">
                <label class="reader-control jump-control" for="desktop-page-1" aria-label="First page">&lt;&lt;</label>
                <label class="reader-control step-control" for="desktop-page-{previous_state}" aria-label="Previous page">&larr;</label>
                <span class="page-count" aria-label="Current page">{count_label}</span>
                <label class="reader-control step-control" for="desktop-page-{next_state}" aria-label="Next page">&rarr;</label>
                <label class="reader-control jump-control" for="desktop-page-{desktop_state_count}" aria-label="Last page">&gt;&gt;</label>
            </div>
''')

    desktop_controls_css = [
        f".desktop-shell > input:nth-of-type({state}):checked ~ .desktop-state-{state} {{ display: flex; }}"
        for state in range(1, desktop_state_count + 1)
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
                <label class="reader-control jump-control" for="mobile-page-1" aria-label="First page">&lt;&lt;</label>
                <label class="reader-control step-control" for="mobile-page-{max(1, page - 1)}" aria-label="Previous page">&larr;</label>
                <span class="page-count" aria-label="Current page">Page {page}</span>
                <label class="reader-control step-control" for="mobile-page-{min(page_count, page + 1)}" aria-label="Next page">&rarr;</label>
                <label class="reader-control jump-control" for="mobile-page-{page_count}" aria-label="Last page">&gt;&gt;</label>
            </div>
''')

    mobile_controls_css = [
        f".mobile-shell > input:nth-of-type({page}):checked ~ .mobile-state-{page} {{ display: flex !important; }}"
        for page in range(1, page_count + 1)
    ]

    return f'''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} — Cambo Walks</title>
    <link rel="stylesheet" href="../../style.css">
    <style>
{desktop_state_css(page_count)}
{mobile_state_css(page_count)}

.state-controls {{ display: none; }}
{chr(10).join(desktop_controls_css)}
{chr(10).join(mobile_controls_css)}

{chr(10).join(
    f".desktop-shell > input:nth-of-type({state}):checked ~ .desktop-stage .edge-state-{state} {{ display: block; }}"
    for state in range(1, desktop_state_count + 1)
)}
    </style>
</head>
<body class="booklet-reader">
    <header class="reader-header">
        <div class="reader-topbar">
            <a class="pdf-control reader-top-action reader-back" href="../../index.html">← Back to Booklets</a>
            <div class="reader-heading">
                <h1 class="reader-title">{html.escape(title)}</h1>
                <p class="reader-subtitle">Click the page edge or use the controls below.</p>
            </div>
            <a class="pdf-control reader-top-action reader-pdf" href="../../pdfs/{html.escape(pdf_name)}" target="_blank" rel="noopener">Open / Print PDF</a>
        </div>
    </header>
    <main class="reader-main">
        <div class="reader-shell desktop-shell">
            {''.join(desktop_inputs)}
            <div class="book-stage desktop-stage">
                <div class="page-stack">
                    {''.join(desktop_leaves)}
                </div>
                {''.join(
                    f'<label class="spread-edge spread-edge-left edge-state-{state}" for="desktop-page-{max(1, state - 1)}" aria-label="Previous spread"></label>'
                    for state in range(1, desktop_state_count + 1)
                )}
                {''.join(
                    f'<label class="spread-edge spread-edge-right edge-state-{state}" for="desktop-page-{min(desktop_state_count, state + 1)}" aria-label="Next spread"></label>'
                    for state in range(1, desktop_state_count + 1)
                )}
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
    <title>Cambo Walks — Booklets</title>
    <link rel="stylesheet" href="style.css">
</head>
<body class="library-page">
    <header class="site-header">
        <p class="eyebrow">Cambo Walks</p>
        <h1>Walk Booklets</h1>
        <p class="intro">Choose a walk to open its digital booklet.</p>
    </header>

    <main class="library-main">
        <div class="library-site-link-wrap"><a class="pdf-control" href="../home.html">← Back to Cambo Walks website</a></div>
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
        # Safety: do not remove existing output if the source folder is empty.
        print(f"No PDF files found in: {PDF_DIR}")
        print("Nothing was changed; existing booklet output has been left intact.")
        return

    # Keep the generated books folder in sync with the PDFs. Only inspect
    # immediate subdirectories: never touch pdfs, tools, or files in books/.
    expected_slugs = {slugify(pdf.stem) for pdf in pdfs}
    removed = []
    for existing in BOOK_DIR.iterdir():
        if existing.is_dir() and existing.name not in expected_slugs:
            shutil.rmtree(existing)
            removed.append(existing.name)

    if removed:
        print("Removed obsolete booklet folder(s):")
        for name in removed:
            print(f"  - {name}")
    else:
        print("No obsolete booklet folders found.")

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
