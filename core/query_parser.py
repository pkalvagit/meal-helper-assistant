"""
Query parser - extracts food intent from natural language queries.
Removes price info, location words, and converts generic terms to better search queries.
"""
import re
from typing import Optional


class QueryParser:
    """Parse user queries to extract food search intent."""

    # Generic terms to improve
    GENERIC_MAPPINGS = {
        "meals": "restaurant",
        "food": "restaurant",
        "lunch": "lunch restaurant",
        "dinner": "dinner restaurant",
        "breakfast": "breakfast restaurant",
        "brunch": "brunch restaurant",
        "eat": "restaurant",
        "something to eat": "restaurant",
    }

    # Words to remove (they don't help Google Places)
    NOISE_WORDS = [
        "near me", "near by", "nearby", "around here", "in the area",
        "under", "below", "less than", "within", "for under",
        "fetch", "fecth", "find", "get", "show", "give me", "search for",
        "i want", "looking for", "can you", "could you",
        "the", "me", "my", "a", "an", "some",
    ]

    # Location patterns to remove (since they're extracted separately)
    LOCATION_PATTERNS = [
        # Full addresses (most specific first) - matches "123 Main St, Boston", "5th Avenue, NY", etc.
        r'\bin\s+(?:\d+\s+)?(?:[A-Z][a-z]*|\d+(?:st|nd|rd|th))[^,]*(?:,\s*[A-Z][^,]+)*(?:,?\s+[A-Z]{2})?(?:\s+\d{5})?',
        r'\bnear\s+(?:\d+\s+)?(?:[A-Z][a-z]*|\d+(?:st|nd|rd|th))[^,]*(?:,\s*[A-Z][^,]+)*(?:,?\s+[A-Z]{2})?(?:\s+\d{5})?',
        r'\bat\s+(?:\d+\s+)?(?:[A-Z][a-z]*|\d+(?:st|nd|rd|th))[^,]*(?:,\s*[A-Z][^,]+)*(?:,?\s+[A-Z]{2})?(?:\s+\d{5})?',
        r'\baround\s+(?:\d+\s+)?(?:[A-Z][a-z]*|\d+(?:st|nd|rd|th))[^,]*(?:,\s*[A-Z][^,]+)*(?:,?\s+[A-Z]{2})?(?:\s+\d{5})?',

        # ZIP codes only (fallback)
        r'\bin\s+\d{5}(?:-\d{4})?',
        r'\bnear\s+\d{5}(?:-\d{4})?',
        r'\bat\s+\d{5}(?:-\d{4})?',
        r'\baround\s+\d{5}(?:-\d{4})?',

        # Trailing ZIP code
        r'\s\d{5}$',
    ]

    # Price pattern to remove (but NOT ZIP codes or street numbers)
    # Match: $20, 20 dollars, $15.99, but NOT standalone 5-digit numbers (ZIP codes)
    PRICE_PATTERN = r'\$\d+(?:\.\d{2})?|\d+(?:\.\d{2})?\s+(?:dollars?|bucks?|usd)'

    @classmethod
    def extract_food_query(cls, user_message: str) -> str:
        """
        Extract the food/restaurant intent from a user message.

        Args:
            user_message: Raw user input like "fetch me meals under $15 near me"

        Returns:
            Cleaned query for Google Places like "restaurant"

        Examples:
            "meals under $15" -> "restaurant"
            "biryani near me" -> "biryani"
            "find pizza under $20" -> "pizza"
            "lunch near me" -> "lunch restaurant"
        """
        query = user_message.lower().strip()

        # Remove price mentions
        query = re.sub(cls.PRICE_PATTERN, '', query, flags=re.IGNORECASE)

        # Remove location patterns (they're extracted separately)
        for pattern in cls.LOCATION_PATTERNS:
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)

        # Remove noise words
        for noise in cls.NOISE_WORDS:
            query = re.sub(rf'\b{re.escape(noise)}\b', '', query, flags=re.IGNORECASE)

        # Clean up whitespace
        query = ' '.join(query.split())

        # If empty or too short, default to "restaurant"
        if not query or len(query) < 2:
            return "restaurant"

        # Replace generic terms with better ones
        for generic, replacement in cls.GENERIC_MAPPINGS.items():
            if query.strip() == generic:
                return replacement

        # If still too generic, add "restaurant"
        if query in ["food", "eat", "something"]:
            return "restaurant"

        return query.strip()


# Quick test
if __name__ == "__main__":
    parser = QueryParser()

    test_cases = [
        "fecth me the meals near me under $15",
        "biryani under $25 near me",
        "find pizza restaurants",
        "lunch near me",
        "indian food under $20",
        "chipotle menu",
        "burger",
    ]

    print("Query Parser Tests:\n")
    for test in test_cases:
        result = parser.extract_food_query(test)
        print(f"  '{test}'")
        print(f"  -> '{result}'")
        print()
