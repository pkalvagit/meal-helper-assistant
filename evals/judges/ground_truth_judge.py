"""
Ground Truth Judge - Verify recommended items exist in restaurant menus.
"""
from typing import Dict, Any
from .base_judge import BaseJudge


class GroundTruthJudge(BaseJudge):
    """Judge for menu item authenticity."""

    def build_prompt(self, test_case: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Build ground truth verification prompt."""
        recommendations = result.get("recommendations", [])
        ground_truth = test_case.get("ground_truth", {})

        # Format recommendations
        rec_text = self._format_recommendations(recommendations)

        # Format ground truth if available
        valid_items = ground_truth.get("sample_valid_items", [])
        invalid_items = ground_truth.get("sample_invalid_items", [])
        valid_restaurants = ground_truth.get("sample_restaurants", [])

        ground_truth_text = ""
        if valid_items:
            ground_truth_text += f"\nKnown Valid Items: {', '.join(valid_items)}"
        if invalid_items:
            ground_truth_text += f"\nKnown Invalid Items: {', '.join(invalid_items)}"
        if valid_restaurants:
            ground_truth_text += f"\nKnown Restaurants: {', '.join(valid_restaurants)}"

        prompt = f"""You are verifying menu item authenticity for restaurant recommendations.

RECOMMENDED ITEMS:
{rec_text}

GROUND TRUTH REFERENCE:
{ground_truth_text if ground_truth_text else "No specific ground truth provided - use your knowledge of typical restaurant menus"}

Your task:
1. Verify if recommended items are realistic for the restaurant type
2. Check if prices are reasonable for the location and restaurant
3. Assess if descriptions match what you'd expect
4. If ground truth is provided, verify items match

Score (1-5):
5 = All items verified, perfect match with ground truth or highly realistic
4 = Minor discrepancies (small price diff, slight name variation) but plausible
3 = Some items questionable but could exist
2 = Several items don't match ground truth or seem implausible
1 = Most items don't exist or are completely wrong for this restaurant type

Respond with valid JSON only:
{{
  "score": 1-5,
  "reasoning": "detailed explanation of your assessment",
  "item_verification": [
    {{"item": "item name", "exists": true/false, "price_reasonable": true/false, "confidence": 0.0-1.0, "notes": "any comments"}}
  ],
  "verified_items": ["list of verified items"],
  "questionable_items": ["list of questionable items"],
  "issues": ["list any problems found"]
}}
"""
        return prompt

    def _format_recommendations(self, recommendations: list) -> str:
        """Format recommendations for prompt."""
        if not recommendations:
            return "No recommendations provided."

        formatted = []
        for i, rec in enumerate(recommendations, 1):
            if isinstance(rec, dict):
                name = rec.get("name", "Unknown")
                price = rec.get("price", "N/A")
                restaurant = rec.get("restaurant", "Unknown Restaurant")
                desc = rec.get("description", "")

                item_text = f"{i}. {name} at {restaurant} - {price}"
                if desc:
                    item_text += f"\n   Description: {desc}"

                formatted.append(item_text)
            else:
                formatted.append(f"{i}. {str(rec)}")

        return "\n".join(formatted)

    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response."""
        parsed = self.extract_json_from_response(response)

        # Ensure required fields
        if "score" not in parsed:
            # Try to infer from verification results
            verifications = parsed.get("item_verification", [])
            if verifications:
                exists_count = sum(1 for v in verifications if v.get("exists", False))
                total = len(verifications)
                parsed["score"] = int((exists_count / total) * 5) if total > 0 else 3
            else:
                parsed["score"] = 3  # Default middle score

        return parsed

    def calculate_score(self, parsed_response: Dict[str, Any]) -> float:
        """Calculate final ground truth score."""
        score = parsed_response.get("score", 3)

        # Adjust based on verification details
        verifications = parsed_response.get("item_verification", [])
        if verifications:
            exists_count = sum(1 for v in verifications if v.get("exists", False))
            price_ok_count = sum(1 for v in verifications if v.get("price_reasonable", True))
            total = len(verifications)

            if total > 0:
                exists_ratio = exists_count / total
                price_ratio = price_ok_count / total

                # Weighted score: 70% existence, 30% price
                calculated_score = (exists_ratio * 0.7 + price_ratio * 0.3) * 5

                # Take average of LLM score and calculated score
                score = (score + calculated_score) / 2

        return float(score)
