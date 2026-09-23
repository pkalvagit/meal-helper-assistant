"""
Menu filtering tool - applies user profile constraints.
"""
from typing import List, Dict, Any
from langchain.tools import tool


@tool
def filter_menu_by_user_profile(
    menu_items: List[Dict[str, Any]],
    allergies: List[str],
    dietary_restrictions: List[str],
    max_price: float,
    min_protein_g: float = 0,
    max_calories: int = 10000
) -> Dict[str, Any]:
    """
    Filter menu items based on user profile.

    Args:
        menu_items: List of menu items
        allergies: User allergies (e.g., ["peanuts", "shellfish"])
        dietary_restrictions: Restrictions (e.g., ["no_beef", "vegan"])
        max_price: Maximum price per item
        min_protein_g: Minimum protein in grams
        max_calories: Maximum calories

    Returns:
        {
            "filtered_items": [...],
            "removed_count": int,
            "removal_reasons": {item_name: [reasons]}
        }
    """
    filtered = []
    removal_reasons = {}

    # Normalize for matching
    allergies_lower = [a.lower() for a in allergies]
    restrictions_lower = [r.lower().replace("no_", "").replace("_", " ")
                          for r in dietary_restrictions]

    for item in menu_items:
        reasons = []
        name = item.get("name", "")

        # Check price (handle None)
        price_str = item.get("price") or ""
        try:
            import re
            price_match = re.search(r'\d+\.?\d*', str(price_str).replace(',', ''))
            if price_match:
                price = float(price_match.group(0))
                if price > max_price:
                    reasons.append(f"Price ${price} exceeds max ${max_price}")
        except:
            pass

        # Check allergens (handle None values)
        desc = item.get("description") or ""
        description = (desc + " " + name).lower()
        ingredients = item.get("ingredients") or []
        ingredient_text = " ".join(str(i) for i in ingredients).lower()

        for allergen in allergies_lower:
            if (allergen in description or
                allergen in ingredient_text or
                allergen in item.get("allergens", [])):
                reasons.append(f"Contains allergen: {allergen}")

        # Check dietary restrictions
        for restriction in restrictions_lower:
            if restriction in description or restriction in ingredient_text:
                reasons.append(f"Contains restricted ingredient: {restriction}")

        # Check nutrition if available
        nutrition = item.get("nutrition", {})
        if nutrition:
            if nutrition.get("protein_g", 0) < min_protein_g:
                reasons.append(f"Protein {nutrition.get('protein_g')}g < min {min_protein_g}g")

            if nutrition.get("calories", 0) > max_calories:
                reasons.append(f"Calories {nutrition.get('calories')} > max {max_calories}")

        # Add or reject
        if reasons:
            removal_reasons[name] = reasons
        else:
            filtered.append(item)

    return {
        "filtered_items": filtered,
        "removed_count": len(menu_items) - len(filtered),
        "removal_reasons": removal_reasons,
        "passed_count": len(filtered)
    }


@tool
def rank_items_by_preferences(
    items: List[Dict[str, Any]],
    preferences: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Rank menu items by user preferences.

    Args:
        items: Filtered menu items
        preferences: User preferences (e.g., {"high_protein": true})

    Returns:
        Ranked list of items with scores
    """
    scored_items = []

    for item in items:
        score = 0
        reasons = []

        desc = item.get("description") or ""
        name = item.get("name") or ""
        description = (desc + " " + name).lower()
        nutrition = item.get("nutrition", {})

        # High protein preference
        if preferences.get("high_protein"):
            protein = nutrition.get("protein_g", 0)
            if protein > 25:
                score += 10
                reasons.append(f"High protein: {protein}g")
            elif protein > 15:
                score += 5

        # Low carb preference
        if preferences.get("low_carb"):
            carbs = nutrition.get("carbs_g", 100)
            if carbs < 20:
                score += 10
                reasons.append(f"Low carb: {carbs}g")
            elif carbs < 40:
                score += 5

        # Vegetarian preference
        if preferences.get("vegetarian_options"):
            if any(tag in description for tag in ["vegetarian", "vegan", "plant-based"]):
                score += 8
                reasons.append("Vegetarian option")

        # Organic preference
        if preferences.get("organic"):
            if "organic" in description:
                score += 5
                reasons.append("Organic")

        scored_items.append({
            **item,
            "preference_score": score,
            "match_reasons": reasons
        })

    # Sort by score
    scored_items.sort(key=lambda x: x["preference_score"], reverse=True)

    return scored_items
