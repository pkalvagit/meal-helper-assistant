import os
import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright
from markdownify import markdownify as md

# Keywords used to identify candidate "menu"/"order" links to follow.
MENU_LINK_KEYWORDS = (
    'menu', 'order', 'food', 'catering', 'delivery', 'takeout', 'to-go',
)

# Price pattern, e.g. "$8.99", "$8.99-$9.99", "$8.99 - 9.99"
PRICE_RE = re.compile(r'\$\d+(?:\.\d{1,2})?(?:\s*[-–]\s*\$?\d+(?:\.\d{1,2})?)?')

# Fallback "price-like" pattern for menu items that advertise nutrition
# stats instead of a dollar price (e.g. Chipotle's protein-focused menu):
# "37g Protein", "220 cal", "81g Protein | GLP-1 Friendly".
NUTRITION_RE = re.compile(r'\d+g\s*Protein|\d+\s*cal\b', re.IGNORECASE)

# CSS classes known to wrap individual menu item cards on specific sites.
# Checked first since they're far more reliable than the generic li/div
# price-sniffing heuristic below.
KNOWN_CARD_SELECTORS = ('.meal-card',)

# Load from environment variables with defaults
MAX_DEPTH = int(os.getenv("SCRAPE_MAX_DEPTH", "3"))
MAX_LINKS_PER_PAGE = int(os.getenv("SCRAPE_MAX_LINKS_PER_PAGE", "8"))
NAV_TIMEOUT_MS = int(os.getenv("SCRAPE_NAV_TIMEOUT_MS", "45000"))
RENDER_WAIT_MS = int(os.getenv("SCRAPE_RENDER_WAIT_MS", "8000"))


def _new_page(context):
    page = context.new_page()
    return page


def _dismiss_cookie_banner(page):
    for text in ('Accept All', 'Accept all', 'Reject Optional Cookies'):
        try:
            btn = page.get_by_role('button', name=text).first
            if btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(500)
                return
        except Exception:
            pass


# Keywords used to heuristically identify a "find a location" style modal
# and the address/zip input inside it.
LOCATION_DIALOG_KEYWORDS = (
    'find a', 'location', 'delivery', 'pickup', 'zip', 'address', 'store',
)
LOCATION_INPUT_KEYWORDS = (
    'city', 'zip', 'address', 'location', 'postal',
)


def _find_location_dialog(page):
    """
    Best-effort detection of a location-picker modal/dialog. Returns the
    dialog locator if one looks present, else None. This is heuristic and
    won't match every site's UI.
    """
    try:
        dialogs = page.get_by_role('dialog')
        count = dialogs.count()
    except Exception:
        return None

    for i in range(count):
        dialog = dialogs.nth(i)
        try:
            if not dialog.is_visible(timeout=500):
                continue
            label = (dialog.get_attribute('aria-label') or '').lower()
            text = dialog.inner_text(timeout=1000).lower()
            haystack = f'{label} {text[:300]}'
            if any(kw in haystack for kw in LOCATION_DIALOG_KEYWORDS):
                if dialog.locator('input').count() > 0:
                    return dialog
        except Exception:
            continue
    return None


def _apply_address(page, address):
    """
    Best-effort: if a location-picker dialog is present, type the given
    address/zip into its input, submit, and click the first resulting
    store/location option. Returns True if an address was applied.

    This is heuristic (site UIs vary) and fails silently (returns False)
    if no matching dialog/input/result is found, so callers can proceed
    with the page as-is.
    """
    if not address:
        return False

    dialog = _find_location_dialog(page)
    if dialog is None:
        return False

    # Prefer an input whose name/placeholder/aria-label hints at address/zip;
    # fall back to the first text input in the dialog.
    target_input = None
    inputs = dialog.locator('input')
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            hints = ' '.join(filter(None, [
                inp.get_attribute('name'),
                inp.get_attribute('placeholder'),
                inp.get_attribute('aria-label'),
                inp.get_attribute('id'),
            ])).lower()
        except Exception:
            hints = ''
        if any(kw in hints for kw in LOCATION_INPUT_KEYWORDS):
            target_input = inp
            break
    if target_input is None and inputs.count() > 0:
        target_input = inputs.first

    if target_input is None:
        return False

    try:
        target_input.click()
        target_input.type(address, delay=80)
        page.wait_for_timeout(1200)
        target_input.press('Enter')
        page.wait_for_timeout(2500)
    except Exception as e:
        return False

    # Click the first plausible, visible result card/row in the dialog.
    # Site markup varies (button/a/li, or a styled div acting as a card),
    # so try a broad set of candidates and pick the first one that's
    # actually visible and not the search input itself.
    try:
        candidates = dialog.locator(
            'li, [role="listitem"], [role="option"], [role="button"], '
            'button, a, .cmg-restaurant-address-item'
        )
        count = candidates.count()
        for i in range(count):
            candidate = candidates.nth(i)
            try:
                if candidate.locator('input').count() > 0:
                    continue  # skip the search box itself / its wrapper
                if not candidate.is_visible(timeout=500):
                    continue
                candidate.click(timeout=5000)
                page.wait_for_timeout(2500)
                return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def _get_main_container(page):
    menu = page.locator('main[aria-label="Order menu"]')
    if menu.count() > 0:
        return menu.first
    return page.locator('body')


