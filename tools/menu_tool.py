"""
Menu tool - handles caching and fetching menus.
Integrates with the extraction pipeline from test-menus.
"""
import json
import hashlib
import sys
import os
import re
import logging
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from io import BytesIO

from langchain.tools import tool
from langchain_core.messages import HumanMessage
from pypdf import PdfReader

# Add utils to path for pipeline imports
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))

# Import pipeline components
from menu_url_finder import resolve_menu_url
from scrape_and_find_menu import scrape_and_find_menu
from finalize_menu import extract_from_md_pattern

# Import LLM factory
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.llm_factory import get_llm_factory

# Cache directory
CACHE_DIR = Path(__file__).parent.parent / "cache" / "menus"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Scraped MD files directory
SCRAPED_DIR = Path(__file__).parent.parent / "cache" / "scraped_menus"
SCRAPED_DIR.mkdir(parents=True, exist_ok=True)

# Logger
logger = logging.getLogger("meal-helper")

# Stats logger (set by agent)
_stats_logger = None


def set_stats_logger(stats_logger):
    """Set the stats logger for menu extraction tracking."""
    global _stats_logger
    _stats_logger = stats_logger


def get_cache_key(restaurant_url: str) -> str:
    """Generate cache filename from URL."""
    return hashlib.md5(restaurant_url.encode()).hexdigest() + ".json"


def load_from_cache(restaurant_url: str) -> Optional[Dict[str, Any]]:
    """Load menu from cache if exists."""
    cache_file = CACHE_DIR / get_cache_key(restaurant_url)
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return None


def save_to_cache(restaurant_url: str, menu_data: Dict[str, Any]):
    """Save menu to cache."""
    cache_file = CACHE_DIR / get_cache_key(restaurant_url)
    with open(cache_file, "w") as f:
        json.dump(menu_data, f, indent=2)


def find_pdf_links_in_md(md_file_path: Path) -> list:
    """Find PDF links in markdown file."""
    try:
        with open(md_file_path, encoding="utf-8") as f:
            content = f.read()

        # Look for PDF links in markdown format: [text](url.pdf)
        import re
        pdf_links = re.findall(r'\[([^\]]+)\]\(([^\)]+\.pdf)\)', content, re.IGNORECASE)

        # Return list of (text, url) tuples
        return pdf_links
    except Exception as e:
        logger.error(f"Error finding PDF links: {e}")
        return []


def extract_pdf_text(pdf_url: str, timeout: int = 30) -> str:
    """
    Download PDF and extract text content.
    Works with any LLM by converting PDF to text first.
    """
    try:
        # Download PDF
        response = requests.get(pdf_url, timeout=timeout)
        response.raise_for_status()

        # Read PDF
        pdf_file = BytesIO(response.content)
        reader = PdfReader(pdf_file)

        # Extract text from all pages
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text.strip():
                text_parts.append(text)

        full_text = "\n\n".join(text_parts)
        return full_text

    except Exception as e:
        logger.error(f"PDF text extraction error: {e}")
        return ""


def extract_from_pdf_with_llm(pdf_url: str) -> Dict[str, Any]:
    """
    Extract menu items from PDF using configured LLM (OpenAI or Claude).

    Process:
    1. Download PDF and extract text
    2. Send text to configured LLM for menu extraction

    This works with both OpenAI and Claude since we convert PDF to text first.
    """
    try:
        # Step 1: Extract text from PDF
        pdf_text = extract_pdf_text(pdf_url)

        if not pdf_text or len(pdf_text) < 100:
            return {
                "success": False,
                "items": [],
                "error": "PDF appears empty or text extraction failed"
            }

        # Step 2: Use configured LLM to extract menu items
        factory = get_llm_factory()
        llm = factory.get_llm("primary")

        # Truncate if too long
        if len(pdf_text) > 50_000:
            pdf_text = pdf_text[:50_000] + "\n... (truncated)"

        prompt = f"""Extract all menu items from this restaurant menu PDF text.

Return a JSON array of items with this structure:
{{
  "items": [
    {{
      "name": "Dish name",
      "price": "$12.99",
      "description": "Description if available",
      "section": "Section name if available (e.g., Appetizers, Entrees)"
    }}
  ]
}}

Only include actual menu items with prices. Skip headers, navigation, and non-menu content.

Menu PDF text:
{pdf_text}"""

        # Call configured LLM
        response = llm.invoke([HumanMessage(content=prompt)])
        text = response.content

        # Parse JSON from response
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group(0))
            items = result.get("items", [])

            return {
                "success": len(items) > 0,
                "items": items,
                "error": None if len(items) > 0 else "No items found in PDF"
            }

        return {
            "success": False,
            "items": [],
            "error": "Failed to parse JSON response from LLM"
        }

    except Exception as e:
        logger.error(f"PDF extraction with LLM error: {e}")
        return {
            "success": False,
            "items": [],
            "error": str(e)
        }


