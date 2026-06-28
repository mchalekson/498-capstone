"""
ib_school_scraper.py  —  IB World School directory scraper (ibo.org)
====================================================================

Pulls every IB World School for a country from the "Find an IB World School"
results table and writes a clean CSV: school name, IB school ID, which of
PYP / MYP / DP / CP each school is authorised for, and language(s) of
instruction. Designed to join onto your CEEB/NCES master DB by school name.

WHAT WE LEARNED (so the code makes sense):
  * The finder is a server-rendered page. You request the results URL with
    SearchFields.* query params and it returns an HTML <table> of schools.
  * There is NO hidden JSON API. The table is the data.
  * ibo.org returns 403 to obvious automation but 200 to a normal browser.
    So this script fetches through your REAL installed Chrome (--use-chrome),
    and—because that can still be blocked—also supports parsing page(s) you
    saved by hand (--from-html), which ALWAYS works.
  * "All Programmes" (SearchFields.ProgrammeAll=true) means "offers every
    programme", which is why a search with it set returns almost nothing.
    The default URL below omits it, returning ALL schools in the country.

  * Results load 20 at a time via a "View more schools" button that appends
    rows to the table (the country list is ~1,900 schools, so ~95 clicks).
    --use-chrome clicks that button for you until everything is loaded.

------------------------------------------------------------------------------
TWO WAYS TO RUN
------------------------------------------------------------------------------
Option A — automated through your real Chrome (recommended; handles the
"View more" button for you):
        pip install playwright beautifulsoup4
        playwright install chromium      # only needed if real Chrome is absent
        python ib_school_scraper.py --use-chrome --out ib_us.csv
  Add --headed to watch it click through. If it reports a 403, use Option B.

Option B — fully manual (guaranteed, but tedious for a big country):
  Open the URL from `--print-url` in your normal Chrome, click "View more
  schools" until it disappears, then Cmd/Ctrl+S -> "Webpage, HTML Only", and:
        python ib_school_scraper.py --from-html saved_page.html --out ib_us.csv
  (For a single state the list is short, so Option B is easy per-state.)

Useful flags:
  --public-only     only US public ("state") schools  (TypePublic, drop TypePrivate)
  --country-code US --region iba    change country/region (see notes at bottom)
  --print-url       just print the results URL and exit
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import re
import sys
import time
from dataclasses import dataclass, field, asdict

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependency. Run:  pip install beautifulsoup4")

BASE = "https://ibo.org/programmes/find-an-ib-school/"

PROG_BY_TOOLTIP = {
    "Primary Years Programme": "PYP",
    "Middle Years Programme": "MYP",
    "Diploma Programme": "DP",
    "Career-related Programme": "CP",
}


@dataclass
class School:
    name: str = ""
    school_id: str = ""
    offers_pyp: bool = False
    offers_myp: bool = False
    offers_dp: bool = False
    offers_cp: bool = False
    programmes: str = ""
    offers_any_ib: bool = False
    languages: str = ""
    ibo_url: str = ""
    country_code: str = ""
    scrape_date: str = field(default_factory=lambda: _dt.date.today().isoformat())


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------
def build_url(region: str, country_code: str, public_only: bool, page: int | None = None) -> str:
    params = [
        ("SearchFields.Region", region),
        ("SearchFields.Country", country_code),
        ("SearchFields.State", ""),
        ("SearchFields.Keywords", ""),
        ("SearchFields.Language", ""),
        ("SearchFields.BoardingFacilities", ""),
        ("SearchFields.SchoolGender", ""),
        ("SearchFields.TypePublic", "true"),
    ]
    if not public_only:
        params.append(("SearchFields.TypePrivate", "true"))
    if page and page > 1:
        # Best-guess pagination param; harmless if the site ignores it, and the
        # next-link auto-detection below is the primary mechanism anyway.
        params.append(("SearchFields.Page", str(page)))
    from urllib.parse import urlencode
    return BASE + "?" + urlencode(params)


# ---------------------------------------------------------------------------
# Parsing  (validated against a real saved results page)
# ---------------------------------------------------------------------------
def parse_results_table(html: str, country_code: str = "") -> list[School]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="Table")
    if not table:
        return []
    schools: list[School] = []
    for tr in table.find_all("tr")[1:]:  # skip header
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        a = tds[0].find("a")
        name = (a.get_text(strip=True) if a else tds[0].get_text(strip=True)).strip()
        if not name:
            continue
        href = a.get("href", "") if a else ""
        m = re.search(r"/school/([0-9A-Za-z]+)", href)
        school_id = m.group(1) if m else (a.get("id", "").strip() if a else "")

        progs: set[str] = set()
        for td in tds[1:5]:
            span = td.find("span", attrs={"data-tooltip": True})
            checked = ("✔" in td.get_text()) or ("✓" in td.get_text())
            if span and checked:
                code = PROG_BY_TOOLTIP.get(span["data-tooltip"].strip())
                if code:
                    progs.add(code)

        langs = [s.get_text(strip=True) for s in tds[-1].select("span.Tag")]

        s = School(
            name=name,
            school_id=school_id,
            offers_pyp="PYP" in progs,
            offers_myp="MYP" in progs,
            offers_dp="DP" in progs,
            offers_cp="CP" in progs,
            programmes=", ".join(p for p in ("PYP", "MYP", "DP", "CP") if p in progs),
            offers_any_ib=bool(progs),
            languages=", ".join(langs),
            ibo_url=("https://ibo.org/school/%s/" % school_id) if school_id else "",
            country_code=country_code,
        )
        schools.append(s)
    return schools


def find_next_url(html: str, current_url: str) -> str | None:
    """Look for a 'next page' link in the results, if pagination exists."""
    soup = BeautifulSoup(html, "html.parser")
    # Common patterns: rel=next, aria-label Next, a '»'/'Next' link, or ?...Page=
    candidates = soup.select("a[rel='next'], a[aria-label*='Next' i]")
    for a in candidates:
        href = a.get("href")
        if href:
            return _abs(href)
    for a in soup.find_all("a"):
        txt = a.get_text(strip=True).lower()
        href = a.get("href", "")
        if href and ("page=" in href.lower()) and txt in ("next", "»", "›", ">"):
            return _abs(href)
    return None


def _abs(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://ibo.org" + href
    return href


# ---------------------------------------------------------------------------
# Fetching through the user's real Chrome (best-effort vs the 403)
# ---------------------------------------------------------------------------
def _ids_of(html: str) -> set[str]:
    return {(s.school_id or s.name.lower()) for s in parse_results_table(html)}


def fetch_all_via_chrome(region: str, country_code: str, public_only: bool,
                         headed: bool, delay: float, max_pages: int) -> list[str]:
    """Open results in real Chrome and page through them with TOP-LEVEL
    navigations (which the site returns 200 for), since the in-page
    'View more' button fires an XHR that the site 403s. Auto-detects the
    correct pagination query parameter."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Run:  pip install playwright  &&  playwright install chromium")

    import tempfile, os
    from urllib.parse import urlparse, parse_qs
    profile_dir = os.path.join(tempfile.gettempdir(), "ib_scraper_chrome_profile")

    PAGE_PARAM_CANDIDATES = [
        "SearchFields.Page", "SearchFields.PageNumber", "SearchFields.PageIndex",
        "SearchFields.Skip", "Page", "page",
    ]

    def url_with(extra: tuple[str, str] | None) -> str:
        base = build_url(region, country_code, public_only)
        return base + (("&" + extra[0] + "=" + extra[1]) if extra else "")

    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                profile_dir, channel="chrome", headless=not headed,
                viewport={"width": 1366, "height": 900}, locale="en-US",
            )
        except Exception:
            print("[fetch] real Chrome not found; falling back to bundled Chromium "
                  "(more likely to be blocked).")
            ctx = p.chromium.launch_persistent_context(
                profile_dir, headless=not headed,
                viewport={"width": 1366, "height": 900}, locale="en-US",
            )
        page = ctx.new_page()

        def load(url: str) -> str | None:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(int(delay * 1000))
            if resp and resp.status == 403:
                return None
            _accept_cookies(page)
            try:
                page.wait_for_selector("table.Table tr", timeout=12_000)
            except Exception:
                pass
            return page.content()

        # Page 1
        print("[fetch] loading page 1 ...")
        html1 = load(url_with(None))
        if html1 is None:
            print("[fetch] 403 even on the first page. Use the manual --from-html route.")
            ctx.close()
            return []
        ids1 = _ids_of(html1)
        print(f"[fetch] page 1: {len(ids1)} schools")
        if not ids1:
            print("[fetch] no schools on page 1 (map view or block). Try --headed / --from-html.")
            ctx.close()
            return []

        # Auto-detect which pagination parameter actually advances the results.
        page_param = None
        for cand in PAGE_PARAM_CANDIDATES:
            test_val = "40" if "Skip" in cand else "2"
            html2 = load(url_with((cand, test_val)))
            if not html2:
                continue
            ids2 = _ids_of(html2)
            if ids2 and ids2 != ids1:
                page_param = cand
                print(f"[fetch] pagination parameter detected: {cand}")
                break
        if not page_param:
            print("[fetch] Could not find a working pagination parameter — the site "
                  "may only page via the blocked XHR. Got the first 20 schools only.\n"
                  "        Next step: in Chrome DevTools (Network tab), click 'View more "
                  "schools' once and copy the request URL; send it to me and I'll wire it in.")
            ctx.close()
            return [html1]

        # Walk pages until results stop changing / stop adding new schools.
        all_html = [html1]
        seen = set(ids1)
        is_skip = "Skip" in page_param
        prev_ids = ids1
        for i in range(2, max_pages + 1):
            val = str((i - 1) * 20) if is_skip else str(i)
            html = load(url_with((page_param, val)))
            if not html:
                print(f"[fetch] page {i}: 403, stopping.")
                break
            ids = _ids_of(html)
            new = ids - seen
            if not ids or ids == prev_ids or not new:
                break
            seen |= ids
            all_html.append(html)
            prev_ids = ids
            print(f"[fetch] page {i}: +{len(new)} new ({len(seen)} total)")
            time.sleep(delay)

        print(f"[fetch] done; {len(seen)} unique schools across {len(all_html)} pages.")
        ctx.close()
        return all_html


