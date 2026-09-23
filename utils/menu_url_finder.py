"""Resolve a restaurant's menu URL starting from its homepage.

Google Places API has no menu-URL field, so the menu link has to be recovered
from the site that `places.websiteUri` points at. This module does that with
three escalating strategies (cheapest first):

    1. parse the homepage HTML   -- JSON-LD, anchors, POS platforms, iframes
    2. read /sitemap.xml         -- server-generated, survives JS-only navs
    3. probe common paths        -- /menu, /menus, /food, ...

Only static HTML is fetched; no JavaScript runs. Sites that render their nav
client-side are flagged `likely_js_rendered` so you can route just those to a
headless browser instead of paying for one everywhere.

CLI:
    python menu_url_finder.py urls.txt -o results.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from platform_fingerprint import PRICE_TOKEN, resolve_order_url

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

HEADERS = {
    # Without a browser-shaped UA, Cloudflare-fronted sites return 403.
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Hosted-menu / online-ordering platforms. A link to one of these *is* the menu.
POS_HOSTS = (
    "toasttab.com", "popmenu.com", "bentobox", "getbento.com", "owner.com",
    "chownow.com", "squareup.com", "square.site", "clover.com", "menufy.com",
    "slicelife.com", "spoton.com", "ubereats.com", "doordash.com",
    "grubhub.com", "opentable.com", "resy.com", "single-platform",
    "menu.dinein", "orderup", "olo.com",
)

# `websiteUri` frequently points at social pages, which never yield a menu URL.
SOCIAL_HOSTS = (
    "facebook.com", "fb.me", "instagram.com", "twitter.com", "x.com",
    "linktr.ee", "tiktok.com", "yelp.com",
)

COMMON_PATHS = (
    "/menu", "/menus", "/our-menu", "/food", "/food-menu",
    "/dinner", "/menu.pdf", "/drinks",
)

MENU_WORD = re.compile(r"\bmenus?\b", re.I)

# Reservation widgets are not menus. They sit in POS_HOSTS for historical
# reasons, so filter them out of `platform` scoring -- a Resy link scored 70 as
# "the menu" is a false positive that costs an extraction call to discover.
RESERVATION_HOSTS = ("opentable.com", "resy.com", "sevenrooms.com", "tock.co")

# Ordering platforms are linked from footers for legal reasons too. Toast's
# diner terms-of-service scored 70 as "the menu" for mayurius.com purely because
# the host matched `toasttab.com`.
NON_MENU_PATHS = (
    "/terms", "/terms-of-service", "/tos", "/privacy", "/legal", "/cookie",
    "/accessibility", "/about", "/careers", "/help", "/support", "/faq",
    "/login", "/signin", "/signup", "/gift", "/giftcard",
)
# Shared with the fingerprinting tier so "is there a price here" means the same
# thing everywhere. Requires cents -- see PRICE_TOKEN for why.
PRICE = PRICE_TOKEN
LOC_TAG = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)

# Candidate confidence. Higher wins when several signals fire on one site.
SCORE = {
    "jsonld": 100,    # schema.org Restaurant.hasMenu -- explicit and rare
    "pdf": 90,        # a linked .pdf whose name says menu
    "anchor": 80,     # <a href="/menu">Menu</a>
    "platform": 70,   # link out to Toast / Popmenu / Square / ...
    "iframe": 65,     # embedded menu widget; the src is fetchable alone
    "sitemap": 60,    # /sitemap.xml listed a menu-ish path
    "probe": 50,      # guessed path that returned real content
}


# TLS trust. Corporate proxies that inspect TLS present their own root CA,
# which Python's bundled `certifi` does not trust -- every fetch then dies with
# CERTIFICATE_VERIFY_FAILED before any HTTP happens. Point MENU_CA_BUNDLE (or
# --ca-bundle) at that root, or use --insecure to skip verification.
VERIFY_DEFAULT: str | bool = os.environ.get("MENU_CA_BUNDLE") or True


def configure_tls(ca_bundle: str | None = None, insecure: bool = False) -> None:
    """Set the process-wide TLS trust used by new Sessions."""
    global VERIFY_DEFAULT
    if insecure:
        VERIFY_DEFAULT = False
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")
        try:  # urllib3 v1 and v2 expose this differently
            from urllib3.exceptions import InsecureRequestWarning
            warnings.simplefilter("ignore", InsecureRequestWarning)
        except ImportError:
            pass
    elif ca_bundle:
        if not Path(ca_bundle).exists():
            raise FileNotFoundError(f"CA bundle not found: {ca_bundle}")
        VERIFY_DEFAULT = ca_bundle


def build_session(total_retries: int = 2, verify: str | bool | None = None) -> requests.Session:
    """A Session with connection pooling and backoff on transient failures."""
    session = requests.Session()
    session.headers.update(HEADERS)
    session.verify = VERIFY_DEFAULT if verify is None else verify
    retry = Retry(
        total=total_retries,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=32)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _normalize(url: str) -> str:
    """Add a scheme if the input is a bare hostname."""
    url = (url or "").strip()
    if url and not urlparse(url).scheme:
        url = "https://" + url
    return url


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def _is_homepage(url: str, home: str) -> bool:
    """True if `url` is just the site root -- i.e. a soft-404 bounce."""
    a, b = urlparse(url), urlparse(home)
    return a.netloc == b.netloc and a.path.strip("/") in ("", b.path.strip("/"))


# --------------------------------------------------------------------------- #
# Strategy 1 -- parse the homepage HTML
# --------------------------------------------------------------------------- #

def find_menu_urls(
    site_url: str,
    session: requests.Session | None = None,
    timeout: float = 10.0,
) -> dict:
    """Fetch a homepage and extract every menu-URL candidate in its HTML.

    Returns a dict with `candidates` (ranked), plus `menu_inline_on_homepage`
    and `likely_js_rendered` so callers can tell "no link" apart from
    "no link because nothing rendered".
    """
    session = session or build_session()
    site_url = _normalize(site_url)
    result: dict = {
        "ok": False,
        "input_url": site_url,
        "final_url": None,
        "status": None,
        "candidates": [],
        "menu_inline_on_homepage": False,
        "likely_js_rendered": False,
        "is_social_only": _host(site_url).endswith(SOCIAL_HOSTS),
        "error": None,
    }

    if result["is_social_only"]:
        result["error"] = "websiteUri points at a social profile, not a site"
        return result

    try:
        resp = session.get(site_url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, requests.exceptions.SSLError):
            result["hint"] = (
                "TLS verification failed before any HTTP request -- almost always an "
                "intercepting proxy whose root CA Python does not trust. Export "
                "MENU_CA_BUNDLE=/path/to/corp-root.pem, pass --ca-bundle, or "
                "--insecure to skip verification."
            )
        return result

    result["status"] = resp.status_code
    result["final_url"] = base = resp.url
    if resp.status_code >= 400:
        result["error"] = f"HTTP {resp.status_code}"
        return result

    result["ok"] = True
    soup = BeautifulSoup(resp.text, "html.parser")
    found: list[dict] = []
    jsonld_blobs: list = []
    # Handed to resolve_order_url so tiers 0-1 are free; stripped before the
    # report is serialised (see resolve_menu_url).
    result["_soup"] = soup
    result["_jsonld"] = jsonld_blobs
    result["_resp"] = resp
    result["_body"] = resp.text

    def add(href: str | None, kind: str) -> None:
        if not href:
            return
        href = href.strip()
        if not href or href.startswith(("mailto:", "tel:", "#", "javascript:", "data:")):
            return
        found.append({"url": urljoin(base, href), "kind": kind, "score": SCORE[kind]})

    # 1a. schema.org Restaurant -> hasMenu / menu. Most reliable when present.
    # Each parsed blob is kept so the order-URL resolver can read `OrderAction`
    # out of the same markup without re-fetching or re-parsing.
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        jsonld_blobs.append(data)
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            # @graph and nested nodes both carry Restaurant objects.
            stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            for key in ("hasMenu", "menu"):
                val = node.get(key)
                if isinstance(val, str):
                    add(val, "jsonld")
                elif isinstance(val, dict):
                    add(val.get("url"), "jsonld")

    # 1b. Anchors whose href or link text says "menu".
    anchors = soup.find_all("a", href=True)
    for a in anchors:
        href = a["href"]
        text = a.get_text(" ", strip=True)
        if MENU_WORD.search(href) or MENU_WORD.search(text):
            is_pdf = href.lower().split("?")[0].split("#")[0].endswith(".pdf")
            add(href, "pdf" if is_pdf else "anchor")

    # 1c. Outbound links to hosted-menu / ordering platforms.
    for a in anchors:
        href = a["href"].lower()
        if any(h in href for h in RESERVATION_HOSTS):
            continue  # booking widget, not a menu
        path = urlparse(href).path.rstrip("/")
        if path and path.startswith(NON_MENU_PATHS):
            continue  # platform boilerplate: terms, privacy, gift cards
        if any(h in href for h in POS_HOSTS):
            add(a["href"], "platform")

    # 1d. Embedded menu widgets -- the src can be fetched on its own.
    for frame in soup.find_all(["iframe", "embed", "object"]):
        src = frame.get("src") or frame.get("data")
        if src and (any(h in src.lower() for h in POS_HOSTS) or MENU_WORD.search(src)):
            add(src, "iframe")

    # 1e. Is the menu inline on this very page? Then there's no separate URL.
    body = soup.get_text(" ", strip=True)
    result["menu_inline_on_homepage"] = (
        len(PRICE.findall(body)) >= 8 and bool(MENU_WORD.search(body))
    )
    # Thin text + no links at all == the nav was almost certainly JS-injected.
    result["likely_js_rendered"] = len(body) < 500 and not anchors

    result["candidates"] = _dedupe(found)
    return result


def _dedupe(candidates: list[dict]) -> list[dict]:
    """Keep the highest-scoring entry per URL, ranked best-first."""
    best: dict[str, dict] = {}
    for c in sorted(candidates, key=lambda c: -c["score"]):
        best.setdefault(c["url"], c)
    return sorted(best.values(), key=lambda c: -c["score"])


# --------------------------------------------------------------------------- #
# Strategy 2 -- /sitemap.xml
# --------------------------------------------------------------------------- #

def menu_from_sitemap(
    site_url: str,
    session: requests.Session | None = None,
    timeout: float = 10.0,
    follow_index: bool = True,
) -> list[str]:
    """Look for menu-ish paths in /sitemap.xml.

    Sitemaps are server-generated, so this often rescues Wix/SPA sites whose
    nav never appears in the static HTML. Follows one level of sitemap index.
    """
    session = session or build_session()
    parts = urlparse(_normalize(site_url))
    root = f"{parts.scheme}://{parts.netloc}"

    def fetch_locs(url: str) -> list[str]:
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
        except requests.RequestException:
            return []
        if resp.status_code >= 400 or "xml" not in resp.headers.get("Content-Type", "xml"):
            return []
        return LOC_TAG.findall(resp.text)

    def menu_pages(urls: list[str]) -> list[str]:
        """Menu-ish URLs that are actual pages.

        A child sitemap named `restaurants-menu-sitemap.xml` matches MENU_WORD
        as readily as a real menu page does, and handing that to the extractor
        spends an API call to read XML.
        """
        return [u for u in urls
                if MENU_WORD.search(u)
                and not u.lower().split("?")[0].endswith((".xml", ".xml.gz"))]

    locs = fetch_locs(f"{root}/sitemap.xml")
    hits = menu_pages(locs)

    # A sitemap index lists child sitemaps rather than pages.
    if follow_index and not hits:
        children = [u for u in locs if u.lower().endswith((".xml", ".xml.gz"))][:5]
        for child in children:
            hits.extend(menu_pages(fetch_locs(child)))

    seen: dict[str, None] = {}
    for url in hits:
        seen.setdefault(url, None)
    return list(seen)


# --------------------------------------------------------------------------- #
# Strategy 3 -- probe common paths
# --------------------------------------------------------------------------- #

def probe_common_paths(
    site_url: str,
    session: requests.Session | None = None,
    timeout: float = 8.0,
    paths: tuple[str, ...] = COMMON_PATHS,
) -> list[str]:
    """HEAD/GET a handful of conventional menu paths.

    Rejects soft-404s: a 200 that redirected back to the homepage, or that
    returned something other than HTML/PDF, does not count as a hit.
    """
    session = session or build_session()
    parts = urlparse(_normalize(site_url))
    root = f"{parts.scheme}://{parts.netloc}"
    hits: list[str] = []

    for path in paths:
        url = root + path
        try:
            resp = session.head(url, timeout=timeout, allow_redirects=True)
            # Plenty of servers mishandle HEAD; retry once with GET.
            if resp.status_code >= 400 or resp.status_code == 405:
                resp = session.get(url, timeout=timeout, allow_redirects=True,
                                   stream=True)
                resp.close()
        except requests.RequestException:
            continue

        if resp.status_code != 200:
            continue
        ctype = resp.headers.get("Content-Type", "").lower()
        if not ("html" in ctype or "pdf" in ctype or not ctype):
            continue
        if _is_homepage(resp.url, root):
            continue  # bounced to home == soft 404
        hits.append(resp.url)

    return hits


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #

def resolve_menu_url(
    site_url: str,
    session: requests.Session | None = None,
    timeout: float = 10.0,
    use_sitemap: bool = True,
    use_probe: bool = True,
    use_order: bool = True,
) -> dict:
    """Return the single best menu URL for one restaurant site.

    Escalates only as needed: the homepage is fetched anyway, so parsing it is
    free; /sitemap.xml costs one request; path probing costs a few HEADs.

    `use_order` additionally resolves an ordering URL and identifies the platform
    behind it. That's tracked separately from `menu_url` rather than competing
    with it: the marketing menu usually has the better dish descriptions, the
    order page has the prices, and the best record joins both.
    """
    report = find_menu_urls(site_url, session=session, timeout=timeout)
    soup = report.pop("_soup", None)
    jsonld_blobs = report.pop("_jsonld", [])
    home_resp = report.pop("_resp", None)
    home_body = report.pop("_body", "")
    strategies = ["html"]

    if not report["candidates"] and use_sitemap and not report["is_social_only"]:
        strategies.append("sitemap")
        for url in menu_from_sitemap(site_url, session=session, timeout=timeout):
            report["candidates"].append(
                {"url": url, "kind": "sitemap", "score": SCORE["sitemap"]}
            )

    if not report["candidates"] and use_probe and not report["is_social_only"]:
        strategies.append("probe")
        for url in probe_common_paths(site_url, session=session, timeout=timeout):
            report["candidates"].append(
                {"url": url, "kind": "probe", "score": SCORE["probe"]}
            )

    report["candidates"] = _dedupe(report["candidates"])
    report["strategies_tried"] = strategies

    top = report["candidates"][0] if report["candidates"] else None
    report["menu_url"] = top["url"] if top else None
    report["menu_url_kind"] = top["kind"] if top else None

    if report["menu_url"]:
        report["outcome"] = "menu_url"
    elif report["menu_inline_on_homepage"]:
        # No separate URL to find -- extract straight from the homepage.
        report["outcome"] = "inline_on_homepage"
        report["menu_url"] = report["final_url"]
    elif report["likely_js_rendered"]:
        report["outcome"] = "needs_browser"
    elif report["is_social_only"]:
        report["outcome"] = "social_only"
    elif not report["ok"]:
        report["outcome"] = "fetch_failed"
    else:
        report["outcome"] = "not_found"

    # Ordering tier. Runs even when a menu URL was found -- a marketing menu
    # that resolved cleanly is exactly the case that turns out to have no
    # prices, which is the whole reason this tier exists.
    if use_order and report["ok"] and not report["is_social_only"]:
        strategies.append("order")
        order = resolve_order_url(
            report.get("final_url") or site_url,
            soup=soup, jsonld_blobs=jsonld_blobs,
            session=session, timeout=timeout,
            home_response=home_resp, home_body=home_body,
        )
        report.update(order)
        report["strategies_tried"] = strategies
        if report.get("order_url") and report["outcome"] == "not_found":
            report["outcome"] = "order_url_only"

    return report


# --------------------------------------------------------------------------- #
# Batch runner
# --------------------------------------------------------------------------- #

def load_urls(path: str | Path) -> list[dict]:
    """Load restaurant sites from a file.

    Accepts, one record per line:
        https://example.com
        place_id_abc, https://example.com
        place_id_abc<TAB>https://example.com
        {"place_id": "abc", "website_uri": "https://example.com"}   (JSONL)

    Blank lines and `#` comments are skipped. A whole-file JSON array of
    objects or strings also works.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    records: list[dict] = []

    # Whole-file JSON array (e.g. dumped straight from a Places response).
    stripped = text.lstrip()
    if stripped.startswith("["):
        for item in json.loads(text):
            if isinstance(item, str):
                records.append({"id": None, "url": _normalize(item)})
            elif isinstance(item, dict):
                records.append({
                    "id": item.get("place_id") or item.get("id"),
                    "url": _normalize(
                        item.get("website_uri") or item.get("websiteUri")
                        or item.get("url") or ""
                    ),
                })
        return [r for r in records if r["url"]]

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("{"):  # JSONL
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.append({
                "id": obj.get("place_id") or obj.get("id"),
                "url": _normalize(
                    obj.get("website_uri") or obj.get("websiteUri")
                    or obj.get("url") or ""
                ),
            })
            continue

        fields = [f.strip() for f in re.split(r"[\t,;]", line) if f.strip()]
        url = next((f for f in fields if "." in f and " " not in f), None)
        if not url:
            continue
        ident = next((f for f in fields if f != url), None)
        records.append({"id": ident, "url": _normalize(url)})

    return [r for r in records if r["url"]]


