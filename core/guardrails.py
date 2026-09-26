"""
Guardrails for input validation and intent classification.
Provider-agnostic: uses Claude (Haiku) OR OpenAI (GPT-4o-mini/5.4-mini/5.4-nano).
Configured via config/llm_config.yaml -> guardrail.provider
"""
import json
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser

from core.llm_factory import get_llm_factory
from core.models import GuardrailResult, Intent, UserProfile


class RestaurantGuardrail:
    """
    Pre-flight checks before calling main agent.

    Fully flexible - respects guardrail.provider in config:
    - Claude: claude-haiku-4-5 ($1/$5 per MTok)
    - OpenAI: gpt-4o-mini ($0.15/$0.60), gpt-5.4-mini ($0.10/$0.40), gpt-5.4-nano ($0.05/$0.20)
    """

    def __init__(self, provider: Optional[str] = None):
        """
        Initialize guardrail with LLM from config.

        Args:
            provider: Override config provider ("claude" or "openai").
                     If None, uses guardrail.provider from config.
        """
        self.factory = get_llm_factory()
        self.llm = self.factory.get_llm("guardrail", provider=provider)
        self.json_parser = JsonOutputParser()

        # Track which provider is being used
        config = self.factory.config["guardrail"]
        self.active_provider = provider or config["provider"]
        self.active_model = config[self.active_provider]["model"]

        import logging
        logging.getLogger("meal-helper").debug(f"Guardrail using {self.active_provider}: {self.active_model}")

    def check_query(
        self,
        query: str,
        user_profile: Optional[UserProfile] = None
    ) -> GuardrailResult:
        """
        Check if query is about restaurants/food.
        Returns intent if valid, rejection reason if not.
        """
        # Step 1: Topic relevance check (binary)
        is_relevant = self._check_topic_relevance(query)

        if not is_relevant:
            return GuardrailResult(
                is_valid=False,
                reason="Query is not about restaurants, food, or dining. "
                       "I can only help with restaurant recommendations.",
                cost=0.0001  # Approx cost
            )

        # Step 2: Extract structured intent
        intent = self._extract_intent(query, user_profile)

        return GuardrailResult(
            is_valid=True,
            intent=intent,
            cost=0.005  # Approx cost for both calls
        )

    def _check_topic_relevance(self, query: str) -> bool:
        """Fast binary check: is this asking to FIND/GET food from restaurants?"""
        messages = [
            SystemMessage(content="""You are a topic classifier for a meal recommendation assistant.
Respond with ONLY "yes" or "no" - nothing else.

Is the user asking to FIND or GET food/meals from restaurants?

Answer "yes" ONLY if they want to:
- Find restaurants or meals
- Get food recommendations
- Order/eat food from a restaurant

Answer "no" if they are:
- Asking for business advice (opening a restaurant, menu planning for their business)
- Requesting consulting/ideas for their own restaurant
- Asking off-topic questions (jokes, general knowledge)
- Seeking nutrition advice without wanting restaurant recommendations

Examples:
"find me biryani near me" → yes
"burger places under $20" → yes
"I want to open a restaurant, what menu should I have" → no
"give me ideas for my restaurant menu" → no
"what's a good name for an Indian restaurant" → no"""),
            HumanMessage(content=query)
        ]

        response = self.llm.invoke(messages)
        text = response.content.lower().strip()

        return "yes" in text

    def _extract_intent(
        self,
        query: str,
        user_profile: Optional[UserProfile]
    ) -> Intent:
        """Extract structured intent from query."""
        profile_context = ""
        if user_profile:
            profile_context = f"""
User profile:
- Allergies: {', '.join(user_profile.allergies) if user_profile.allergies else 'None'}
- Dietary restrictions: {', '.join(user_profile.dietary_restrictions) if user_profile.dietary_restrictions else 'None'}
- Budget: ${user_profile.budget.max_per_meal} per meal
- Preferences: {user_profile.preferences}
"""

        system_prompt = f"""Extract structured intent from the user's query.
{profile_context}

Return JSON with this exact structure:
{{
  "query_type": "search|filter|question",
  "location": {{"lat": 38.0, "lng": -77.0, "radius": 5000}} or null,
  "cuisine": "italian" or null,
  "price_range": {{"min": 0, "max": 15}} or null,
  "dietary_requirements": ["high_protein", "vegetarian"],
  "nutrition_requirements": {{"min_protein_g": 25, "max_calories": 800}},
  "meal_type": "breakfast|lunch|dinner|snack" or null
}}

Rules:
- If no location mentioned, use user's default or set to null
- Extract price from query ("under $15" → {{"max": 15}})
- Identify dietary needs ("high protein" → add to dietary_requirements)
- Be precise with numbers"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Query: {query}")
        ]

        response = self.llm.invoke(messages)

        # Parse JSON response
        try:
            intent_data = json.loads(response.content)

            # Use user profile location if not specified
            if not intent_data.get("location") and user_profile and user_profile.location:
                intent_data["location"] = user_profile.location

            return Intent(
                is_restaurant_query=True,
                query_type=intent_data.get("query_type", "search"),
                location=intent_data.get("location"),
                cuisine=intent_data.get("cuisine"),
                price_range=intent_data.get("price_range"),
                dietary_requirements=intent_data.get("dietary_requirements", []),
                nutrition_requirements=intent_data.get("nutrition_requirements", {}),
                meal_type=intent_data.get("meal_type"),
                raw_query=query
            )

        except (json.JSONDecodeError, KeyError) as e:
            # Fallback: basic intent
            print(f"Warning: Intent extraction failed: {e}")
            return Intent(
                is_restaurant_query=True,
                query_type="question",
                raw_query=query
            )
