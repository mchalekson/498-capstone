/* ===========================================================================
 * IB World School scraper — runs in YOUR browser's DevTools console.
 *
 * Why this and not Python: ibo.org returns 403 to any automated browser
 * (Playwright/Selenium), but your normal browser gets 200. This script lets
 * your own trusted browser do the work: it clicks "View more schools" until
 * every school is loaded, then extracts the table and downloads a CSV.
 *
 * HOW TO USE
 *  1. In normal Chrome, open the results URL (Country = United States), e.g.:
 *     https://ibo.org/programmes/find-an-ib-school/?SearchFields.Region=iba&SearchFields.Country=US&SearchFields.State=&SearchFields.Keywords=&SearchFields.Language=&SearchFields.BoardingFacilities=&SearchFields.SchoolGender=&SearchFields.TypePublic=true&SearchFields.TypePrivate=true
 *     (make sure the school TABLE is showing, with a "View more schools" button)
 *  2. Press F12 -> Console tab.
 *  3. Paste this whole file and press Enter. If Chrome warns about pasting,
 *     type  allow pasting  first, then paste again.
 *  4. Watch the count climb. When it finishes it downloads ib_us.csv.
 *     (~1,900 US schools => a few minutes.)
 * ======================================================================== */

(async () => {
  const PROG_BY_TOOLTIP = {
    "Primary Years Programme": "PYP",
    "Middle Years Programme": "MYP",
    "Diploma Programme": "DP",
    "Career-related Programme": "CP",
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const rowEls = () =>
    Array.from(document.querySelectorAll("table.Table tr")).filter(
      (tr) => tr.querySelector("td")
    );

  const findMoreButton = () =>
    Array.from(document.querySelectorAll("a, button")).find(
      (el) =>
        /view more schools/i.test(el.textContent || "") &&
        el.offsetParent !== null
    );

  // --- 1. Click "View more schools" until it's gone -----------------------
  let clicks = 0;
  const MAX_CLICKS = 400;
  while (clicks < MAX_CLICKS) {
    const btn = findMoreButton();
    if (!btn) break;
    const before = rowEls().length;
    btn.scrollIntoView({ block: "center" });
    btn.click();
    clicks++;
    // wait for new rows to append (or give up after ~6s)
    let waited = 0;
    while (waited < 6000 && rowEls().length <= before) {
      await sleep(300);
      waited += 300;
    }
    if (clicks % 5 === 0 || rowEls().length === before) {
      console.log(`clicks: ${clicks} | rows loaded: ${rowEls().length}`);
    }
    await sleep(400); // polite pause
    if (rowEls().length === before) {
      // no growth after a click -> likely finished or blocked; try once more then stop
      const btn2 = findMoreButton();
      if (!btn2) break;
    }
  }
  console.log(`Finished clicking after ${clicks} clicks. Extracting...`);

  // --- 2. Extract the table ----------------------------------------------
  const rows = rowEls();
  const data = [];
  const seen = new Set();
  for (const tr of rows) {
    const tds = tr.querySelectorAll("td");
    if (tds.length < 5) continue;
    const a = tds[0].querySelector("a");
    const name = (a ? a.textContent : tds[0].textContent).trim();
    if (!name) continue;
    const href = a ? a.getAttribute("href") || "" : "";
    const m = href.match(/\/school\/([0-9A-Za-z]+)/);
    const id = m ? m[1] : a ? (a.id || "") : "";
    const key = id || name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);

    const progs = new Set();
    for (let i = 1; i <= 4; i++) {
      const td = tds[i];
      if (!td) continue;
      const span = td.querySelector("span[data-tooltip]");
      const checked = /[\u2714\u2713]/.test(td.textContent || "");
      if (span && checked) {
        const code = PROG_BY_TOOLTIP[(span.getAttribute("data-tooltip") || "").trim()];
        if (code) progs.add(code);
      }
    }
    const langs = Array.from(tds[tds.length - 1].querySelectorAll("span.Tag"))
      .map((s) => s.textContent.trim())
      .join(", ");

    data.push({
      name,
      school_id: id,
      offers_pyp: progs.has("PYP"),
      offers_myp: progs.has("MYP"),
      offers_dp: progs.has("DP"),
      offers_cp: progs.has("CP"),
      programmes: ["PYP", "MYP", "DP", "CP"].filter((p) => progs.has(p)).join(", "),
      offers_any_ib: progs.size > 0,
      languages: langs,
      ibo_url: id ? `https://ibo.org/school/${id}/` : "",
    });
  }

  // --- 3. Build CSV and download -----------------------------------------
  const cols = [
    "name", "school_id", "offers_pyp", "offers_myp", "offers_dp", "offers_cp",
    "programmes", "offers_any_ib", "languages", "ibo_url",
  ];
  const esc = (v) => {
    const s = String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const csv = [cols.join(",")]
    .concat(data.map((r) => cols.map((c) => esc(r[c])).join(",")))
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "ib_us.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();

  const dp = data.filter((d) => d.offers_dp).length;
  console.log(`DONE: ${data.length} schools extracted (${dp} offer the Diploma Programme). Downloaded ib_us.csv`);
})();