def _collect_links_and_images(container):
    links = container.locator('a[href]').evaluate_all(
        'els => els.map(e => ({ text: e.innerText.trim(), href: e.href }))'
    )
    images = container.locator('img[src]').evaluate_all('els => els.map(e => e.src)')
    return links, images


def _is_menu_like_link(link, base_domain):
    href = link.get('href') or ''
    text = (link.get('text') or '').lower()
    if not href.startswith('http'):
        return False
    if urlparse(href).netloc != base_domain:
        return False
    haystack = f'{text} {href.lower()}'
    return any(kw in haystack for kw in MENU_LINK_KEYWORDS)


def _extract_menu_items(container):
    """
    Attempt to extract structured (name, price, description) menu items.
    Heuristic: look for elements that contain a price pattern, then use
    the nearest heading-like text as the item name and remaining text as
    description.

    <li> elements are preferred since they're typically leaf-level item
    cards; <div> is used as a fallback for prices not already covered by
    an <li> match, since divs can otherwise pick up nested parent
    containers that bleed multiple items together.
    """
    def _query(selector):
        try:
            return container.locator(selector).evaluate_all(
                '''
                els => els
                    .filter(e => /\\$\\d/.test(e.innerText || "") && e.innerText.length < 400)
                    .map(e => e.innerText.trim())
                '''
            )
        except Exception:
            return []

    li_candidates = _query('li')
    div_candidates = _query('div')

    def parse(text):
        price_match = PRICE_RE.search(text)
        if not price_match:
            return None
        price = price_match.group(0)

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        name = lines[0] if lines else ''
        # Skip garbage where the "name" line is itself just a price.
        if not name or PRICE_RE.fullmatch(name):
            return None

        desc_lines = [
            l for l in lines[1:]
            if l != price and not PRICE_RE.fullmatch(l.strip())
        ]
        description = ' '.join(desc_lines).strip()
        return {'name': name, 'price': price, 'description': description}

    best_by_key = {}

    # First pass: li elements (leaf-level item cards).
    for text in dict.fromkeys(li_candidates):  # dedupe while preserving order
        parsed = parse(text)
        if not parsed:
            continue
        key = (parsed['name'], parsed['price'])
        existing = best_by_key.get(key)
        if existing is None or len(parsed['description']) > len(existing['description']):
            best_by_key[key] = parsed

    li_prices = {v['price'] for v in best_by_key.values()}

    # Second pass: div elements, only for prices not already captured via li,
    # to avoid nested-container bleed duplicating/mangling existing items.
    for text in dict.fromkeys(div_candidates):
        parsed = parse(text)
        if not parsed or parsed['price'] in li_prices:
            continue
        key = (parsed['name'], parsed['price'])
        existing = best_by_key.get(key)
        if existing is None or len(parsed['description']) > len(existing['description']):
            best_by_key[key] = parsed

    return list(best_by_key.values())


def _items_to_markdown(items):
    if not items:
        return ''
    lines = ['| Item | Price | Description |', '|---|---|---|']
    for item in items:
        name = item['name'].replace('|', '/')
        price = item['price'].replace('|', '/')
        desc = item['description'].replace('|', '/') or '-'
        lines.append(f"| {name} | {price} | {desc} |")
    return '\n'.join(lines)


