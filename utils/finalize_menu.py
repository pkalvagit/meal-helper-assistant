"""
Token-optimized menu extraction pipeline with image fallback.

Flow:
1. Try pattern-based extraction from MD (FREE)
2. Fall back to LLM on MD content (CHEAPER)
3. Fall back to LLM on PDF (EXPENSIVE)
4. Fall back to LLM on menu images (LAST RESORT)

Usage:
    python finalize_menu.py menu_urls.json --md-dir scraped_menus --output final_menus.json
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import anthropic
import requests
from PIL import Image
from io import BytesIO

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DEFAULT_MODEL = "claude-opus-5"
HAIKU_MODEL = "claude-haiku-4-5"  # For simple extractions

# Pricing per 1M tokens (input, output)
PRICING = {
    "claude-opus-5": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Image optimization
MAX_IMAGE_DIMENSION = 2048  # Max width/height to limit token cost
MIN_IMAGE_DIMENSION = 400   # Don't resize below this

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}


# --------------------------------------------------------------------------- #
# Data Classes
# --------------------------------------------------------------------------- #

@dataclass
class ExtractionResult:
    """Result from one extraction attempt."""
    success: bool
    method: str  # "pattern", "llm_md", "llm_pdf", "llm_image"
    items: list[dict]
    cost: float
    tokens_used: int
    error: Optional[str] = None


@dataclass
class MenuItem:
    """Structured menu item."""
    name: str
    price: Optional[str]
    description: Optional[str]
    section: Optional[str]
    currency: str = "USD"


# --------------------------------------------------------------------------- #
# Image Utilities
# --------------------------------------------------------------------------- #

def estimate_image_tokens(width: int, height: int) -> int:
    """Calculate token count for an image based on dimensions."""
    tokens = (width / 768) * (height / 768) * 512
    return int(tokens) + 1  # Round up


def optimize_image_size(img: Image.Image) -> tuple[Image.Image, int]:
    """
    Resize image if too large to reduce token cost.
    Returns (optimized_image, estimated_tokens).
    """
    width, height = img.size

    # Calculate current tokens
    current_tokens = estimate_image_tokens(width, height)

    # If already small enough, return as-is
    if width <= MAX_IMAGE_DIMENSION and height <= MAX_IMAGE_DIMENSION:
        return img, current_tokens

    # Resize while maintaining aspect ratio
    ratio = min(MAX_IMAGE_DIMENSION / width, MAX_IMAGE_DIMENSION / height)
    new_width = max(int(width * ratio), MIN_IMAGE_DIMENSION)
    new_height = max(int(height * ratio), MIN_IMAGE_DIMENSION)

    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    new_tokens = estimate_image_tokens(new_width, new_height)

    print(f"  Resized image: {width}×{height} ({current_tokens} tokens) → "
          f"{new_width}×{new_height} ({new_tokens} tokens)")

    return resized, new_tokens


def download_and_prepare_image(url: str, timeout: int = 30) -> Optional[tuple[str, str, int]]:
    """
    Download image from URL and prepare for Claude API.
    Returns (base64_data, media_type, estimated_tokens) or None on failure.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()

        # Detect media type
        content_type = response.headers.get("content-type", "").lower()
        if "image/png" in content_type:
            media_type = "image/png"
        elif "image/jpeg" in content_type or "image/jpg" in content_type:
            media_type = "image/jpeg"
        elif "image/webp" in content_type:
            media_type = "image/webp"
        elif "image/gif" in content_type:
            media_type = "image/gif"
        else:
            print(f"  Unsupported image type: {content_type}")
            return None

        # Load and optimize image
        img = Image.open(BytesIO(response.content))

        # Convert RGBA to RGB if needed (for JPEG)
        if img.mode == "RGBA" and media_type == "image/jpeg":
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            img = rgb_img

        # Optimize size
        img, estimated_tokens = optimize_image_size(img)

        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format=img.format or "PNG")
        b64_data = base64.standard_b64encode(buffer.getvalue()).decode("ascii")

        return b64_data, media_type, estimated_tokens

    except Exception as e:
        print(f"  Failed to download/process image: {e}")
        return None