def run_batch(
    urls_path: str | Path,
    out_path: str | Path | None = None,
    workers: int = 8,
    timeout: float = 10.0,
    use_sitemap: bool = True,
    use_probe: bool = True,
    use_order: bool = True,
    verbose: bool = True,
) -> list[dict]:
    """Resolve a menu URL for every site in `urls_path`.

    Runs `workers` sites concurrently against one pooled Session and writes a
    JSON array of per-site reports to `out_path`.
    """
    records = load_urls(urls_path)
    if verbose:
        print(f"Loaded {len(records)} site(s) from {urls_path}", file=sys.stderr)

    session = build_session()
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                resolve_menu_url, rec["url"],
                session=session, timeout=timeout,
                use_sitemap=use_sitemap, use_probe=use_probe,
                use_order=use_order,
            ): rec
            for rec in records
        }
        for future in as_completed(futures):
            rec = futures[future]
            try:
                report = future.result()
            except Exception as exc:  # never let one bad site kill the run
                report = {
                    "ok": False, "input_url": rec["url"], "outcome": "error",
                    "menu_url": None, "error": f"{type(exc).__name__}: {exc}",
                    "candidates": [],
                }
            report["id"] = rec["id"]
            results.append(report)
            if verbose:
                print(
                    f"  [{report['outcome']:>19}] {rec['url']}"
                    f" -> {report.get('menu_url') or '-'}",
                    file=sys.stderr,
                )
                if report.get("order_url"):
                    print(
                        f"{'':>24} order: {report['order_url']}"
                        f"  [{report.get('platform') or 'unknown'}"
                        f"/{report.get('price_confidence') or '?'}"
                        f"/{report.get('order_prefix_price_count')} prices]",
                        file=sys.stderr,
                    )
                if report.get("error"):
                    print(f"{'':>24} {report['error'][:180]}", file=sys.stderr)

    # Restore input order; as_completed returns them scrambled.
    order = {rec["url"]: i for i, rec in enumerate(records)}
    results.sort(key=lambda r: order.get(r["input_url"], 1 << 30))

    if out_path:
        Path(out_path).write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if verbose:
            print(f"Wrote {len(results)} result(s) to {out_path}", file=sys.stderr)

    if verbose:
        counts: dict[str, int] = {}
        for r in results:
            counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
        print("\nOutcomes:", file=sys.stderr)
        for outcome, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {outcome:>19}: {n}", file=sys.stderr)

    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve restaurant menu URLs from Places `websiteUri` values."
    )
    parser.add_argument("urls_file", help="file of site URLs (one per line, or JSON/JSONL)")
    parser.add_argument("-o", "--out", default="menu_urls.json", help="output JSON path")
    parser.add_argument("-w", "--workers", type=int, default=8, help="concurrent sites")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="per-request seconds")
    parser.add_argument("--no-sitemap", action="store_true", help="skip /sitemap.xml")
    parser.add_argument("--no-probe", action="store_true", help="skip path probing")
    parser.add_argument("--no-order", action="store_true",
                        help="skip order-URL resolution and platform fingerprinting")
    parser.add_argument("--ca-bundle", metavar="PEM",
                        help="CA bundle to trust (for TLS-inspecting proxies); "
                             "also settable via MENU_CA_BUNDLE")
    parser.add_argument("--insecure", action="store_true",
                        help="skip TLS verification (diagnostics only)")
    parser.add_argument("-q", "--quiet", action="store_true", help="suppress progress")
    args = parser.parse_args(argv)

    configure_tls(ca_bundle=args.ca_bundle, insecure=args.insecure)
    if args.insecure and not args.quiet:
        print("WARNING: TLS verification disabled (--insecure).", file=sys.stderr)

    run_batch(
        args.urls_file,
        out_path=args.out,
        workers=args.workers,
        timeout=args.timeout,
        use_sitemap=not args.no_sitemap,
        use_probe=not args.no_probe,
        use_order=not args.no_order,
        verbose=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