def _accept_cookies(page) -> None:
    for sel in (
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "#CybotCookiebotDialogBodyButtonAccept",
        "button:has-text('Allow all')",
        "button:has-text('Accept')",
    ):
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                page.wait_for_timeout(800)
                return
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_csv(schools: list[School], path: str) -> None:
    # De-dupe by school_id (or name) in case saved pages overlap.
    seen, unique = set(), []
    for s in schools:
        key = s.school_id or s.name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    if not unique:
        print("[write] 0 schools parsed. If you used --from-html, make sure the "
              "saved page actually shows the results table (not the map view).")
        return
    fields = list(asdict(unique[0]).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in unique:
            w.writerow(asdict(s))
    dp = sum(s.offers_dp for s in unique)
    print(f"[write] wrote {len(unique)} schools -> {path}  ({dp} offer the Diploma Programme)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape the IB World School directory (ibo.org)")
    ap.add_argument("--region", default="iba", help="IB region code (default iba = IB Americas)")
    ap.add_argument("--country-code", default="US", help="2-letter country code (default US)")
    ap.add_argument("--public-only", action="store_true", help="Only public/state schools")
    ap.add_argument("--from-html", nargs="+", metavar="FILE", help="Parse saved results page(s)")
    ap.add_argument("--use-chrome", action="store_true", help="Fetch via real Chrome (Playwright)")
    ap.add_argument("--headed", action="store_true", help="Show the browser (with --use-chrome)")
    ap.add_argument("--delay", type=float, default=1.5, help="Seconds between page loads (politeness)")
    ap.add_argument("--max-pages", dest="max_clicks", type=int, default=200, help="Safety cap on pages (20 schools each)")
    ap.add_argument("--out", default="ib_world_schools.csv", help="Output CSV path")
    ap.add_argument("--print-url", action="store_true", help="Print the results URL and exit")
    args = ap.parse_args()

    url = build_url(args.region, args.country_code, args.public_only)
    if args.print_url:
        print(url)
        return

    all_schools: list[School] = []
    if args.from_html:
        for fp in args.from_html:
            with open(fp, encoding="utf-8") as f:
                rows = parse_results_table(f.read(), args.country_code)
            print(f"[parse] {fp}: {len(rows)} schools")
            all_schools.extend(rows)
    elif args.use_chrome:
        for html in fetch_all_via_chrome(args.region, args.country_code, args.public_only,
                                         args.headed, args.delay, args.max_clicks):
            all_schools.extend(parse_results_table(html, args.country_code))
    else:
        sys.exit("Choose a mode:  --from-html FILE [FILE ...]   or   --use-chrome\n"
                 "(Run with --print-url to get the URL to open/save in your browser.)")

    write_csv(all_schools, args.out)


if __name__ == "__main__":
    main()