def scrape_page(page, url, address=None):
    """Navigate to url and return (container_html, links, images, extracted_items)."""
    page.goto(url, wait_until='domcontentloaded', timeout=NAV_TIMEOUT_MS)

    # Wait for initial JS to render
    page.wait_for_timeout(RENDER_WAIT_MS)
    _dismiss_cookie_banner(page)

    # Try waiting for menu-specific content to appear
    # This helps with SPAs that load content after initial render
    try:
        # Wait for common menu indicators (price or food-related text)
        page.wait_for_selector('text=/\\$\\d+/', timeout=3000)
    except Exception:
        # No prices found, but continue anyway (might be image-only menu)
        pass

    applied = _apply_address(page, address)
    if applied:
        pass  # Address was applied successfully
    elif address:
        # No location dialog detected on this page; nothing to apply.
        pass

    container = _get_main_container(page)
    html_string = container.inner_html()
    links, images = _collect_links_and_images(container)
    items = _extract_menu_items(container)

    return html_string, links, images, items


def scrape_and_find_menu(start_url, outputfile=None, max_depth=MAX_DEPTH,
                          max_links_per_page=MAX_LINKS_PER_PAGE,
                          extra_seed_urls=None, address=None):
    """
    Crawl starting from start_url, following menu/order-like links up to
    max_depth levels deep (breadth-first), extracting structured menu items
    (name, price, description) where possible. Writes a single consolidated
    markdown file with one section per visited page plus a combined Links
    section.

    extra_seed_urls: optional list of additional URLs to crawl at depth 0,
    alongside start_url. Useful for pages reachable only via client-side
    JS navigation (e.g. SPA category tiles with no real <a href>), which
    the link-based crawler cannot discover on its own.

    address: optional address/city/ZIP string. If a page shows a "find a
    location" style modal (heuristically detected), this address is typed
    into it and the first result is selected before scraping that page.
    Best-effort — site UIs vary, so this may not work on every site.
    """
    base_domain = urlparse(start_url).netloc

    visited = set()
    queue = [(start_url, 0)]
    for seed in (extra_seed_urls or []):
        queue.append((seed, 0))
    sections = []
    all_links_seen = {}   # href -> text
    all_images_seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            ignore_https_errors=True,  # corp proxy (Zscaler) presents its own CA
        )
        page = _new_page(context)

        while queue:
            url, depth = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                html_string, links, images, items = scrape_page(page, url, address=address)
            except Exception as e:
                continue

            for link in links:
                href = link.get('href')
                if href:
                    all_links_seen.setdefault(href, link.get('text') or href)
            for src in images:
                if src:
                    all_images_seen.add(src)

            markdown_string = md(html_string)
            item_table = _items_to_markdown(items)

            section = [f'## Page: {url}', '']
            if item_table:
                section.append('### Extracted Menu Items')
                section.append('')
                section.append(item_table)
                section.append('')
            section.append('### Raw Content')
            section.append('')
            section.append(markdown_string if markdown_string.strip() else '*(empty)*')
            sections.append('\n'.join(section))

            if depth + 1 < max_depth:
                menu_links = [l for l in links if _is_menu_like_link(l, base_domain)]
                added = 0
                for link in menu_links:
                    href = link['href']
                    if href not in visited and added < max_links_per_page:
                        queue.append((href, depth + 1))
                        added += 1

        browser.close()

    # Build final Links section (deduplicated)
    link_lines = []
    for href, text in all_links_seen.items():
        link_lines.append(f'- [{text}]({href})')
    for src in sorted(all_images_seen):
        link_lines.append(f'- {src}')

    final_md = '\n\n---\n\n'.join(sections)
    if link_lines:
        final_md += '\n\n## Links\n\n' + '\n'.join(link_lines) + '\n'

    # Don't print to console - only write to file
    if outputfile is None:
        outputfile = 'output.md'

    with open(outputfile, 'w') as f:
        f.write(final_md)


if __name__ == "__main__":
    data_map = {
        # "biryani_grill": {
        #     "url": 'https://cash.app/$biryanigrill/l/CALL_CAESDUw0WVRNVjBTNlJHNjY',
        # },
        # "chipottle": {
        #     "url": 'https://www.chipotle.com/#menu',
        #     # Reachable only via a client-side JS category tile (no real
        #     # <a href> on the page), so it can't be auto-discovered by the
        #     # link-based crawler. Seeded directly instead.
        #     # "extra_seed_urls": [
        #     #     'https://www.chipotle.com/order/build/high-protein-menu',
        #     # ],
        #     # Used to satisfy any "find a location" modal encountered.
        #     "address": '20147',
        # },
        "shakeshack":{
            "url": "https://www.shakeshack.com/",
            "address": "20147"
        }
    }
    for key, config in data_map.items():
        print(f"Scraping {key}...")
        scrape_and_find_menu(
            config["url"],
            f"menu_deep_{key}.md",
            extra_seed_urls=config.get("extra_seed_urls"),
            address=config.get("address"),
        )
