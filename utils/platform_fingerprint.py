"""Identify the ordering platform behind a restaurant's order URL.

Why this exists: a marketing menu page lists dishes, an *ordering* page lists
dishes with prices, because that's the page that has to charge money. Matching
hostnames against a list of platform domains misses the common case, though --
platforms white-label onto the restaurant's own domain. `order.mayurius.com`
carries no Toast string anywhere in its URL, but sets a `toast-sites-experiment-id`
cookie and ships the whole priced menu as embedded JSON.

So fingerprinting looks at the *response*, not the URL: final hostname after
redirects, then cookies, then headers, then a body prefix. Cookies are the
strongest white-label signal -- they survive custom domains and CDN fronting.

Not every platform's prices mean the same thing, which is what `price_confidence`
records. A POS (Toast, Square, Clover) quotes what the register charges. A
delivery marketplace (DoorDash, Uber Eats) quotes those prices inflated 15-30%
to fund the courier. Storing both in one column silently corrupts the good rows.

Only Toast is marked `verified=True` -- its signals were confirmed against a live
site. The rest are seeded from platform conventions and need confirming; run
`python platform_fingerprint.py probe <url>...` against a known site to see what
signals actually appear, then promote the entry.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin

import requests

# Fingerprinting only needs a prefix -- a Toast menu page is >1 MB and the
# platform markers appear early. Extraction re-fetches in full when it needs
# the body.
BODY_SNIFF_BYTES = 512 * 1024

# Prices show up two ways: rendered text ("$10.99") and embedded JSON
# ("price":10.99), which is how every SPA ordering page ships its menu.
#
# Cents stay optional, because plenty of menus really do print `Branzino $34`.
# The false positives that broke this aren't about cents, they're about shape:
#
#   \"__html\":\"$14\"   React RSC flight data -- every Next.js app-router page
#   $250k - $500k        franchise-investment copy
#   $L21, $undefined     more RSC reference markers
#
# All 14 "prices" found on biryanigrill.com/order were one of those, on a page
# with no menu prices at all. So the lookarounds require a price to sit in prose
# (not wrapped in quotes) and to end at a non-word character (killing the `k`/`M`
# magnitude suffixes). `$L21` never matches -- `$` must be followed by a digit.
# The leading currency-code form (`US$6.18`) needs its own branch: the
# lookbehind below would otherwise reject the `S`. Aggregator templates localise
# this way, which is itself a hint the number was converted rather than printed.
PRICE_TOKEN = re.compile(
    r"\b(?:US|CA|AU|NZ|HK|SG|R)\$\s?\d{1,4}(?:[.,]\d{2})?(?![\w])"
    r"|(?<![\w\"\\])[$£€]\s?\d{1,4}(?:[.,]\d{2})?(?![\w.,]\d)(?![\w])"
    r"|\b\d{1,4}[.,]\d{2}\s?(?:USD|EUR|GBP)\b"
    r"|\"(?:price|amount|basePrice|unitPrice)\\?\":\s?\d+(?:\.\d+)?",
    re.I,
)

# Prices only: what the platform's numbers actually mean.
CANONICAL = "canonical"    # register prices, first-party
MARKED_UP = "marked_up"    # marketplace prices, inflated for delivery
NO_PRICES = "none"         # reservations/CRM -- no menu prices at all


@dataclass(frozen=True)
class Platform:
    key: str
    label: str
    hosts: tuple[str, ...] = ()
    cookies: tuple[str, ...] = ()
    # (header-name, substring-of-value); matched case-insensitively.
    headers: tuple[tuple[str, str], ...] = ()
    body: tuple[str, ...] = ()
    price_confidence: str = CANONICAL
    # ordering | menu_host | marketplace | reservation
    kind: str = "ordering"
    verified: bool = False
    notes: str = ""


PLATFORMS: tuple[Platform, ...] = (
    Platform(
        key="toast", label="Toast",
        hosts=("toasttab.com", "toastweb.com"),
        cookies=("toast-sites-experiment-id",),
        body=('"restaurantGuid"', "__TOAST", "toast-sites"),
        verified=True,
        notes="Confirmed on order.mayurius.com: cookie set on a custom domain, "
              "full priced menu embedded as JSON with \"price\": floats.",
    ),
    Platform(
        key="square", label="Square Online",
        hosts=("squareup.com", "square.site"),
        body=("square-marketplace", "data-square-", "sq-payment"),
    ),
    Platform(
        key="chownow", label="ChowNow",
        hosts=("chownow.com",),
        body=("chownow", "cn-order"),
    ),
    Platform(
        key="popmenu", label="Popmenu",
        hosts=("popmenu.com",),
        body=("popmenu", "pm-menu-item"),
    ),
    Platform(
        key="olo", label="Olo",
        hosts=("olo.com", "ordering.app"),
        body=("olo-", "data-olo"),
    ),
    Platform(
        key="clover", label="Clover",
        hosts=("clover.com",),
        body=("clover-", "cloverapp"),
    ),
    Platform(
        key="menufy", label="Menufy",
        hosts=("menufy.com",),
    ),
    Platform(
        key="slice", label="Slice",
        hosts=("slicelife.com",),
    ),
    Platform(
        key="spoton", label="SpotOn",
        hosts=("spoton.com", "spotonorder.com"),
    ),
    Platform(
        key="owner", label="Owner.com",
        hosts=("owner.com",),
    ),
    Platform(
        key="bentobox", label="BentoBox",
        hosts=("getbento.com", "bentobox.com"),
        kind="menu_host",
        notes="Site builder. Menus are usually priced but sometimes marketing-only.",
    ),
    # Marketplaces: real prices, systematically inflated. Usable, but never
    # let these outrank a POS for the same restaurant.
    Platform(
        key="doordash", label="DoorDash",
        hosts=("doordash.com",), price_confidence=MARKED_UP, kind="marketplace",
    ),
    Platform(
        key="ubereats", label="Uber Eats",
        hosts=("ubereats.com",), price_confidence=MARKED_UP, kind="marketplace",
    ),
    Platform(
        key="grubhub", label="Grubhub",
        hosts=("grubhub.com", "seamless.com"),
        price_confidence=MARKED_UP, kind="marketplace",
    ),
    # Reservation widgets are NOT menu sources. They land here so the resolver
    # can positively reject them rather than scoring them as a menu link.
    Platform(
        key="opentable", label="OpenTable",
        hosts=("opentable.com",), price_confidence=NO_PRICES, kind="reservation",
    ),
    Platform(
        key="resy", label="Resy",
        hosts=("resy.com",), price_confidence=NO_PRICES, kind="reservation",
    ),
)

# Registry lookup by key, for callers that want a platform's metadata directly.
BY_KEY = {p.key: p for p in PLATFORMS}

# Signal strength. A hostname match is unambiguous; a cookie match is nearly as
# good and is the only thing that catches white-labelled deployments; body
# markers are weakest because vendor names leak into unrelated CSS classes.
SIGNAL_WEIGHT = {"host": 100, "cookie": 90, "header": 70, "body": 60}

ORDER_WORD = re.compile(
    r"\border\s*(?:online|now|ahead|here|pickup|takeout|food|from|at|@)\b"
    r"|\bstart\s+(?:your\s+)?order\b"
    r"|\border\s*&\s*pay\b"
    r"|\bonline\s+ordering\b",
    re.I,
)

# A bare "Order" button. Too loose to match anywhere in a page -- "in order to",
# "money order", "reorder" would all hit -- so it is only applied to an anchor
# whose *entire* text is short, which is what a call-to-action button looks like.
# Biryani Grill labels its Cash App handoff "Order" and "Order @ Navarasa";
# without this the link is missed, and with it the restaurant is correctly
# recorded as ordering by Cash App only.
ORDER_BUTTON = re.compile(r"^\W*order\b", re.I)
ORDER_BUTTON_MAX_WORDS = 4

# Subdomains worth a blind GET when the HTML yielded no order link at all.
ORDER_SUBDOMAINS = ("order", "ordering", "menu", "store")

# "Order Now" buttons that hand off to a human instead of a cart. These are real
# ordering channels, so they aren't noise -- but they will never carry a priced
# menu, and fetching them wastes a request and can resolve to a login wall.
# Recorded as `offline_order_channels` so a restaurant that only takes orders by
# message can be marked terminal rather than retried forever.
OFFLINE_ORDER_HOSTS: tuple[tuple[str, str], ...] = (
    ("api.whatsapp.com", "whatsapp"), ("wa.me", "whatsapp"),
    ("chat.whatsapp.com", "whatsapp"),
    ("m.me", "messenger"), ("messenger.com", "messenger"),
    ("facebook.com", "facebook"), ("instagram.com", "instagram"),
    ("cash.app", "cash_app"), ("venmo.com", "venmo"), ("paypal.me", "paypal"),
    ("maps.app.goo.gl", "google_maps"), ("goo.gl", "google_maps"),
    ("forms.gle", "web_form"), ("docs.google.com", "web_form"),
)

# `urlTemplate` values are RFC 6570 templates: strip the variable expansions.
URI_TEMPLATE_VAR = re.compile(r"\{[^}]*\}")


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def clean_uri_template(value: str) -> str:
    """`https://x.com/order{?utm_source}` -> `https://x.com/order`."""
    return URI_TEMPLATE_VAR.sub("", value or "").strip()


# --------------------------------------------------------------------------- #
# Fingerprinting one response
# --------------------------------------------------------------------------- #

def fingerprint_response(resp: requests.Response, body: str = "") -> dict:
    """Identify the platform serving `resp`.

    Checks hostname, then cookies, then headers, then `body`. Returns the
    highest-confidence match plus every signal that fired, so a wrong call can
    be diagnosed from the output alone rather than by re-running.
    """
    host = _host(resp.url)
    cookie_names = {c.lower() for c in resp.cookies.keys()}
    # Redirect hops set cookies too, and requests only exposes the final jar
    # reliably via history; fold in Set-Cookie from every hop.
    for hop in list(resp.history) + [resp]:
        for raw in hop.raw.headers.getlist("Set-Cookie") if hasattr(hop, "raw") else []:
            cookie_names.add(raw.split("=", 1)[0].strip().lower())

    header_blob = {k.lower(): v.lower() for k, v in resp.headers.items()}
    body_low = (body or "").lower()

    matches: list[dict] = []
    for p in PLATFORMS:
        signals: list[str] = []

        if any(host == h or host.endswith("." + h) for h in p.hosts):
            signals.append("host")
        if any(c.lower() in cookie_names for c in p.cookies):
            signals.append("cookie")
        if any(sub.lower() in header_blob.get(name.lower(), "")
               for name, sub in p.headers):
            signals.append("header")
        if body_low and any(m.lower() in body_low for m in p.body):
            signals.append("body")

        if signals:
            matches.append({
                "platform": p.key,
                "label": p.label,
                "kind": p.kind,
                "price_confidence": p.price_confidence,
                "confidence": max(SIGNAL_WEIGHT[s] for s in signals),
                "signals": signals,
                "verified_registry_entry": p.verified,
            })

    if not matches:
        return {"platform": None, "confidence": 0, "signals": [],
                "kind": None, "price_confidence": None}

    matches.sort(key=lambda m: -m["confidence"])
    best = dict(matches[0])
    if len(matches) > 1:
        best["also_matched"] = [m["platform"] for m in matches[1:]]
    return best


def fetch_and_fingerprint(
    url: str,
    session: requests.Session,
    timeout: float = 12.0,
    sniff_body: bool = True,
) -> dict:
    """GET `url`, follow redirects, fingerprint whatever answers."""
    out: dict = {
        "url": url, "final_url": None, "status": None,
        "platform": None, "confidence": 0, "signals": [],
        "kind": None, "price_confidence": None,
        "prefix_price_count": None, "body_truncated": False, "error": None,
    }
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True,
                           stream=sniff_body)
    except requests.RequestException as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    body = ""
    try:
        out["final_url"] = resp.url
        out["status"] = resp.status_code
        if sniff_body and "html" in resp.headers.get("Content-Type", "html").lower():
            raw = resp.raw.read(BODY_SNIFF_BYTES, decode_content=True) or b""
            body = raw.decode(resp.encoding or "utf-8", errors="replace")
        out.update(fingerprint_response(resp, body))

        # Price-shaped tokens in the prefix: the cheapest available hint at
        # "would extraction find anything here". Deliberately reported as
        # unknown rather than zero when the body was cut off -- Toast keeps its
        # menu payload past the 512 KB mark, so a truncated 0 means nothing and
        # would otherwise look like a page with no prices.
        n = len(set(PRICE_TOKEN.findall(body)))
        out["body_truncated"] = len(body.encode("utf-8", "replace")) >= BODY_SNIFF_BYTES
        out["prefix_price_count"] = n if (n or not out["body_truncated"]) else None
    finally:
        resp.close()
    return out


# --------------------------------------------------------------------------- #
# Resolving an order URL for one site
# --------------------------------------------------------------------------- #

def order_candidates_from_jsonld(data) -> list[str]:
    """Pull OrderAction entry points out of a parsed JSON-LD blob.

    schema.org puts the order link at
    `potentialAction.OrderAction.target.EntryPoint.urlTemplate`, right beside
    the `hasMenu` that the menu finder already reads. Biryani Grill declares
    both: `hasMenu` -> a priceless marketing anchor, OrderAction -> /order.
    """
    found: list[str] = []
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
            continue
        if not isinstance(node, dict):
            continue
        stack.extend(v for v in node.values() if isinstance(v, (dict, list)))

        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if not any(t in ("OrderAction", "FoodEstablishmentReservation") for t in types):
            continue

        target = node.get("target")
        for t in (target if isinstance(target, list) else [target]):
            if isinstance(t, str):
                found.append(clean_uri_template(t))
            elif isinstance(t, dict):
                for key in ("urlTemplate", "url"):
                    if isinstance(t.get(key), str):
                        found.append(clean_uri_template(t[key]))
    return [u for u in found if u]


def order_candidates_from_anchors(soup, base: str) -> list[str]:
    """Anchors whose text or href says 'order online' / 'start order'."""
    found: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        text = a.get_text(" ", strip=True)
        if ORDER_WORD.search(text) or ORDER_WORD.search(href):
            found.append(urljoin(base, href))
        elif _is_order_button(text):
            found.append(urljoin(base, href))
    return found


# Account links, not ordering links -- these lead to a login wall.
_ORDER_BUTTON_STOP = re.compile(r"\b(?:history|status|tracking|again|details)\b", re.I)


def _is_order_button(text: str) -> bool:
    """True for short call-to-action anchors like 'Order' or 'Order @ Navarasa'."""
    words = text.split()
    if not words or len(words) > ORDER_BUTTON_MAX_WORDS:
        return False
    return bool(ORDER_BUTTON.match(text)) and not _ORDER_BUTTON_STOP.search(text)


def subdomain_candidates(site_url: str) -> list[str]:
    """`example.com` -> `https://order.example.com/`, etc.

    Only worth spending requests on when the HTML gave us nothing: plenty of
    restaurants link their ordering page from a JS-rendered nav we never see.
    """
    host = _host(site_url)
    if not host:
        return []
    root = host[4:] if host.startswith("www.") else host
    # Already on a subdomain -- don't stack another.
    if root.count(".") > 1:
        return []
    return [f"https://{sub}.{root}/" for sub in ORDER_SUBDOMAINS]


def _rank(result: dict) -> tuple:
    """Best order URL first.

    Canonical POS beats a marked-up marketplace even when the marketplace
    fingerprint is more confident, because the price *meaning* matters more
    than the certainty of the platform ID. Reservation widgets sort last.
    """
    rank_by_conf = {CANONICAL: 3, MARKED_UP: 2, None: 1, NO_PRICES: 0}
    return (
        rank_by_conf.get(result.get("price_confidence"), 1),
        result.get("confidence", 0),
        result.get("prefix_price_count") or 0,
    )


def resolve_order_url(
    site_url: str,
    soup=None,
    jsonld_blobs: list | None = None,
    session: requests.Session | None = None,
    timeout: float = 12.0,
    max_fetches: int = 4,
    probe_subdomains: bool = True,
    home_response: requests.Response | None = None,
    home_body: str = "",
) -> dict:
    """Find the best ordering URL for one restaurant and identify its platform.

    `soup` and `jsonld_blobs` come from the homepage the menu finder already
    fetched, so tiers 0 and 1 cost zero extra requests. Only tier 2 -- resolving
    and fingerprinting -- spends any, capped at `max_fetches`.
    """
    session = session or requests.Session()
    report: dict = {
        "order_url": None, "order_url_kind": None,
        "platform": None, "platform_confidence": 0, "platform_signals": [],
        "price_confidence": None, "order_candidates": [],
        "offline_order_channels": [], "checked": [],
    }

    tiered: list[tuple[str, str]] = []
    seen: set[str] = set()
    offline: list[dict] = []
    prefetched: list[dict] = []

    # Tier 0a -- `websiteUri` sometimes points straight at the ordering platform.
    # mayurius.com/order redirects to a Toast page, so there is no "order link"
    # to find on it: it *is* the order page. Fingerprint the response the finder
    # already has rather than hunting for a link that cannot exist.
    if home_response is not None:
        fp = fingerprint_response(home_response, home_body)
        if fp.get("platform") and fp.get("price_confidence") != NO_PRICES:
            n = len(set(PRICE_TOKEN.findall(home_body or "")))
            prefetched.append({
                **fp,
                "url": home_response.url, "final_url": home_response.url,
                "status": home_response.status_code, "kind": "site_is_order_page",
                "prefix_price_count": n, "error": None,
            })
            seen.add(home_response.url)

    def push(url: str, kind: str) -> None:
        url = (url or "").strip()
        if not url or url.startswith("#"):
            return
        if url in seen:
            return
        seen.add(url)

        host = _host(url)
        for pattern, channel in OFFLINE_ORDER_HOSTS:
            if host == pattern or host.endswith("." + pattern):
                offline.append({"channel": channel, "url": url, "kind": kind})
                return

        tiered.append((url, kind))

    # Tier 0 -- schema.org OrderAction. Free: the bytes are already parsed.
    for blob in (jsonld_blobs or []):
        for url in order_candidates_from_jsonld(blob):
            push(urljoin(site_url, url), "jsonld_order")

    # Tier 1 -- "Order Online" anchors. Also free.
    if soup is not None:
        for url in order_candidates_from_anchors(soup, site_url):
            push(url, "anchor_order")

    # Tier 2 -- blind subdomain guesses, only if the page told us nothing.
    if probe_subdomains and not tiered and not prefetched:
        for url in subdomain_candidates(site_url):
            push(url, "subdomain_probe")

    # Tier 2b -- nothing fetchable, but an "Order Now" button did point
    # somewhere. Try subdomains before giving up.
    if probe_subdomains and not tiered and not prefetched and offline:
        for url in subdomain_candidates(site_url):
            push(url, "subdomain_probe")

    report["order_candidates"] = (
        [{"url": p["url"], "kind": p["kind"]} for p in prefetched]
        + [{"url": u, "kind": k} for u, k in tiered]
    )
    report["offline_order_channels"] = offline
    if not tiered and not prefetched:
        return report

    results: list[dict] = list(prefetched)
    for url, kind in tiered[:max_fetches]:
        res = fetch_and_fingerprint(url, session, timeout=timeout)
        res["kind"] = kind
        results.append(res)
        report["checked"].append({
            "url": url, "kind": kind, "status": res["status"],
            "platform": res["platform"], "prefix_price_count": res["prefix_price_count"],
            "error": res["error"],
        })

    usable = [r for r in results
              if r["status"] and r["status"] < 400
              and r.get("price_confidence") != NO_PRICES]
    if not usable:
        return report

    best = max(usable, key=_rank)
    report.update({
        "order_url": best.get("final_url") or best["url"],
        "order_url_kind": best["kind"],
        "platform": best.get("platform"),
        "platform_confidence": best.get("confidence", 0),
        "platform_signals": best.get("signals", []),
        "price_confidence": best.get("price_confidence"),
        "order_prefix_price_count": best.get("prefix_price_count"),
        "platform_entry_verified": best.get("verified_registry_entry", False),
    })
    return report


# --------------------------------------------------------------------------- #
# CLI -- registry growth tool
# --------------------------------------------------------------------------- #

def _cli_session(ca_bundle: str | None, insecure: bool) -> requests.Session:
    """Session shaped like the finder's, including its TLS-proxy handling.

    Imported lazily: menu_url_finder imports this module, so a module-level
    import here would be circular.
    """
    from menu_url_finder import build_session, configure_tls, HEADERS

    configure_tls(ca_bundle=ca_bundle, insecure=insecure)
    session = build_session()
    session.headers.update(HEADERS)
    return session


def cmd_probe(urls: list[str], timeout: float, session: requests.Session) -> int:
    """Dump raw signals for a URL so registry entries can be verified.

    Point this at a site you know uses a given platform, then copy the cookie
    and header names it prints into that platform's registry entry. This is how
    unverified entries get promoted -- the alternative is trusting guesses.
    """
    for url in urls:
        print(f"\n=== {url}")
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
        except requests.RequestException as exc:
            print(f"  ERROR {type(exc).__name__}: {exc}")
            continue
        raw = resp.raw.read(BODY_SNIFF_BYTES, decode_content=True) or b""
        body = raw.decode(resp.encoding or "utf-8", errors="replace")
        resp.close()

        print(f"  final:   {resp.url}")
        print(f"  status:  {resp.status_code}")
        print(f"  hops:    {[h.status_code for h in resp.history] or '-'}")
        print(f"  cookies: {sorted(resp.cookies.keys()) or '-'}")
        interesting = {k: v for k, v in resp.headers.items()
                       if k.lower() in ("server", "x-powered-by", "via",
                                        "x-served-by", "content-type")}
        print(f"  headers: {interesting}")
        prices = sorted(set(PRICE_TOKEN.findall(body)))
        cut = " (prefix only -- may appear later)" if len(raw) >= BODY_SNIFF_BYTES else ""
        print(f"  prices:  {len(prices)} distinct{cut} {prices[:6]}")
        print(f"  verdict: {json.dumps(fingerprint_response(resp, body))}")
    return 0


def cmd_resolve(urls: list[str], timeout: float, session: requests.Session) -> int:
    """Run the full tier-0/1/2 resolver against bare site URLs."""
    from bs4 import BeautifulSoup

    out = []
    for url in urls:
        soup, blobs, resp, body = None, [], None, ""
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            body = resp.text
            soup = BeautifulSoup(body, "html.parser")
            url = resp.url
            for tag in soup.find_all("script", type="application/ld+json"):
                try:
                    blobs.append(json.loads(tag.string or tag.get_text() or ""))
                except (json.JSONDecodeError, ValueError):
                    continue
        except requests.RequestException as exc:
            print(f"{url}: fetch failed: {exc}", file=sys.stderr)

        # Pass the page we just fetched so tier 0a can fire: when websiteUri
        # already *is* the ordering page there is no order link to find on it.
        rep = resolve_order_url(url, soup=soup, jsonld_blobs=blobs,
                                session=session, timeout=timeout,
                                home_response=resp, home_body=body)
        rep["site_url"] = url
        out.append(rep)
        print(f"{url}\n  -> {rep['order_url'] or '-'}"
              f"  [{rep['platform'] or 'unknown'}"
              f" / {rep['price_confidence'] or '?'}"
              f" / {rep['order_url_kind'] or '-'}]", file=sys.stderr)
    print(json.dumps(out, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, help_text in (
        ("probe", "dump raw platform signals for a URL"),
        ("resolve", "find + fingerprint order URLs for sites"),
    ):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("urls", nargs="+")
        s.add_argument("-t", "--timeout", type=float, default=15.0)
        s.add_argument("--ca-bundle", metavar="PEM",
                       help="CA bundle to trust (TLS-inspecting proxies); "
                            "also settable via MENU_CA_BUNDLE")
        s.add_argument("--insecure", action="store_true",
                       help="skip TLS verification (diagnostics only)")

    args = p.parse_args(argv)
    session = _cli_session(args.ca_bundle, args.insecure)
    if args.cmd == "probe":
        return cmd_probe(args.urls, args.timeout, session)
    return cmd_resolve(args.urls, args.timeout, session)


if __name__ == "__main__":
    raise SystemExit(main())
