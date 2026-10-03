# Booklets — CSS-only PDF flipbooks

This directory is a replacement for `booktest`. The published viewer uses **HTML + CSS only**:
there is no JavaScript and no PDF.js.

## Build

1. Copy PDFs into `booklets/pdfs/`.
2. From the repository root run:

```powershell
python -m pip install pymupdf
python booklets/tools/build_booklets.py
```

The builder renders each PDF page to WebP and generates a CSS-only flipbook plus the library page.

The generated viewer can be opened directly as a local file; it does not use `fetch()`, JavaScript, PDF.js, or the GitHub API.

The original `booktest/` directory is untouched.
