PDF book viewer - runs entirely in the browser
==============================================
No server, no internet, no install. Double-click index.html (or open it with
VS Code Live Server - it works either way).

FOLDER
  index.html          the page
  css/style.css       styling
  js/viewer.js        menus, page flip, arrows, swipe, storage
  js/samples.js       sample PDF added on first run (delete it if not wanted)
  js/lib/pdf.js       PDF.js engine (Apache-2.0), bundled so nothing is downloaded
  js/lib/pdf.worker.js  PDF.js worker, bundled
  pdfs/               a handy place to keep your own PDF files (see below)

USING IT
  Document menu   choose which PDF to read
  Add PDFs        pick one or more PDF files
  Add folder      pick a folder (e.g. the pdfs/ folder) - every PDF inside is added
  Remove          removes the selected PDF from the viewer (your original is not touched)
  You can also drag PDFs onto the page.

  Page 1 is shown as a cover, then two pages at a time when the screen is wide enough.
  Turn pages with the arrows, arrow keys, a swipe, or a tap on a page.

WHERE THE FILES LIVE
  A web page cannot read your folders on its own, so PDFs you add are copied into the
  browser's own storage (IndexedDB) and are still there next time you open the page.
  To add new files later, keep them in pdfs/ and use "Add folder". Clearing the browser's
  site data removes them from the viewer.

SETTINGS (js/viewer.js)
  FLIP_MS      flip speed in milliseconds
  W >= 700 and 0.75 in layout()   when two pages are shown instead of one