def find_menu_images(html_content: str, base_url: str) -> list[str]:
    """
    Extract likely menu image URLs from scraped HTML/MD content.
    Looks for images with 'menu' in filename or nearby text.
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    soup = BeautifulSoup(html_content, "html.parser")
    image_urls = []

    # Find all images
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, src)

        # Check if likely a menu image
        src_lower = src.lower()
        alt_text = (img.get("alt") or "").lower()

        if any(keyword in src_lower or keyword in alt_text
               for keyword in ["menu", "food", "dish", "plate"]):
            image_urls.append(full_url)

    return image_urls


# --------------------------------------------------------------------------- #
# Extraction Methods
# --------------------------------------------------------------------------- #

def extract_from_md_pattern(md_file_path: Path) -> ExtractionResult:
    """
    FREE: Pattern-based extraction from markdown table.
    Looks for the table created by scrape_and_find_menu.py.
    """
    try:
        with open(md_file_path, encoding="utf-8") as f:
            content = f.read()

        items = []

        # Look for extracted items table
        if "### Extracted Menu Items" in content:
            # Find the table
            table_match = re.search(
                r"### Extracted Menu Items\s*\n\s*\|.*?\|.*?\|.*?\|\s*\n\|[-\s|]+\|\s*\n((?:\|[^\n]+\n?)+)",
                content,
                re.MULTILINE
            )

            if table_match:
                table_rows = table_match.group(1).strip().split("\n")

                for row in table_rows:
                    # Parse: | Name | Price | Description |
                    parts = [p.strip() for p in row.split("|")[1:-1]]
                    if len(parts) >= 3:
                        name, price, desc = parts[0], parts[1], parts[2]

                        # Skip garbage rows
                        if name and price and not re.match(r"^\$?\d+\.?\d*$", name):
                            items.append({
                                "name": name,
                                "price": price if price != "-" else None,
                                "description": desc if desc != "-" else None,
                                "section": None,
                                "currency": "USD"
                            })

        # Success if we found a reasonable number of items
        if len(items) >= 5:
            return ExtractionResult(
                success=True,
                method="pattern",
                items=items,
                cost=0.0,
                tokens_used=0
            )
        else:
            return ExtractionResult(
                success=False,
                method="pattern",
                items=[],
                cost=0.0,
                tokens_used=0,
                error=f"Only found {len(items)} items (threshold: 5)"
            )

    except Exception as e:
        return ExtractionResult(
            success=False,
            method="pattern",
            items=[],
            cost=0.0,
            tokens_used=0,
            error=str(e)
        )


def extract_from_md_llm(
    md_file_path: Path,
    client: anthropic.Anthropic,
    model: str = HAIKU_MODEL
) -> ExtractionResult:
    """
    CHEAPER: Use LLM to extract from markdown text.
    Uses Haiku by default for cost savings.
    """
    try:
        with open(md_file_path, encoding="utf-8") as f:
            md_content = f.read()

        # Truncate if too long (keep first 100K chars)
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
      "section": "Section name if available (e.g., Appetizers, Entrees)",
      "currency": "USD"
    }}
  ]
}}

Only include actual menu items with prices. Skip navigation, headers, and non-menu content.

Content:
{md_content}"""

        response = client.messages.create(
            model=model,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text
        text = next((b.text for b in response.content if b.type == "text"), "")

        # Parse JSON
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            result = json.loads(json_match.group(0))
            items = result.get("items", [])

            # Calculate cost
            input_price, output_price = PRICING[model]
            cost = (response.usage.input_tokens * input_price / 1_000_000 +
                   response.usage.output_tokens * output_price / 1_000_000)

            return ExtractionResult(
                success=len(items) > 0,
                method="llm_md",
                items=items,
                cost=cost,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens
            )

        return ExtractionResult(
            success=False,
            method="llm_md",
            items=[],
            cost=0.0,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            error="Failed to parse JSON response"
        )

    except Exception as e:
        return ExtractionResult(
            success=False,
            method="llm_md",
            items=[],
            cost=0.0,
            tokens_used=0,
            error=str(e)
        )


def extract_from_pdf_llm(
    pdf_url: str,
    client: anthropic.Anthropic,
    model: str = DEFAULT_MODEL,
    timeout: int = 30
) -> ExtractionResult:
    """
    EXPENSIVE: Download PDF and extract with LLM using document block.
    """
    try:
        # Download PDF
        response = requests.get(pdf_url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()

        pdf_bytes = response.content

        # Check size (32MB limit)
        if len(pdf_bytes) > 32 * 1024 * 1024:
            return ExtractionResult(
                success=False,
                method="llm_pdf",
                items=[],
                cost=0.0,
                tokens_used=0,
                error="PDF exceeds 32MB limit"
            )

        # Encode to base64
        b64_pdf = base64.standard_b64encode(pdf_bytes).decode("ascii")

        prompt = """Extract all menu items from this PDF menu.

Return a JSON array with this structure:
{
  "items": [
    {
      "name": "Dish name",
      "price": "$12.99",
      "description": "Description if available",
      "section": "Section name (e.g., Appetizers, Entrees)",
      "currency": "USD"
    }
  ]
}

Only include actual food/drink items with prices."""

        response = client.messages.create(
            model=model,
            max_tokens=16000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": b64_pdf
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )

        # Extract text
        text = next((b.text for b in response.content if b.type == "text"), "")

        # Parse JSON
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            result = json.loads(json_match.group(0))
            items = result.get("items", [])

            # Calculate cost
            input_price, output_price = PRICING[model]
            cost = (response.usage.input_tokens * input_price / 1_000_000 +
                   response.usage.output_tokens * output_price / 1_000_000)

            return ExtractionResult(
                success=len(items) > 0,
                method="llm_pdf",
                items=items,
                cost=cost,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens
            )

        return ExtractionResult(
            success=False,
            method="llm_pdf",
            items=[],
            cost=0.0,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            error="Failed to parse JSON response"
        )

    except Exception as e:
        return ExtractionResult(
            success=False,
            method="llm_pdf",
            items=[],
            cost=0.0,
            tokens_used=0,
            error=str(e)
        )


def extract_from_image_llm(
    image_url: str,
    client: anthropic.Anthropic,
    model: str = DEFAULT_MODEL
) -> ExtractionResult:
    """
    LAST RESORT: Extract menu from image using vision.
    Optimizes image size to reduce token cost.
    """
    try:
        # Download and prepare image
        image_data = download_and_prepare_image(image_url)
        if not image_data:
            return ExtractionResult(
                success=False,
                method="llm_image",
                items=[],
                cost=0.0,
                tokens_used=0,
                error="Failed to download/process image"
            )

        b64_data, media_type, estimated_tokens = image_data

        print(f"  Image prepared: {media_type}, ~{estimated_tokens} tokens")

        prompt = """Extract all menu items from this menu image.

Return a JSON array with this structure:
{
  "items": [
    {
      "name": "Dish name",
      "price": "$12.99",
      "description": "Description if visible",
      "section": "Section name if visible",
      "currency": "USD"
    }
  ]
}

Extract everything you can see. If prices aren't visible, set price to null."""

        response = client.messages.create(
            model=model,
            max_tokens=16000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )

        # Extract text
        text = next((b.text for b in response.content if b.type == "text"), "")

        # Parse JSON
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            result = json.loads(json_match.group(0))
            items = result.get("items", [])

            # Calculate cost
            input_price, output_price = PRICING[model]
            cost = (response.usage.input_tokens * input_price / 1_000_000 +
                   response.usage.output_tokens * output_price / 1_000_000)

            return ExtractionResult(
                success=len(items) > 0,
                method="llm_image",
                items=items,
                cost=cost,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens
            )

        return ExtractionResult(
            success=False,
            method="llm_image",
            items=[],
            cost=0.0,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            error="Failed to parse JSON response"
        )

    except Exception as e:
        return ExtractionResult(
            success=False,
            method="llm_image",
            items=[],
            cost=0.0,
            tokens_used=0,
            error=str(e)
        )


# --------------------------------------------------------------------------- #
# Main Pipeline
# --------------------------------------------------------------------------- #

def sanitize_filename(url: str) -> str:
    """Convert URL to safe filename."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    path = parsed.path.strip("/").replace("/", "_")
    return f"{domain}_{path}" if path else domain


def finalize_menu(
    menu_urls_json: Path,
    md_directory: Path,
    output_file: Path,
    use_image_fallback: bool = True
) -> dict[str, Any]:
    """
    Main extraction pipeline with tiered fallback strategy.

    Returns summary statistics.
    """
    client = anthropic.Anthropic()

    # Load restaurant data
    with open(menu_urls_json) as f:
        restaurants = json.load(f)

    results = []
    stats = {
        "total": len(restaurants),
        "pattern": 0,
        "llm_md": 0,
        "llm_pdf": 0,
        "llm_image": 0,
        "failed": 0,
        "total_cost": 0.0,
        "total_tokens": 0
    }

    for i, restaurant in enumerate(restaurants, 1):
        input_url = restaurant.get("input_url", "")
        menu_url = restaurant.get("menu_url")
        menu_url_kind = restaurant.get("menu_url_kind")

        print(f"\n[{i}/{len(restaurants)}] {input_url}")
        print(f"  Menu URL: {menu_url} ({menu_url_kind})")

        # Construct MD filename
        md_filename = sanitize_filename(input_url) + ".md"
        md_path = md_directory / md_filename

        result = None

        # Tier 1: Pattern extraction (FREE)
        if md_path.exists():
            print("  Trying: Pattern extraction from MD...")
            result = extract_from_md_pattern(md_path)

            if result.success:
                print(f"  ✓ Success! Extracted {len(result.items)} items (FREE)")
                stats["pattern"] += 1

        # Tier 2: LLM on MD (CHEAPER)
        if not result or not result.success:
            if md_path.exists():
                print("  Trying: LLM extraction from MD...")
                result = extract_from_md_llm(md_path, client, model=HAIKU_MODEL)

                if result.success:
                    print(f"  ✓ Success! Extracted {len(result.items)} items "
                          f"(${result.cost:.4f}, {result.tokens_used} tokens)")
                    stats["llm_md"] += 1
                    stats["total_cost"] += result.cost
                    stats["total_tokens"] += result.tokens_used

        # Tier 3: LLM on PDF (EXPENSIVE)
        if not result or not result.success:
            if menu_url_kind == "pdf" and menu_url:
                print("  Trying: LLM extraction from PDF...")
                result = extract_from_pdf_llm(menu_url, client, model=DEFAULT_MODEL)

                if result.success:
                    print(f"  ✓ Success! Extracted {len(result.items)} items "
                          f"(${result.cost:.4f}, {result.tokens_used} tokens)")
                    stats["llm_pdf"] += 1
                    stats["total_cost"] += result.cost
                    stats["total_tokens"] += result.tokens_used

        # Tier 4: LLM on Image (LAST RESORT)
        if not result or not result.success:
            if use_image_fallback and md_path.exists():
                print("  Trying: Find menu images from scraped content...")

                with open(md_path, encoding="utf-8") as f:
                    md_content = f.read()

                image_urls = find_menu_images(md_content, input_url)

                if image_urls:
                    print(f"  Found {len(image_urls)} potential menu images")

                    # Try first image only (to limit cost)
                    for img_url in image_urls[:1]:
                        print(f"  Trying: LLM extraction from image: {img_url}")
                        result = extract_from_image_llm(img_url, client, model=DEFAULT_MODEL)

                        if result.success:
                            print(f"  ✓ Success! Extracted {len(result.items)} items "
                                  f"(${result.cost:.4f}, {result.tokens_used} tokens)")
                            stats["llm_image"] += 1
                            stats["total_cost"] += result.cost
                            stats["total_tokens"] += result.tokens_used
                            break

        # Record result
        if result and result.success:
            results.append({
                "url": input_url,
                "menu_url": menu_url,
                "method": result.method,
                "items": result.items,
                "cost": result.cost,
                "tokens_used": result.tokens_used
            })
        else:
            print(f"  ✗ Failed: {result.error if result else 'No extraction attempted'}")
            stats["failed"] += 1
            results.append({
                "url": input_url,
                "menu_url": menu_url,
                "method": None,
                "items": [],
                "cost": 0.0,
                "tokens_used": 0,
                "error": result.error if result else "No extraction method succeeded"
            })

    # Save results
    output = {
        "stats": stats,
        "results": results
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total restaurants: {stats['total']}")
    print(f"Pattern extraction (FREE): {stats['pattern']}")
    print(f"LLM on MD: {stats['llm_md']}")
    print(f"LLM on PDF: {stats['llm_pdf']}")
    print(f"LLM on Image: {stats['llm_image']}")
    print(f"Failed: {stats['failed']}")
    print(f"\nTotal cost: ${stats['total_cost']:.2f}")
    print(f"Total tokens: {stats['total_tokens']:,}")
    print(f"Average cost per restaurant: ${stats['total_cost'] / stats['total']:.4f}")
    print(f"\nResults saved to: {output_file}")

    return stats


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Token-optimized menu extraction with image fallback"
    )
    parser.add_argument(
        "menu_urls_json",
        type=Path,
        help="JSON file from menu_url_finder.py"
    )
    parser.add_argument(
        "--md-dir",
        type=Path,
        default=Path("scraped_menus"),
        help="Directory containing MD files from scrape_and_find_menu.py"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("final_menus.json"),
        help="Output JSON file"
    )
    parser.add_argument(
        "--no-image-fallback",
        action="store_true",
        help="Skip image extraction tier"
    )

    args = parser.parse_args()

    if not args.menu_urls_json.exists():
        print(f"Error: {args.menu_urls_json} not found", file=sys.stderr)
        sys.exit(1)

    if not args.md_dir.exists():
        print(f"Warning: {args.md_dir} not found - skipping MD extraction")

    finalize_menu(
        args.menu_urls_json,
        args.md_dir,
        args.output,
        use_image_fallback=not args.no_image_fallback
    )


if __name__ == "__main__":
    main()
