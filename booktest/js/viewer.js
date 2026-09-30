(function () {
	const $ = (id) => document.getElementById(id);

	const stage = $("stage");
	const statusEl = $("status");
	const book = $("book");

	const slotL = $("slotL");
	const slotR = $("slotR");
	const leaf = $("leaf");
	const leafFront = $("leafFront");
	const leafBack = $("leafBack");

	const prevBtn = $("prev");
	const nextBtn = $("next");
	const counter = $("counter");
	const select = $("fileSelect");

	/*
	 * GitHub repository containing the PDFs.
	 *
	 * The contents of this directory are read automatically from
	 * GitHub's public repository API.
	 */
	const PDF_DIRECTORY_API = "https://api.github.com/repos/pvrgulf/pvrwalk/contents/booktest/pdfs";

	/*
	 * The GitHub API returns the direct download URL for each file.
	 * Only PDF files are included in the document selector.
	 */
	let library = [];

	let pdf = null;
	let total = 0;
	let loadToken = 0;

	const setStatus = (text) => {
		statusEl.textContent = text || "";
	};

	/*
	 * Convert a filename into a more readable title.
	 *
	 * Examples:
	 *   walk.pdf
	 *     -> Walk
	 *
	 *   Woodland Circular Walk - 02.pdf
	 *     -> Woodland Circular Walk - 02
	 */
	const prettyName = (name) =>
		name
			.replace(/\.pdf$/i, "")
			.replace(/_/g, " ")
			.replace(/\s+/g, " ")
			.trim();

	const isPdfName = (name) => /\.pdf$/i.test(name);

	/*
	 * ------------------------------------------------------------------
	 * PDF LIBRARY
	 * ------------------------------------------------------------------
	 *
	 * Get the contents of:
	 *
	 *   booktest/pdfs/
	 *
	 * directly from the GitHub repository.
	 */
	async function loadLibrary(selectName) {
		setStatus("Finding PDFs…");
		select.disabled = true;

		try {
			const response = await fetch(PDF_DIRECTORY_API, {
				headers: {
					Accept: "application/vnd.github+json",
				},
				cache: "no-store",
			});

			if (!response.ok) {
				throw new Error("GitHub returned HTTP " + response.status + ".");
			}

			const files = await response.json();

			if (!Array.isArray(files)) {
				throw new Error("The GitHub directory response was not a list.");
			}

			/*
			 * Only files directly in the pdfs directory are used.
			 * Subdirectories are ignored.
			 */
			library = files
				.filter((file) => file.type === "file" && isPdfName(file.name) && file.download_url)
				.map((file) => ({
					name: file.name,
					label: prettyName(file.name),
					url: file.download_url,
				}))
				.sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }));

			select.innerHTML = "";

			if (!library.length) {
				const option = document.createElement("option");
				option.textContent = "No PDF files found";
				option.disabled = true;
				option.selected = true;
				select.appendChild(option);

				select.disabled = true;
				setStatus("There are no PDF files in the pdfs directory.");
				return;
			}

			select.disabled = false;

			library.forEach((entry) => {
				const option = document.createElement("option");

				option.value = entry.name;
				option.textContent = entry.label;

				select.appendChild(option);
			});

			/*
			 * Remember the last selected document during this browser
			 * session. If there isn't one, select the first PDF.
			 */
			const wanted = selectName || getLastSelected();

			if (wanted && library.some((entry) => entry.name === wanted)) {
				select.value = wanted;
			} else {
				select.value = library[0].name;
			}

			setStatus("");
		} catch (error) {
			console.error("Could not load PDF directory:", error);

			select.innerHTML = "";

			const option = document.createElement("option");
			option.textContent = "Could not load PDF list";
			option.disabled = true;
			option.selected = true;

			select.appendChild(option);
			select.disabled = true;

			setStatus("Could not read the PDF directory. " + error.message);
		}
	}

	/*
	 * ------------------------------------------------------------------
	 * LAST SELECTED PDF
	 * ------------------------------------------------------------------
	 */

	function getLastSelected() {
		try {
			return localStorage.getItem("pdf-viewer-last");
		} catch (e) {
			return null;
		}
	}

	function setLastSelected(name) {
		try {
			localStorage.setItem("pdf-viewer-last", name);
		} catch (e) {
			/* Ignore storage errors. */
		}
	}

	/*
	 * ------------------------------------------------------------------
	 * OPEN SELECTED PDF
	 * ------------------------------------------------------------------
	 */

	async function openSelected() {
		const entry = library.find((item) => item.name === select.value);

		if (!entry) {
			clearViewer();
			setStatus("No PDF has been selected.");
			return;
		}

		setLastSelected(entry.name);

		const token = ++loadToken;

		clearViewer();
		setStatus("Loading " + entry.label + "…");

		try {
			/*
			 * PDF.js can load the PDF directly from the GitHub download URL.
			 *
			 * This avoids copying the PDF into browser storage and means that
			 * the selector always uses the current PDF in the repository.
			 */
			const loadingTask = pdfjsLib.getDocument({
				url: entry.url,
			});

			const doc = await loadingTask.promise;

			if (token !== loadToken) {
				return;
			}

			const firstPage = await doc.getPage(1);

			const viewport = firstPage.getViewport({
				scale: 1,
			});

			ar = viewport.width / viewport.height;

			pdf = doc;
			total = doc.numPages;
			pos = 0;

			setStatus("");

			await layout();
		} catch (error) {
			console.error("Could not open PDF:", error);

			if (token === loadToken) {
				clearViewer();

				setStatus("Could not open “" + entry.label + "”. " + error.message);
			}
		}
	}

	/*
	 * ------------------------------------------------------------------
	 * CLEAR VIEWER
	 * ------------------------------------------------------------------
	 */

	function clearViewer() {
		pdf = null;
		total = 0;
		pos = 0;
		busy = false;
		layoutTok++;

		cache.clear();
		pending.clear();
		cacheKey = "";

		mount(slotL, null);
		mount(slotR, null);

		leaf.style.display = "none";

		book.style.width = "0";
		book.style.height = "0";

		counter.textContent = "";

		prevBtn.disabled = true;
		nextBtn.disabled = true;
	}

	/*
	 * ------------------------------------------------------------------
	 * BOOK MODEL
	 * ------------------------------------------------------------------
	 *
	 * Position 0 is the cover.
	 *
	 * Then:
	 *
	 *   pages 2-3
	 *   pages 4-5
	 *   pages 6-7
	 *   etc.
	 *
	 * On narrow screens, pages are shown one at a time.
	 */

	const spread = (p) =>
		mode === "double"
			? p === 0
				? { L: null, R: 0 }
				: {
						L: p,
						R: p + 1 < total ? p + 1 : null,
					}
			: {
					L: null,
					R: p,
				};

	const snap = (p) => (mode === "double" && p > 0 && p % 2 === 0 ? p - 1 : p);

	const nextPos = () => {
		const next = mode === "double" ? (pos === 0 ? 1 : pos + 2) : pos + 1;

		return next < total ? next : null;
	};

	const prevPos = () => (pos === 0 ? null : mode === "double" ? (pos === 1 ? 0 : pos - 2) : pos - 1);

	/*
	 * ------------------------------------------------------------------
	 * LAYOUT
	 * ------------------------------------------------------------------
	 */

	const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

	const FLIP_MS = reduceMotion ? 0 : 800;

	book.style.setProperty("--flip", FLIP_MS + "ms");

	let ar = 0.707;
	let mode = "single";
	let pageW = 0;
	let pageH = 0;
	let pos = 0;
	let busy = false;
	let layoutTok = 0;

	let cacheKey = "";

	const cache = new Map();
	const pending = new Map();

	const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

	/*
	 * ------------------------------------------------------------------
	 * LAYOUT THE BOOK
	 * ------------------------------------------------------------------
	 */

	async function layout() {
		if (!pdf) {
			return;
		}

		const tok = ++layoutTok;

		const W = stage.clientWidth;
		const H = stage.clientHeight;

		const single = Math.min(W, H * ar);

		const dbl = Math.min(W / 2, H * ar);

		mode = W >= 700 && total > 1 && dbl >= 0.75 * single ? "double" : "single";

		pageW = Math.floor(mode === "double" ? dbl : single);

		pageH = Math.floor(pageW / ar);

		pos = snap(pos);

		const dpr = Math.min(window.devicePixelRatio || 1, 2);

		const key = pageW + "x" + pageH + "@" + dpr;

		if (key !== cacheKey) {
			cache.clear();
			pending.clear();
			cacheKey = key;
		}

		book.classList.toggle("double", mode === "double");

		book.style.width = (mode === "double" ? pageW * 2 : pageW) + "px";

		book.style.height = pageH + "px";

		book.style.perspective = pageW * 4 + "px";

		[slotL, slotR, leaf].forEach((element) => {
			element.style.width = pageW + "px";

			element.style.height = pageH + "px";
		});

		slotL.style.left = "0px";

		slotR.style.left = leaf.style.left = (mode === "double" ? pageW : 0) + "px";

		leaf.style.display = "none";

		const s = spread(pos);

		await ensure([s.L, s.R]);

		if (tok !== layoutTok) {
			return;
		}

		mount(slotL, s.L);
		mount(slotR, s.R);

		shift(s, false);

		updateUi();
		prefetch();
	}

	/*
	 * Centre a lone cover or last page.
	 */

	function shift(s, animate) {
		const x = mode !== "double" ? 0 : s.L == null ? -pageW / 2 : s.R == null ? pageW / 2 : 0;

		if (!animate) {
			book.style.transition = "none";
		}

		book.style.transform = "translateX(" + x + "px)";

		if (!animate) {
			book.offsetWidth;
			book.style.transition = "";
		}
	}

	/*
	 * ------------------------------------------------------------------
	 * RENDER PDF PAGES
	 * ------------------------------------------------------------------
	 */

	function getBitmap(idx) {
		if (cache.has(idx)) {
			return Promise.resolve(cache.get(idx));
		}

		if (pending.has(idx)) {
			return pending.get(idx);
		}

		const doc = pdf;
		const key = cacheKey;
		const w = pageW;
		const h = pageH;

		const dpr = Math.min(window.devicePixelRatio || 1, 2);

		const job = (async () => {
			const page = await doc.getPage(idx + 1);

			const base = page.getViewport({
				scale: 1,
			});

			const vp = page.getViewport({
				scale: Math.min(w / base.width, h / base.height) * dpr,
			});

			const canvas = document.createElement("canvas");

			canvas.width = Math.round(w * dpr);

			canvas.height = Math.round(h * dpr);

			const ctx = canvas.getContext("2d");

			ctx.fillStyle = "#fff";

			ctx.fillRect(0, 0, canvas.width, canvas.height);

			await page.render({
				canvasContext: ctx,
				viewport: vp,
				transform: [1, 0, 0, 1, (canvas.width - vp.width) / 2, (canvas.height - vp.height) / 2],
			}).promise;

			pending.delete(idx);

			if (doc === pdf && key === cacheKey) {
				cache.set(idx, canvas);
			}

			return canvas;
		})();

		pending.set(idx, job);

		return job;
	}

	const ensure = (list) => Promise.all(list.filter((i) => i != null && i >= 0 && i < total).map(getBitmap));

	function mount(el, idx) {
		el.replaceChildren();

		el.classList.toggle("has-page", idx != null);

		const source = idx == null ? null : cache.get(idx);

		if (!source) {
			return;
		}

		const canvas = document.createElement("canvas");

		canvas.width = source.width;

		canvas.height = source.height;

		canvas.getContext("2d").drawImage(source, 0, 0);

		el.appendChild(canvas);
	}

	function prefetch() {
		for (const i of [...cache.keys()]) {
			if (i < pos - 2 || i > pos + 3) {
				cache.delete(i);
			}
		}

		for (let i = Math.max(0, pos - 2); i <= Math.min(total - 1, pos + 3); i++) {
			getBitmap(i);
		}
	}

	/*
	 * ------------------------------------------------------------------
	 * PAGE FLIP
	 * ------------------------------------------------------------------
	 */

	async function flip(newPos, dir) {
		if (busy || !pdf) {
			return;
		}

		busy = true;

		const a = spread(pos);
		const b = spread(newPos);
		const dbl = mode === "double";

		await ensure([a.L, a.R, b.L, b.R]);

		if (!pdf) {
			busy = false;
			return;
		}

		leaf.style.transition = "none";

		if (dir > 0) {
			/*
			 * Right page turns over to the left.
			 */
			mount(leafFront, a.R);

			mount(leafBack, dbl ? b.L : null);

			mount(slotR, b.R);

			leaf.style.transform = "rotateY(0deg)";
		} else {
			/*
			 * Left page turns back to the right.
			 */
			mount(leafFront, b.R);

			mount(leafBack, dbl ? a.L : null);

			mount(slotL, b.L);

			leaf.style.transform = "rotateY(-180deg)";
		}

		leaf.style.display = "block";

		leaf.offsetWidth;

		shift(b, true);

		leaf.style.transition = "transform " + FLIP_MS + "ms ease-in-out";

		leaf.style.transform = dir > 0 ? "rotateY(-180deg)" : "rotateY(0deg)";

		await wait(FLIP_MS + 50);

		pos = newPos;

		mount(slotL, b.L);

		mount(slotR, b.R);

		leaf.style.display = "none";

		busy = false;

		updateUi();
		prefetch();
	}

	/*
	 * ------------------------------------------------------------------
	 * USER INTERFACE
	 * ------------------------------------------------------------------
	 */

	function updateUi() {
		const s = spread(pos);

		const shown = [s.L, s.R].filter((x) => x != null).map((x) => x + 1);

		counter.textContent = shown.length > 1 ? "Pages " + shown[0] + "–" + shown[1] + " of " + total : "Page " + shown[0] + " of " + total;

		prevBtn.disabled = prevPos() === null;

		nextBtn.disabled = nextPos() === null;
	}

	/*
	 * ------------------------------------------------------------------
	 * ARROWS / KEYBOARD
	 * ------------------------------------------------------------------
	 */

	function go(dir) {
		const p = dir > 0 ? nextPos() : prevPos();

		if (p !== null) {
			flip(p, dir);
		}
	}

	prevBtn.addEventListener("click", () => go(-1));

	nextBtn.addEventListener("click", () => go(1));

	document.addEventListener("keydown", (e) => {
		if (e.target.tagName === "SELECT") {
			return;
		}

		if (e.key === "ArrowLeft") {
			go(-1);
		} else if (e.key === "ArrowRight") {
			go(1);
		}
	});

	/*
	 * ------------------------------------------------------------------
	 * SWIPE / TAP
	 * ------------------------------------------------------------------
	 */

	let sx = 0;
	let sy = 0;
	let down = false;

	stage.addEventListener("pointerdown", (e) => {
		down = true;
		sx = e.clientX;
		sy = e.clientY;
	});

	stage.addEventListener("pointercancel", () => {
		down = false;
	});

	stage.addEventListener("pointerup", (e) => {
		if (!down) {
			return;
		}

		down = false;

		const dx = e.clientX - sx;

		const dy = e.clientY - sy;

		if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
			go(dx < 0 ? 1 : -1);
		} else if (Math.abs(dx) < 10 && Math.abs(dy) < 10 && e.target.closest("#book")) {
			const r = book.getBoundingClientRect();

			go(e.clientX < r.left + r.width * (mode === "double" ? 0.5 : 0.3) ? -1 : 1);
		}
	});

	/*
	 * ------------------------------------------------------------------
	 * WINDOW RESIZE
	 * ------------------------------------------------------------------
	 */

	let resizeTimer;

	const relayout = () => (busy ? setTimeout(relayout, 200) : layout());

	window.addEventListener("resize", () => {
		clearTimeout(resizeTimer);

		resizeTimer = setTimeout(relayout, 200);
	});

	/*
	 * ------------------------------------------------------------------
	 * PDF SELECTION
	 * ------------------------------------------------------------------
	 */

	select.addEventListener("change", () => {
		select.blur();
		openSelected();
	});

	/*
	 * ------------------------------------------------------------------
	 * START
	 * ------------------------------------------------------------------
	 */

	(async function init() {
		if (!window.pdfjsLib || !window.pdfjsWorker) {
			setStatus("The PDF engine " + "(js/lib/pdf.js and " + "js/lib/pdf.worker.js) " + "did not load.");

			return;
		}

		/*
		 * The worker is bundled locally, so the PDF.js engine itself
		 * does not need to be downloaded from the internet.
		 */
		pdfjsLib.GlobalWorkerOptions.workerSrc = "js/lib/pdf.worker.js";

		/*
		 * Read the actual contents of the repository's pdfs directory.
		 */
		await loadLibrary();

		/*
		 * Open whichever document was selected.
		 */
		if (library.length) {
			await openSelected();
		}
	})();
})();