def extract_with_llm(md_file_path: Path) -> Dict[str, Any]:
    """
    Extract menu items using configured LLM (OpenAI or Claude).
    Uses the LLM factory to respect user's configuration.
    """
    try:
        # Get configured LLM
        factory = get_llm_factory()
        llm = factory.get_llm("primary")

        # Read markdown file
        with open(md_file_path, encoding="utf-8") as f:
            md_content = f.read()

        # Truncate if too long
        if len(md_content) > 100_000:
            md_content = md_content[:100_000] + "\n... (truncated)"

        prompt = f"""Extract all menu items from this restaurant webpage content.

Return a JSON array of items with this structure:
{{
  "items": [
    {{
      "name": "Dish name",
      "price": "$12.99",
      "description": "Description if available",
      "section": "Section name if available (e.g., Appetizers, Entrees)"
    }}
  ]
}}

Only include actual menu items with prices. Skip navigation, headers, and non-menu content.

Content:
{md_content}"""

        # Call LLM (works with both OpenAI and Claude via LangChain)
        response = llm.invoke([HumanMessage(content=prompt)])
        text = response.content

        # Parse JSON from response
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group(0))
            items = result.get("items", [])

            return {
                "success": len(items) > 0,
                "items": items,
                "error": None if len(items) > 0 else "No items found"
            }

        return {
            "success": False,
            "items": [],
            "error": "Failed to parse JSON response"
        }

    except Exception as e:
        return {
            "success": False,
            "items": [],
            "error": str(e)
        }


