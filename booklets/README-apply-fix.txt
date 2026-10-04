This archive contains the complete corrected PVR Walk booklet project.

The authoritative source files are:
- tools/build_booklets.py
- style.css
- build-booklets.bat

To apply the fix to an existing booklet folder, copy those three files from this archive over the matching files in your existing folder, then run build-booklets.bat. Your source PDFs remain in pdfs; the builder regenerates books and index.html from them.

The generated reader contains no JavaScript. PDF links point to the copied PDF beside each generated reader.
