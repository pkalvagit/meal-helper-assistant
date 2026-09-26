"""
Relevance Judge - Evaluate budget adherence and goal alignment.
"""
from typing import Dict, Any
from .base_judge import BaseJudge


class RelevanceJudge(BaseJudge):
    """Judge for recommendation relevance - budget, intent, goals."""

    def build_prompt(self, test_case: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Build relevance evaluation prompt."""
        query = test_case.get("query", "")
        user_profile = test_case.get("user_profile", {})
        recommendations = result.get("recommendations", [])

        # Extract profile details
        budget = user_profile.get("budget", {}).get("max_per_meal", "N/A")
        allergies = user_profile.get("allergies", [])
        restrictions = user_profile.get("dietary_restrictions", [])
        preferences = user_profile.get("preferences", {})
        nutrition_targets = preferences.get("nutrition_targets", {})

        # Format recommendations
        rec_text = self._format_recommendations(recommendations)

        prompt = f"""You are evaluating recommendation quality and relevance.

USER QUERY: "{query}"

USER PROFILE:
- Budget: ${budget} per meal
- Allergies: {', '.join(allergies) if allergies else 'None'}
- Dietary Restrictions: {', '.join(restrictions) if restrictions else 'None'}
- Preferences: {preferences}
- Nutrition Targets: {nutrition_targets if nutrition_targets else 'None specified'}

RECOMMENDATIONS:
{rec_text}

Evaluate on these dimensions:

1. BUDGET ADHERENCE: Are all items within ${budget}?
2. QUERY INTENT: Do recommendations match what the user asked for?
3. GOAL ALIGNMENT: Do they support user's dietary/nutrition goals?
4. VARIETY: Is there good selection and diversity?

Score (1-5):
5 = Perfect match for all user needs, excellent recommendations
4 = Good match overall, minor improvements possible
3 = Acceptable, meets basic requirements but could be better targeted
2 = Somewhat relevant but misses key requirements
1 = Poor match, doesn't meet user needs

Respond with valid JSON only:
{{
  "score": 1-5,
  "reasoning": "overall assessment explaining the score",
  "budget_score": 1-5,
  "intent_score": 1-5,
  "goal_score": 1-5,
  "variety_score": 1-5,
  "budget_violations": ["items over budget with prices"],
  "strengths": ["what worked well"],
  "weaknesses": ["what could improve"]
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
                restaurant = rec.get("restaurant", "Unknown")
                desc = rec.get("description", "")

                item_text = f"{i}. {name} at {restaurant} - {price}"
                if desc:
                    item_text += f"\n   {desc}"

                formatted.append(item_text)
            else:
                formatted.append(f"{i}. {str(rec)}")

        return "\n".join(formatted)

    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response."""
        parsed = self.extract_json_from_response(response)

        # Ensure required fields
        if "score" not in parsed:
            # Calculate from sub-scores if available
            sub_scores = [
                parsed.get("budget_score", 3),
                parsed.get("intent_score", 3),
                parsed.get("goal_score", 3),
                parsed.get("variety_score", 3),
            ]
            parsed["score"] = sum(sub_scores) / len(sub_scores)

        return parsed

    def calculate_score(self, parsed_response: Dict[str, Any]) -> float:
        """Calculate final relevance score."""
        # Use weighted average of dimensions
        weights = self.config.get("scoring", {}).get("weights", {})
        budget_weight = weights.get("budget_adherence", 0.3)
        intent_weight = weights.get("query_intent_match", 0.3)
        goal_weight = weights.get("goal_alignment", 0.3)
        variety_weight = weights.get("variety", 0.1)

        budget_score = parsed_response.get("budget_score", 3)
        intent_score = parsed_response.get("intent_score", 3)
        goal_score = parsed_response.get("goal_score", 3)
        variety_score = parsed_response.get("variety_score", 3)

        weighted_score = (
            budget_score * budget_weight +
            intent_score * intent_weight +
            goal_score * goal_weight +
            variety_score * variety_weight
        )

        # Also consider overall score from LLM
        llm_score = parsed_response.get("score", 3)

        # Take weighted average (70% weighted dimensions, 30% LLM holistic)
        final_score = weighted_score * 0.7 + llm_score * 0.3

        return float(final_score)