@tool
def get_restaurant_menu(
    restaurant_name: str,
    restaurant_url: str,
    force_fetch: bool = False
) -> Dict[str, Any]:
    """
    Get restaurant menu - checks cache first, fetches if needed.

    IMPORTANT: restaurant_url must be the actual website URL from search results.
    After calling search_restaurants_nearby or search_restaurants_by_query,
    extract the "website" field from each result and pass it here.

    Example workflow:
    1. search_results = search_restaurants_nearby(...)
    2. For each result: get_restaurant_menu(result["name"], result["website"])

    Args:
        restaurant_name: Name of restaurant (from search results)
        restaurant_url: Restaurant website URL (MUST be from search results "website" field)
        force_fetch: Skip cache and re-fetch (default False)

    Returns:
        {
            "restaurant": str,
            "url": str,
            "cached": bool,
            "items": [
                {"name": str, "price": str, "description": str, "section": str}
            ],
            "error": str (if failed)
        }
    """
    # Validate URL
    if not restaurant_url or restaurant_url.strip() == "":
        error_msg = "No website URL provided. Cannot fetch menu without a valid URL. This restaurant may not have a website in Google Places data."

        # Log stats
        if _stats_logger:
            _stats_logger.log_menu_extraction(
                restaurant_name=restaurant_name,
                restaurant_url=restaurant_url,
                menu_url_found=False,
                error=error_msg
            )

        return {
            "restaurant": restaurant_name,
            "url": restaurant_url,
            "error": error_msg
        }

    # Check cache
    if not force_fetch:
        cached = load_from_cache(restaurant_url)
        if cached:
            cached["cached"] = True

            # Log stats for cached result
            if _stats_logger:
                _stats_logger.log_menu_extraction(
                    restaurant_name=restaurant_name,
                    restaurant_url=restaurant_url,
                    menu_url_found=True,
                    menu_url=cached.get("menu_url"),
                    menu_url_type=cached.get("menu_url_kind"),
                    scraping_success=True,
                    md_file=cached.get("md_file"),
                    extraction_method="cached",
                    items_found=len(cached.get("items", [])),
                    cached=True
                )

            return cached

    # Need to fetch - use YOUR FULL PIPELINE
    try:
        logger.info(f"[Pipeline] Step 1/3: Finding menu URL for {restaurant_name}")

        # STEP 1: Find menu URL using menu_url_finder
        menu_result = resolve_menu_url(restaurant_url, timeout=15)

        if not menu_result or not menu_result.get("ok"):
            error_msg = menu_result.get("error", "Could not find menu URL")

            # Log stats
            if _stats_logger:
                _stats_logger.log_menu_extraction(
                    restaurant_name=restaurant_name,
                    restaurant_url=restaurant_url,
                    menu_url_found=False,
                    error=error_msg
                )

            return {
                "restaurant": restaurant_name,
                "url": restaurant_url,
                "cached": False,
                "items": [],
                "error": error_msg
            }

        menu_url = menu_result.get("menu_url")
        menu_url_kind = menu_result.get("menu_url_kind", "unknown")

        if not menu_url:
            error_msg = "No menu URL found on website"

            # Log stats
            if _stats_logger:
                _stats_logger.log_menu_extraction(
                    restaurant_name=restaurant_name,
                    restaurant_url=restaurant_url,
                    menu_url_found=False,
                    error=error_msg
                )

            return {
                "restaurant": restaurant_name,
                "url": restaurant_url,
                "cached": False,
                "items": [],
                "error": error_msg
            }

        logger.info(f"[Pipeline] Menu URL found: {menu_url} (type: {menu_url_kind})")

        # STEP 2: Scrape and create MD file
        # Create safe filename from restaurant name
        import re
        safe_name = re.sub(r'[^a-z0-9]+', '_', restaurant_name.lower()).strip('_')
        md_file = SCRAPED_DIR / f"{safe_name}.md"

        logger.info(f"[Pipeline] Scraping menu page to {md_file}")

        try:
            scrape_and_find_menu(
                start_url=menu_url,
                outputfile=str(md_file),
                max_depth=2,  # Allow one level of link following
                max_links_per_page=3,  # Follow up to 3 menu-like links
                address=None
            )
            logger.info(f"[Pipeline] Scraping completed successfully")
        except Exception as scrape_err:
            logger.error(f"[Pipeline] Scraping failed: {scrape_err}")
            # Try without playwright if it fails
            pass

        # STEP 3: Extract from MD file
        logger.info(f"[Pipeline] Extracting items from MD file")

        items = []
        extraction_method = None
        scraping_success = md_file.exists()

        # Check if MD file is empty or too small
        if md_file.exists():
            md_size = md_file.stat().st_size
            if md_size < 100:  # Less than 100 bytes is likely empty
                logger.warning(f"[Pipeline] MD file too small ({md_size} bytes) - empty scrape result")
                scraping_success = False

        # Try pattern extraction first (FREE)
        if md_file.exists() and scraping_success:
            pattern_result = extract_from_md_pattern(md_file)

            if pattern_result.success and len(pattern_result.items or []) >= 3:
                logger.info(f"[Pipeline] Pattern extraction: {len(pattern_result.items)} items (FREE)")
                items = pattern_result.items
                extraction_method = "pattern"
            else:
                # Fall back to LLM extraction using configured LLM (OpenAI or Claude)
                logger.info(f"[Pipeline] Pattern extraction insufficient, using LLM")
                llm_result = extract_with_llm(md_file)

                if llm_result["success"]:
                    items = llm_result["items"] or []
                    logger.info(f"[Pipeline] LLM extraction: {len(items)} items")
                    extraction_method = "llm_md"
                else:
                    error_msg = llm_result['error'] or 'No items found'
                    logger.error(f"[Pipeline] LLM extraction failed: {error_msg}")

                    # Check if MD contains PDF links - if so, try PDF extraction
                    pdf_links = find_pdf_links_in_md(md_file)
                    if pdf_links:
                        logger.info(f"[Pipeline] Found PDF links, attempting PDF extraction with configured LLM")

                        for link_text, pdf_path in pdf_links:
                            # Convert relative URL to absolute
                            from urllib.parse import urljoin
                            pdf_url = urljoin(menu_url, pdf_path)

                            logger.info(f"[Pipeline] PDF extraction from: {pdf_url}")

                            try:
                                # Extract PDF using configured LLM (works with OpenAI or Claude)
                                pdf_result = extract_from_pdf_with_llm(pdf_url)

                                if pdf_result["success"] and len(pdf_result["items"] or []) > 0:
                                    items = pdf_result["items"]
                                    logger.info(f"[Pipeline] PDF extraction: {len(items)} items")
                                    extraction_method = "llm_pdf"
                                    break  # Success, stop trying other PDFs
                                else:
                                    logger.warning(f"[Pipeline] PDF extraction failed: {pdf_result['error']}")
                            except Exception as pdf_err:
                                logger.error(f"[Pipeline] PDF extraction error: {pdf_err}")

                    if not items:
                        extraction_method = "llm_md_failed"
        elif not scraping_success:
            logger.warning(f"[Pipeline] Skipping extraction - empty scrape (likely JS-heavy site)")
            extraction_method = "scraping_failed_empty"

        menu_data = {
            "restaurant": restaurant_name,
            "url": restaurant_url,
            "menu_url": menu_url,
            "menu_url_kind": menu_url_kind,
            "md_file": str(md_file) if md_file.exists() else None,
            "cached": False,
            "items": items,
            "item_count": len(items),
            "extraction_method": extraction_method  # Track how we tried to extract
        }

        # Always cache - even empty results serve as failure records
        # This prevents retrying failed extractions repeatedly
        save_to_cache(restaurant_url, menu_data)

        if not items:
            logger.warning(f"[Pipeline] Cached empty result for {restaurant_name} - serves as failure record")

        # Log stats
        if _stats_logger:
            _stats_logger.log_menu_extraction(
                restaurant_name=restaurant_name,
                restaurant_url=restaurant_url,
                menu_url_found=True,
                menu_url=menu_url,
                menu_url_type=menu_url_kind,
                scraping_success=scraping_success,
                md_file=str(md_file) if md_file.exists() else None,
                extraction_method=extraction_method,
                items_found=len(items),
                cached=False
            )

        return menu_data

    except Exception as e:
        import traceback
        traceback.print_exc()

        # Log stats for exception
        if _stats_logger:
            _stats_logger.log_menu_extraction(
                restaurant_name=restaurant_name,
                restaurant_url=restaurant_url,
                menu_url_found=False,
                error=f"Exception: {str(e)}"
            )

        return {
            "restaurant": restaurant_name,
            "url": restaurant_url,
            "error": str(e),
            "items": []
        }


