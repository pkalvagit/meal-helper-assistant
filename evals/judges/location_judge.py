"""
Location Judge - Verify restaurants are in correct geographic location.
"""
from typing import Dict, Any
import math
from .base_judge import BaseJudge


class LocationJudge(BaseJudge):
    """Judge for geographic location accuracy."""

    def __init__(self, config: Dict[str, Any], llm_factory=None):
        super().__init__(config, llm_factory)
        self.use_llm_verification = config.get("llm_verification", False)

    def build_prompt(self, test_case: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Build location verification prompt (only if LLM verification enabled)."""
        query = test_case.get("query", "")
        expected = test_case.get("expected_behavior", {})
        expected_location = expected.get("expected_location", "Unknown")
        recommendations = result.get("recommendations", [])

        # Format recommendations with locations
        rec_text = self._format_recommendations(recommendations)

        prompt = f"""You are evaluating location accuracy for restaurant recommendations.

USER QUERY: "{query}"
EXPECTED LOCATION: {expected_location}

RECOMMENDED RESTAURANTS:
{rec_text}

Verify:
1. Are all restaurants in or near the expected location?
2. Are distances reasonable for the query?
3. If user specified a specific area, are results constrained to that area?

Score (1-5):
5 = All restaurants in perfect location, highly relevant
4 = All restaurants nearby, minor variations acceptable
3 = Most restaurants in right area, some outliers
2 = Many restaurants too far from expected location
1 = Most restaurants in wrong location

Respond with valid JSON only:
{{
  "score": 1-5,
  "reasoning": "explain location assessment",
  "restaurants_in_area": ["restaurants in correct location"],
  "restaurants_out_of_area": ["restaurants too far"],
  "issues": ["any location problems"]
}}
"""
        return prompt

    def _format_recommendations(self, recommendations: list) -> str:
        """Format recommendations with location info."""
        if not recommendations:
            return "No recommendations provided."

        formatted = []
        for i, rec in enumerate(recommendations, 1):
            if isinstance(rec, dict):
                name = rec.get("name", "Unknown")
                restaurant = rec.get("restaurant", "")
                location = rec.get("location", {})

                item_text = f"{i}. {name}"
                if restaurant:
                    item_text += f" at {restaurant}"

                if location and isinstance(location, dict):
                    lat = location.get("lat", "N/A")
                    lng = location.get("lng", "N/A")
                    address = location.get("address", "")

                    if address:
                        item_text += f"\n   Address: {address}"
                    if lat != "N/A" and lng != "N/A":
                        item_text += f"\n   Coordinates: ({lat}, {lng})"

                formatted.append(item_text)
            else:
                formatted.append(f"{i}. {str(rec)}")

        return "\n".join(formatted)

    def evaluate_programmatic(
        self,
        test_case: Dict[str, Any],
        agent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Programmatic location verification using distance calculation."""
        expected_behavior = test_case.get("expected_behavior", {})
        max_distance = expected_behavior.get("max_distance_miles", 10.0)

        # Get expected location (could be from user profile or test case)
        user_profile = test_case.get("user_profile", {})
        expected_loc = user_profile.get("location", {})

        if not expected_loc:
            return {
                "score": 3,
                "reasoning": "No expected location provided, cannot verify",
                "distances": {},
            }

        expected_lat = expected_loc.get("lat")
        expected_lng = expected_loc.get("lng")

        if expected_lat is None or expected_lng is None:
            return {
                "score": 3,
                "reasoning": "Expected location missing coordinates",
                "distances": {},
            }

        # Check each recommendation
        recommendations = agent_result.get("recommendations", [])
        distances = {}
        in_range = []
        out_of_range = []

        for rec in recommendations:
            if not isinstance(rec, dict):
                continue

            restaurant = rec.get("restaurant", rec.get("name", "Unknown"))
            location = rec.get("location", {})

            if isinstance(location, dict):
                lat = location.get("lat")
                lng = location.get("lng")

                if lat is not None and lng is not None:
                    distance = self._haversine_distance(
                        expected_lat, expected_lng, lat, lng
                    )
                    distances[restaurant] = round(distance, 2)

                    if distance <= max_distance:
                        in_range.append(restaurant)
                    else:
                        out_of_range.append(restaurant)

        # Calculate score based on percentage in range
        total = len(distances)
        if total == 0:
            score = 3
            reasoning = "No location data available for recommendations"
        else:
            in_range_pct = len(in_range) / total
            # 5 = 100% in range, 4 = 80%+, 3 = 60%+, 2 = 40%+, 1 = <40%
            if in_range_pct >= 1.0:
                score = 5
            elif in_range_pct >= 0.8:
                score = 4
            elif in_range_pct >= 0.6:
                score = 3
            elif in_range_pct >= 0.4:
                score = 2
            else:
                score = 1

            reasoning = f"{len(in_range)}/{total} restaurants within {max_distance} miles"

        return {
            "score": score,
            "reasoning": reasoning,
            "distances": distances,
            "in_range": in_range,
            "out_of_range": out_of_range,
            "max_distance_miles": max_distance,
        }

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points in miles using Haversine formula."""
        R = 3959.0  # Earth radius in miles

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response."""
        parsed = self.extract_json_from_response(response)

        if "score" not in parsed:
            # Infer from in/out of area counts
            in_area = len(parsed.get("restaurants_in_area", []))
            out_area = len(parsed.get("restaurants_out_of_area", []))
            total = in_area + out_area

            if total > 0:
                ratio = in_area / total
                parsed["score"] = int(ratio * 5)
            else:
                parsed["score"] = 3

        return parsed

    def calculate_score(self, parsed_response: Dict[str, Any]) -> float:
        """Calculate final location score."""
        return float(parsed_response.get("score", 3))
