(function () {
  const $ = (id) => document.getElementById(id);
  const stage = $("stage"), statusEl = $("status"), book = $("book");
  const slotL = $("slotL"), slotR = $("slotR"), leaf = $("leaf"), leafFront = $("leafFront"), leafBack = $("leafBack");
  const prevBtn = $("prev"), nextBtn = $("next"), counter = $("counter");
  const select = $("fileSelect"), fileInput = $("fileInput"), folderInput = $("folderInput");

  let library = [];   // [{ key, name, label }]
  let pdf = null, total = 0, loadToken = 0;

  const setStatus = (t) => { statusEl.textContent = t || ""; };
  const prettyName = (n) => n.replace(/\.pdf$/i, "").replace(/_+/g, " ");
  const isPdf = (f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf";
  const lsGet = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } };

  /* ---------- Storage: PDFs are kept inside the browser (IndexedDB) ---------- */
  const DB = "pdf-viewer", STORE = "pdfs";
  const mem = new Map();  // fallback if the browser blocks IndexedDB (e.g. private mode)
  let dbBroken = false;
  const openDb = () => new Promise((ok, fail) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE);
    r.onsuccess = () => ok(r.result);
    r.onerror = () => fail(r.error);
  });
  async function idb(mode, fn, fallback) {
    if (!dbBroken) {
      try {
        const db = await openDb();
        return await new Promise((ok, fail) => {
          const req = fn(db.transaction(STORE, mode).objectStore(STORE));
          req.onsuccess = () => ok(req.result);
          req.onerror = () => fail(req.error);
        });
      } catch (e) { dbBroken = true; }
    }
    return fallback();
  }
  const idbKeys = () => idb("readonly", (s) => s.getAllKeys(), () => [...mem.keys()]);
  const idbGet = (k) => idb("readonly", (s) => s.get(k), () => mem.get(k));
  const idbPut = (k, v) => idb("readwrite", (s) => s.put(v, k), () => mem.set(k, v));
  const idbDel = (k) => idb("readwrite", (s) => s.delete(k), () => mem.delete(k));

  // First run: add the sample PDF(s) from js/samples.js
  async function seedSamples() {
    if (!window.SAMPLE_PDFS || lsGet("pdf-viewer-seeded")) return;
    for (const s of window.SAMPLE_PDFS) {
      if (await idbGet(s.name)) continue;
      const bin = atob(s.data), bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      await idbPut(s.name, new Blob([bytes], { type: "application/pdf" }));
    }
    lsSet("pdf-viewer-seeded", "1");
  }

  /* ---------- The document menu ---------- */
  async function loadLibrary(selectName) {
    const names = (await idbKeys()).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
    library = names.map((n) => ({ name: n, label: prettyName(n) }));
    select.innerHTML = "";
    $("removeBtn").disabled = !library.length;
    if (!library.length) {
      select.innerHTML = "<option>No PDFs yet</option>";
      select.disabled = true;
      return;
    }
    select.disabled = false;
    library.forEach((e) => {
      const o = document.createElement("option");
      o.value = e.name; o.textContent = e.label;
      select.appendChild(o);
    });
    const want = selectName || lsGet("pdf-viewer-last");
    select.value = library.some((e) => e.name === want) ? want : library[0].name;
  }

  /* ---------- Adding and removing files ---------- */
  async function addFiles(files) {
    const pdfs = [...files].filter(isPdf);
    if (!pdfs.length) { setStatus("No PDF files found in that selection."); return; }
    setStatus("Adding " + pdfs.length + " file" + (pdfs.length > 1 ? "s" : "") + "…");
    try {
      for (const f of pdfs) await idbPut(f.name, f);
      await loadLibrary(pdfs[pdfs.length - 1].name);
      openSelected();
    } catch (err) {
      setStatus("Could not add the file: " + err.message);
    }
  }

  async function removeCurrent() {
    const entry = library.find((e) => e.name === select.value);
    if (!entry || !confirm("Remove “" + entry.label + "” from the viewer?\n(The original file on your computer is not touched.)")) return;
    await idbDel(entry.name);
    await loadLibrary();
    openSelected();
  }

  /* ---------- Opening a PDF ---------- */
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const FLIP_MS = reduceMotion ? 0 : 800;
  book.style.setProperty("--flip", FLIP_MS + "ms");

  let ar = 0.707, mode = "single", pageW = 0, pageH = 0, pos = 0, busy = false, layoutTok = 0;
  let cacheKey = "";
  const cache = new Map(), pending = new Map();
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function openSelected() {
    const entry = library.find((e) => e.name === select.value);
    if (!entry) { clearViewer(); setStatus("No PDFs yet. Click “Add PDFs” or “Add folder” to get started."); return; }
    lsSet("pdf-viewer-last", entry.name);
    const token = ++loadToken;
    clearViewer();
    setStatus("Loading…");
    try {
      const blob = await idbGet(entry.name);
      const doc = await pdfjsLib.getDocument({ data: new Uint8Array(await blob.arrayBuffer()) }).promise;
      if (token !== loadToken) return;
      const vp = (await doc.getPage(1)).getViewport({ scale: 1 });
      ar = vp.width / vp.height;
      pdf = doc; total = doc.numPages; pos = 0;
      setStatus("");
      await layout();
    } catch (err) {
      if (token === loadToken) setStatus("Could not open “" + entry.label + "”. " + err.message);
    }
  }

  function clearViewer() {
    pdf = null; total = 0; pos = 0; busy = false; layoutTok++;
    cache.clear(); pending.clear(); cacheKey = "";
    mount(slotL, null); mount(slotR, null);
    leaf.style.display = "none";
    book.style.width = "0";
    counter.textContent = "";
    prevBtn.disabled = nextBtn.disabled = true;
  }

  /* ---------- Book model: cover alone, then two pages per spread ---------- */
  // Double mode positions: 0 (cover), 1 (pages 2-3), 3 (pages 4-5) ...
  // Single mode positions: every page.
  const spread = (p) => mode === "double"
    ? (p === 0 ? { L: null, R: 0 } : { L: p, R: p + 1 < total ? p + 1 : null })
    : { L: null, R: p };
  const snap = (p) => (mode === "double" && p > 0 && p % 2 === 0 ? p - 1 : p);
  const nextPos = () => { const n = mode === "double" ? (pos === 0 ? 1 : pos + 2) : pos + 1; return n < total ? n : null; };
  const prevPos = () => (pos === 0 ? null : mode === "double" ? (pos === 1 ? 0 : pos - 2) : pos - 1);

  /* ---------- Layout: choose 1 or 2 pages depending on space ---------- */
  async function layout() {
    if (!pdf) return;
    const tok = ++layoutTok;
    const W = stage.clientWidth, H = stage.clientHeight;
    const single = Math.min(W, H * ar), dbl = Math.min(W / 2, H * ar);
    mode = W >= 700 && total > 1 && dbl >= 0.75 * single ? "double" : "single";
    pageW = Math.floor(mode === "double" ? dbl : single);
    pageH = Math.floor(pageW / ar);
    pos = snap(pos);

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const key = pageW + "x" + pageH + "@" + dpr;
    if (key !== cacheKey) { cache.clear(); pending.clear(); cacheKey = key; }

    book.classList.toggle("double", mode === "double");
    book.style.width = (mode === "double" ? pageW * 2 : pageW) + "px";
    book.style.height = pageH + "px";
    book.style.perspective = pageW * 4 + "px";
    [slotL, slotR, leaf].forEach((el) => { el.style.width = pageW + "px"; el.style.height = pageH + "px"; });
    slotL.style.left = "0px";
    slotR.style.left = leaf.style.left = (mode === "double" ? pageW : 0) + "px";
    leaf.style.display = "none";

    const s = spread(pos);
    await ensure([s.L, s.R]);
    if (tok !== layoutTok) return;
    mount(slotL, s.L); mount(slotR, s.R);
    shift(s, false);
    updateUi();
    prefetch();
  }

  // Centre a lone cover / lone last page in the middle of the screen
  function shift(s, animate) {
    const x = mode !== "double" ? 0 : s.L == null ? -pageW / 2 : s.R == null ? pageW / 2 : 0;
    if (!animate) book.style.transition = "none";
    book.style.transform = "translateX(" + x + "px)";
    if (!animate) { book.offsetWidth; book.style.transition = ""; }
  }

  /* ---------- Rendering pages to cached canvases ---------- */
  function getBitmap(idx) {
    if (cache.has(idx)) return Promise.resolve(cache.get(idx));
    if (pending.has(idx)) return pending.get(idx);
    const doc = pdf, key = cacheKey, w = pageW, h = pageH;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const job = (async () => {
      const page = await doc.getPage(idx + 1);
      const base = page.getViewport({ scale: 1 });
      const vp = page.getViewport({ scale: Math.min(w / base.width, h / base.height) * dpr });
      const c = document.createElement("canvas");
      c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
      const ctx = c.getContext("2d");
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
      await page.render({
        canvasContext: ctx, viewport: vp,
        transform: [1, 0, 0, 1, (c.width - vp.width) / 2, (c.height - vp.height) / 2]
      }).promise;
      pending.delete(idx);
      if (doc === pdf && key === cacheKey) cache.set(idx, c);
      return c;
    })();
    pending.set(idx, job);
    return job;
  }
  const ensure = (list) => Promise.all(list.filter((i) => i != null && i >= 0 && i < total).map(getBitmap));

  function mount(el, idx) {
    el.replaceChildren();
    el.classList.toggle("has-page", idx != null);
    const src = idx == null ? null : cache.get(idx);
    if (!src) return;
    const c = document.createElement("canvas");
    c.width = src.width; c.height = src.height;
    c.getContext("2d").drawImage(src, 0, 0);
    el.appendChild(c);
  }

  function prefetch() {
    for (const i of [...cache.keys()]) if (i < pos - 2 || i > pos + 3) cache.delete(i);
    for (let i = Math.max(0, pos - 2); i <= Math.min(total - 1, pos + 3); i++) getBitmap(i);
  }

  /* ---------- The page flip ---------- */
  async function flip(newPos, dir) {
    if (busy || !pdf) return;
    busy = true;
    const a = spread(pos), b = spread(newPos), dbl = mode === "double";
    await ensure([a.L, a.R, b.L, b.R]);
    if (!pdf) return;

    leaf.style.transition = "none";
    if (dir > 0) {                       // right page turns over to the left
      mount(leafFront, a.R); mount(leafBack, dbl ? b.L : null);
      mount(slotR, b.R);                 // revealed underneath
      leaf.style.transform = "rotateY(0deg)";
    } else {                             // left page turns back to the right
      mount(leafFront, b.R); mount(leafBack, dbl ? a.L : null);
      mount(slotL, b.L);
      leaf.style.transform = "rotateY(-180deg)";
    }
    leaf.style.display = "block";
    leaf.offsetWidth;                    // apply start position
    shift(b, true);
    leaf.style.transition = "transform " + FLIP_MS + "ms ease-in-out";
    leaf.style.transform = dir > 0 ? "rotateY(-180deg)" : "rotateY(0deg)";
    await wait(FLIP_MS + 50);

    pos = newPos;
    mount(slotL, b.L); mount(slotR, b.R);
    leaf.style.display = "none";
    busy = false;
    updateUi();
    prefetch();
  }

  function updateUi() {
    const s = spread(pos);
    const shown = [s.L, s.R].filter((x) => x != null).map((x) => x + 1);
    counter.textContent = (shown.length > 1 ? "Pages " + shown[0] + "–" + shown[1] : "Page " + shown[0]) + " of " + total;
    prevBtn.disabled = prevPos() === null;
    nextBtn.disabled = nextPos() === null;
  }

  /* ---------- Controls: arrows, keys, swipe, tap ---------- */
  function go(dir) {
    const p = dir > 0 ? nextPos() : prevPos();
    if (p !== null) flip(p, dir);
  }
  prevBtn.addEventListener("click", () => go(-1));
  nextBtn.addEventListener("click", () => go(1));

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "SELECT") return;
    if (e.key === "ArrowLeft") go(-1);
    else if (e.key === "ArrowRight") go(1);
  });

  let sx = 0, sy = 0, down = false;
  stage.addEventListener("pointerdown", (e) => { down = true; sx = e.clientX; sy = e.clientY; });
  stage.addEventListener("pointercancel", () => { down = false; });
  stage.addEventListener("pointerup", (e) => {
    if (!down) return;
    down = false;
    const dx = e.clientX - sx, dy = e.clientY - sy;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) go(dx < 0 ? 1 : -1);          // swipe
    else if (Math.abs(dx) < 10 && Math.abs(dy) < 10 && e.target.closest("#book")) {      // tap a page
      const r = book.getBoundingClientRect();
      go(e.clientX < r.left + r.width * (mode === "double" ? 0.5 : 0.3) ? -1 : 1);
    }
  });

  /* Re-layout when the window is resized or the device is rotated */
  let resizeTimer;
  const relayout = () => (busy ? setTimeout(relayout, 200) : layout());
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(relayout, 200); });

  /* ---------- Menus and drag-and-drop ---------- */
  select.addEventListener("change", () => { select.blur(); openSelected(); });
  $("addBtn").addEventListener("click", () => fileInput.click());
  $("folderBtn").addEventListener("click", () => folderInput.click());
  $("removeBtn").addEventListener("click", removeCurrent);
  fileInput.addEventListener("change", () => { addFiles(fileInput.files); fileInput.value = ""; });
  folderInput.addEventListener("change", () => { addFiles(folderInput.files); folderInput.value = ""; });
  ["dragenter", "dragover"].forEach((t) => document.addEventListener(t, (e) => { e.preventDefault(); document.body.classList.add("dropping"); }));
  ["dragleave", "drop"].forEach((t) => document.addEventListener(t, (e) => { e.preventDefault(); if (t === "drop" || e.target === document.documentElement) document.body.classList.remove("dropping"); }));
  document.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));

  /* ---------- Start ---------- */
  (async function init() {
    if (!window.pdfjsLib || !window.pdfjsWorker) {
      setStatus("The PDF engine (js/lib/pdf.js and js/lib/pdf.worker.js) did not load.");
      return;
    }
    // The worker is loaded as a normal script, so PDF.js runs it directly (works from file://)
    pdfjsLib.GlobalWorkerOptions.workerSrc = "js/lib/pdf.worker.js";
    try { await seedSamples(); } catch (e) { /* ignore */ }
    await loadLibrary();
    openSelected();
  })();
})();