@tool
def check_menu_cache_status(restaurant_urls: List[str]) -> Dict[str, bool]:
    """
    Check which restaurant menus are cached.

    Args:
        restaurant_urls: List of restaurant URLs

    Returns:
        {url: is_cached} mapping
    """
    status = {}
    for url in restaurant_urls:
        cache_file = CACHE_DIR / get_cache_key(url)
        status[url] = cache_file.exists()
    return status


@tool
def extract_menu_from_text(
    menu_text: str,
    restaurant_name: str
) -> List[Dict[str, Any]]:
    """
    Extract structured menu items from raw text using LLM.
    Useful when menu is in webpage text but not cached.

    Args:
        menu_text: Raw menu text (markdown, HTML, or plain text)
        restaurant_name: Restaurant name for context

    Returns:
        List of menu items with name, price, description
    """
    try:
        client = anthropic.Anthropic()

        prompt = f"""Extract menu items from this text for {restaurant_name}.

Return JSON array:
[
  {{
    "name": "Dish name",
    "price": "$12.99",
    "description": "Description",
    "section": "Section (e.g., Appetizers)"
  }}
]

Menu text:
{menu_text[:10000]}"""  # Limit to 10K chars

        response = client.messages.create(
            model="claude-haiku-4-5",  # Cheap model
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = next((b.text for b in response.content if b.type == "text"), "")

        # Parse JSON
        import re
        json_match = re.search(r'\[[\s\S]*\]', text)
        if json_match:
            items = json.loads(json_match.group(0))
            return items

        return []

    except Exception as e:
        return [{"error": str(e)}]
